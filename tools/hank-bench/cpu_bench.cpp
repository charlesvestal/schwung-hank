/* Measures render_block cost against the SPI frame budget, ON the device.
 * A 128-frame block is 2.9 ms of audio; the budget is ~2370 us of wall time. */
#include "../../src/dsp/plugin_api_v1.h"
#include <dlfcn.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <time.h>

static host_api_v1_t g_host;
static double now_us() {
    struct timespec t; clock_gettime(CLOCK_MONOTONIC, &t);
    return t.tv_sec * 1e6 + t.tv_nsec / 1e3;
}
int main(int argc, char **argv) {
    const char *so = argv[1];
    void *lib = dlopen(so, RTLD_NOW | RTLD_LOCAL);
    if (!lib) { printf("dlopen: %s\n", dlerror()); return 1; }
    typedef plugin_api_v2_t *(*init_fn)(const host_api_v1_t *);
    plugin_api_v2_t *api = ((init_fn)dlsym(lib, MOVE_PLUGIN_INIT_V2_SYMBOL))(&g_host);
    const int N = 128;
    const double BUDGET = 2370.0;
    printf("%-28s %10s %10s %9s\n", "case", "mean us", "max us", "% budget");
    struct Case { const char *name; int voices; const char *extra; const char *val; };
    Case cases[] = {
        { "1 voice",                 1,  "unison", "0" },
        { "8 voices",                8,  "unison", "0" },
        { "16 voices",              16,  "unison", "0" },
        { "16 voices + unison",     16,  "unison", "1" },
        { "16 + unison + fx",       16,  "unison", "1" },
    };
    for (int c = 0; c < 5; c++) {
        void *inst = api->create_instance(".", 0);
        char b[32];
        api->set_param(inst, "init", "1");
        snprintf(b, sizeof b, "%d", cases[c].voices);
        api->set_param(inst, "voice_count", b);
        api->set_param(inst, cases[c].extra, cases[c].val);
        api->set_param(inst, "op2_level", "0.8");
        api->set_param(inst, "op2_fbk", "0.6");
        api->set_param(inst, "op2_coarse", "7");
        api->set_param(inst, "filter_on", "1");
        api->set_param(inst, "cutoff", "0.6");
        api->set_param(inst, "resonance", "0.5");
        api->set_param(inst, "op1_sustain", "1.0");
        api->set_param(inst, "op1_decay", "1.0");
        if (c == 4) { api->set_param(inst, "width", "0.7");
                      api->set_param(inst, "distortion", "0.5");
                      api->set_param(inst, "crush", "0.3"); }
        for (int v = 0; v < cases[c].voices; v++) {
            uint8_t on[3] = { 0x90, (uint8_t)(48 + v), 100 };
            api->on_midi(inst, on, 3, 0);
        }
        int16_t out[256];
        for (int w = 0; w < 200; w++) api->render_block(inst, out, N);   /* warm */
        double sum = 0, mx = 0; const int R = 2000;
        for (int i = 0; i < R; i++) {
            double t0 = now_us();
            api->render_block(inst, out, N);
            double d = now_us() - t0;
            sum += d; if (d > mx) mx = d;
        }
        printf("%-28s %10.1f %10.1f %8.1f%%\n",
               cases[c].name, sum / R, mx, 100.0 * (sum / R) / BUDGET);
        api->destroy_instance(inst);
    }
    return 0;
}
