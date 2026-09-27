/* Apply a `state` blob to a SOUNDING voice, the way a snapshot recall does.
 *
 * Shift+Delete writes <prefix>:state for every position at once, under your
 * hands, while notes are ringing. Every parameter changes in one block. This
 * isolates the module: hold a note, swap the whole state mid-note, and report
 * the largest sample-to-sample jump against a control run that changes nothing.
 * If the module clicks here it is the module; if it does not, the click is
 * somewhere in the host that recall also touches.
 */
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <cstdint>
#include <cmath>
#include <dlfcn.h>
#include "../../src/dsp/plugin_api_v1.h"

int main(int argc, char **argv) {
    if (argc < 2) { fprintf(stderr, "usage: state_recall <dsp.so> [--control]\n"); return 2; }
    const bool control = (argc > 2 && strcmp(argv[2], "--control") == 0);
    void *h = dlopen(argv[1], RTLD_NOW); if (!h) { fprintf(stderr, "%s\n", dlerror()); return 2; }
    typedef plugin_api_v2_t *(*init_t)(const host_api_v1_t *);
    init_t init = (init_t)dlsym(h, "move_plugin_init_v2"); if (!init) return 2;
    plugin_api_v2_t *api = init(nullptr);
    void *inst = api->create_instance(".", nullptr); if (!inst) return 2;
    typedef void (*rf_t)(void *, float *, int);
    rf_t rf = (rf_t)dlsym(h, "hank_bench_render_float");
    if (!rf) { fprintf(stderr, "no float render entry point -- refusing to measure stack garbage\n"); return 2; }

    /* Capture two states far apart: a soft pad and a bright metallic patch. */
    char A[4096], B[4096];
    api->set_param(inst, "preset", argc > 3 ? argv[3] : "18");
    api->get_param(inst, "state", A, sizeof A);
    api->set_param(inst, "preset", argc > 4 ? argv[4] : "29");
    api->get_param(inst, "state", B, sizeof B);

    /* Start on A, hold a note, then slam B in mid-note. */
    api->set_param(inst, "state", A);
    api->set_param(inst, "sustain", "0.9");
    api->set_param(inst, "decay", "0.9");

    const int N = 128;
    float il[256];
    uint8_t on[3] = { 0x90, 52, 100 };
    api->on_midi(inst, on, 3, 0);

    double worst = 0.0; int worstBlock = -1; float prev = 0.0f; bool have = false;
    static double win[16]; static int winN = 16;
    const int swapBlock = (int)(0.8 * 44100 / N);
    for (int b = 0; b < (int)(1.6 * 44100 / N); b++) {
        if (b == swapBlock && !control) api->set_param(inst, "state", B);
        if (rf) rf(inst, il, N);
        double blockMax = 0.0;
        for (int i = 0; i < N * 2; i += 2) {
            if (have) {
                double d = fabs((double)il[i] - (double)prev);
                if (d > worst) { worst = d; worstBlock = b; }
                if (d > blockMax) blockMax = d;
            }
            prev = il[i]; have = true;
        }
        int rel = b - swapBlock;
        if (rel >= -2 && rel < 14) { if (blockMax > win[rel + 2]) win[rel + 2] = blockMax; }
    }
    for (int i = 0; i < winN; i++)
        printf("   block swap%+d  max jump %.6f\n", i - 2, win[i]);
    printf("%s: largest jump %.6f (%.1f dBFS) at block %d (swap at %d, %+d blocks)\n",
           control ? "control (no recall)" : "state recall ",
           worst, 20.0 * log10(worst > 0 ? worst : 1e-9), worstBlock, swapBlock,
           worstBlock - swapBlock);
    return 0;
}
