/* Hold A, play B, release B, release A -- voice_count=1. Stereo f32 to stdout. */
#include <cstdio>
#include <cstdint>
#include <cstring>
#include <dlfcn.h>
#include "../../src/dsp/plugin_api_v1.h"
int main(int argc, char **argv) {
    if (argc < 2) return 2;
    void *h = dlopen(argv[1], RTLD_NOW); if (!h) { fprintf(stderr, "%s\n", dlerror()); return 2; }
    typedef plugin_api_v2_t *(*init_t)(const host_api_v1_t *);
    init_t init = (init_t)dlsym(h, "move_plugin_init_v2"); if (!init) return 2;
    plugin_api_v2_t *api = init(nullptr);
    void *inst = api->create_instance(".", nullptr); if (!inst) return 2;
    api->set_param(inst, "voice_count", "1");
    api->set_param(inst, "decay", "0.95");
    api->set_param(inst, "sustain", "0.9");
    api->set_param(inst, "attack", "0.0");
    typedef void (*rf_t)(void *, float *, int);
    rf_t rf = (rf_t)dlsym(h, "move_plugin_render_float");
    const int N = 128; float il[256]; int16_t o[256];
    const int A = 48, B = 55;
    uint8_t on_a[3]={0x90,A,100}, on_b[3]={0x90,B,100}, off_b[3]={0x80,B,0}, off_a[3]={0x80,A,0};
    for (int b = 0; b < (int)(2.0 * 44100 / N); b++) {
        double t = b * N / 44100.0;
        if (b == 0)                              api->on_midi(inst, on_a, 3, 0);
        if (t >= 0.5 && t - N/44100.0 < 0.5)     api->on_midi(inst, on_b, 3, 0);
        if (t >= 1.0 && t - N/44100.0 < 1.0)     api->on_midi(inst, off_b, 3, 0);
        if (t >= 1.5 && t - N/44100.0 < 1.5)     api->on_midi(inst, off_a, 3, 0);
        if (rf) { rf(inst, il, N); fwrite(il, sizeof(float), N*2, stdout); }
        else { api->render_block(inst, o, N);
               for (int i = 0; i < N*2; i++) { float f = o[i]/32768.0f; fwrite(&f, 4, 1, stdout); } }
    }
    return 0;
}
