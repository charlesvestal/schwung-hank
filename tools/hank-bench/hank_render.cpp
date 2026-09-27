/* Render notes from a built Hank dsp.so -> interleaved stereo f32 on stdout.
 *
 * Every measurement in this directory goes through here, so note timing,
 * pre-roll and velocity are decided in ONE place: a curve fitted against a
 * harness that varies is fitted to the harness. argv[4] takes a comma-
 * separated list of keys, because a level measured on a single note cannot
 * see what voices summing does to the peak. */
#include "../../src/dsp/plugin_api_v1.h"
#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

static host_api_v1_t g_host;

int main(int argc, char **argv) {
    if (argc < 5) {
        fprintf(stderr, "usage: hank_render <dsp.so> <secs> <gate_secs> <key> [key=value ...]\n");
        return 2;
    }
    const char *so = argv[1];
    double secs = atof(argv[2]), gate = atof(argv[3]);
    int key = atoi(argv[4]);
    const double preroll = getenv("BENCH_PREROLL") ? atof(getenv("BENCH_PREROLL")) : 0;
    const int velocity = getenv("BENCH_VELOCITY") ? atoi(getenv("BENCH_VELOCITY")) : 100;
    if (!isfinite(preroll) || preroll < 0 || preroll > 10 || velocity < 1 || velocity > 127) return 2;

    void *lib = dlopen(so, RTLD_NOW | RTLD_LOCAL);
    if (!lib) { fprintf(stderr, "dlopen: %s\n", dlerror()); return 1; }
    typedef plugin_api_v2_t *(*init_fn)(const host_api_v1_t *);
    init_fn init = (init_fn)dlsym(lib, MOVE_PLUGIN_INIT_V2_SYMBOL);
    if (!init) { fprintf(stderr, "no entry\n"); return 1; }
    typedef void (*float_render_fn)(void *, float *, int);
    float_render_fn render_float = nullptr;
    if (getenv("BENCH_FLOAT") && atoi(getenv("BENCH_FLOAT"))) {
        render_float = (float_render_fn)dlsym(lib, "hank_bench_render_float");
        if (!render_float) { fprintf(stderr, "float mode requires bench library\n"); return 1; }
    }
    memset(&g_host, 0, sizeof g_host);
    plugin_api_v2_t *api = init(&g_host);
    void *inst = api->create_instance(".", 0);
    if (!inst) { fprintf(stderr, "no instance\n"); return 1; }

    /* Known state first: without this, anything the caller does not set keeps
     * the value it had in factory preset 0. */
    api->set_param(inst, "init", "1");

    for (int a = 5; a < argc; a++) {
        char *eq = strchr(argv[a], '=');
        if (!eq) continue;
        *eq = 0;
        api->set_param(inst, argv[a], eq + 1);
    }

    /* A CHORD, NOT ONLY A NOTE. Every level measured here was measured on one
     * note, so nothing in the bench could see what voices summing does to the
     * peak -- which is the case a player hits first. argv[4] takes a
     * comma-separated list. */
    int keys[16], nkeys = 0;
    for (const char *q = argv[4]; *q && nkeys < 16; ) {
        keys[nkeys++] = atoi(q);
        const char *c = strchr(q, ',');
        if (!c) break;
        q = c + 1;
    }
    if (nkeys == 0) { keys[0] = key; nkeys = 1; }

    const double SR = 44100.0; const int N = 128;
    int blocks = (int)(secs * SR / N), gb = (int)(gate * SR / N);
    int16_t out[256];
    float il[256];
    for (int b = 0; b < (int)(preroll * SR / N); b++) {
        if (render_float) render_float(inst, il, N);
        else api->render_block(inst, out, N);
    }
    for (int k = 0; k < nkeys; k++) {
        uint8_t on[3] = { 0x90, (uint8_t)keys[k], (uint8_t)velocity };
        api->on_midi(inst, on, 3, 0);
    }
    for (int b = 0; b < blocks; b++) {
        if (b == gb) for (int k = 0; k < nkeys; k++) {
            uint8_t off[3] = { 0x80, (uint8_t)keys[k], 0 };
            api->on_midi(inst, off, 3, 0);
        }
        if (render_float) render_float(inst, il, N);
        else {
            api->render_block(inst, out, N);
            for (int j = 0; j < N * 2; j++) il[j] = out[j] / 32768.0f;
        }
        fwrite(il, sizeof(float), N * 2, stdout);
    }
    api->destroy_instance(inst);
    return 0;
}
