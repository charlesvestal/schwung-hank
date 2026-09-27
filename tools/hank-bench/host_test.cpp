/* Loads a built Hank dsp.so through the real plugin_api_v2 ABI and auditions
 * every factory preset. This is the consumer that proves the contract, not a
 * source-level pin: it dlopens, creates an instance, plays a note, renders. */
#include "../../src/dsp/plugin_api_v1.h"
#include <dlfcn.h>
#include <stdio.h>
#include <string.h>
#include <math.h>
#include <stdlib.h>

static host_api_v1_t g_host;   /* zeroed: every callback NULL, reserved tail NULL */

int main(int argc, char **argv) {
    const char *so = argc > 1 ? argv[1] : "build/dsp.so";
    void *lib = dlopen(so, RTLD_NOW | RTLD_LOCAL);
    if (!lib) { printf("dlopen: %s\n", dlerror()); return 1; }
    typedef plugin_api_v2_t *(*init_fn)(const host_api_v1_t *);
    init_fn init = (init_fn)dlsym(lib, MOVE_PLUGIN_INIT_V2_SYMBOL);
    if (!init) { printf("no %s\n", MOVE_PLUGIN_INIT_V2_SYMBOL); return 1; }
    memset(&g_host, 0, sizeof g_host);
    plugin_api_v2_t *api = init(&g_host);
    if (!api || api->api_version != 2) { printf("bad api\n"); return 1; }

    char buf[256];
    void *inst = api->create_instance(".", 0);
    if (!inst) { printf("no instance\n"); return 1; }
    api->get_param(inst, "preset_count", buf, sizeof buf);
    int count = atoi(buf);
    printf("%-16s %-6s %8s %8s %8s  %s\n", "preset", "cat", "peak dB", "rms dB", "tail s", "flags");
    printf("--------------------------------------------------------------------\n");

    int bad = 0;
    for (int i = 0; i < count; i++) {
        snprintf(buf, sizeof buf, "%d", i);
        api->set_param(inst, "preset", buf);
        char name[64]; api->get_param(inst, "preset_name", name, sizeof name);
        char vc[32];   api->get_param(inst, "voice_count", vc, sizeof vc);

        /* percussion-ish patches get a short gate; everything else 2 s */
        int key = 60; double gate = 2.0, secs = 5.0;
        if (strstr(name,"kick")) { key = 36; gate = 0.05; secs = 2.0; }
        else if (strstr(name,"snare")||strstr(name,"hat")||strstr(name,"block")||strstr(name,"zap"))
             { key = 48; gate = 0.05; secs = 2.0; }
        else if (strstr(name,"sub")) key = 36;

        uint8_t on[3]  = { 0x90, (uint8_t)key, 100 };
        uint8_t off[3] = { 0x80, (uint8_t)key, 0 };
        api->on_midi(inst, on, 3, 0);

        const int N = 128;
        int16_t out[256];
        int blocks = (int)(secs * 44100 / N), gb = (int)(gate * 44100 / N);
        /* Two passes: the first finds the peak, the second measures RMS over
         * the SOUNDING part only. A single pass over the whole window counts
         * the silence after a 5 ms hat as signal, so every short percussion
         * patch reported as "quiet" no matter how loud it actually was. */
        static double buf[2 * 44100 * 6];
        long n = 0;
        double peak = 0; int lastLoud = 0;
        for (int b = 0; b < blocks; b++) {
            if (b == gb) api->on_midi(inst, off, 3, 0);
            api->render_block(inst, out, N);
            for (int j = 0; j < N*2; j++) {
                double v = out[j] / 32768.0, a = fabs(v);
                if (a > peak) peak = a;
                if (a > 0.0005) lastLoud = b;
                if (n < (long)(sizeof buf / sizeof buf[0])) buf[n++] = v;
            }
        }
        double sum2 = 0; long cnt = 0;
        const double floorAmp = peak * 0.02;      /* -34 dB below peak */
        for (long j = 0; j < n; j++)
            if (fabs(buf[j]) > floorAmp) { sum2 += buf[j]*buf[j]; cnt++; }
        if (cnt == 0) { cnt = 1; }
        api->on_midi(inst, off, 3, 0);
        double rms = sqrt(sum2/cnt), tail = (double)lastLoud*N/44100.0;
        double pdb = peak>1e-9?20*log10(peak):-120, rdb = rms>1e-9?20*log10(rms):-120;
        char flags[128] = "";
        if (peak < 1e-4) strcat(flags, "SILENT ");
        if (peak >= 0.999) strcat(flags, "CLIP ");
        if (rdb < -45 && peak > 1e-4) strcat(flags, "quiet ");
        if (rdb > -8) strcat(flags, "hot ");
        if (gate > 1.0 && tail < 0.08) strcat(flags, "short ");   /* a mallet IS 0.2 s */
        if (flags[0]) bad++;
        printf("%-16s %-6s %8.1f %8.1f %8.2f  %s\n", name, vc, pdb, rdb, tail, flags);
    }
    api->destroy_instance(inst);
    printf("\n%d presets, %d flagged\n", count, bad);
    return 0;
}
