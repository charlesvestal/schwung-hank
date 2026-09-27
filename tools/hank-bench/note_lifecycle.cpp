/* Two things a note must do: stop when released, and stop when the sound is
 * replaced.
 *
 * 1. DECAY AT MAXIMUM MUST STILL RELEASE. The envelope carried an "infinite
 *    release at max" flag from when release was its own raw parameter. DECAY
 *    drives the release now and it is a macro, so the top of an ordinary knob
 *    was a note that could not be stopped by note-off, all-notes-off, or a new
 *    preset. Reported by a user.
 *
 * 2. A PRESET LOAD MUST STOP WHAT IS SOUNDING, and without a click -- a mute
 *    is a click, which is the defect this module has been bitten by twice.
 */
#include <cstdio>
#include <cstdint>
#include <cstring>
#include <cmath>
#include <dlfcn.h>
#include "../../src/dsp/plugin_api_v1.h"

static plugin_api_v2_t *api; static void *inst;
typedef void (*rf_t)(void *, float *, int);
static rf_t rf;
static const int N = 128;

/* Render `secs`, return peak, and record the largest sample-to-sample jump. */
static double run(double secs, double *worstJump) {
    float il[256]; double pk = 0.0; float prev = 0.0f; bool have = false;
    if (worstJump) *worstJump = 0.0;
    for (int b = 0; b < (int)(secs * 44100 / N); b++) {
        rf(inst, il, N);
        for (int i = 0; i < N * 2; i += 2) {
            double a = fabs((double)il[i]); if (a > pk) pk = a;
            if (have && worstJump) {
                double d = fabs((double)il[i] - (double)prev);
                if (d > *worstJump) *worstJump = d;
            }
            prev = il[i]; have = true;
        }
    }
    return pk;
}
static double db(double v) { return 20.0 * log10(v > 0 ? v : 1e-12); }

int main(int argc, char **argv) {
    if (argc < 2) return 2;
    void *h = dlopen(argv[1], RTLD_NOW); if (!h) { fprintf(stderr, "%s\n", dlerror()); return 2; }
    typedef plugin_api_v2_t *(*init_t)(const host_api_v1_t *);
    api = ((init_t)dlsym(h, "move_plugin_init_v2"))(nullptr);
    inst = api->create_instance(".", nullptr);
    rf = (rf_t)dlsym(h, "hank_bench_render_float");
    if (!rf) { fprintf(stderr, "no float render entry point\n"); return 2; }
    int fails = 0;

    /* ---- 1. decay at maximum ------------------------------------------- */
    api->set_param(inst, "decay", "1.0");
    api->set_param(inst, "sustain", "0.9");
    api->set_param(inst, "attack", "0.0");
    uint8_t on[3]  = { 0x90, 52, 100 };
    uint8_t off[3] = { 0x80, 52, 0 };
    api->on_midi(inst, on, 3, 0);
    run(0.3, nullptr);
    api->on_midi(inst, off, 3, 0);
    /* PEAK OVER A TAIL WINDOW, not over the whole run. Measuring the peak from
     * the moment of release includes the release itself, so a perfectly
     * healthy envelope reports full level and the test fails on working code
     * -- which is exactly what the first version of it did. */
    run(12.0, nullptr);
    double after = run(0.5, nullptr);
    printf("  decay=1.0, note released, 12 s later: peak %.1f dBFS\n", db(after));
    if (db(after) > -80.0) {
        printf("  FAIL: the note is still sounding -- it cannot be turned off\n");
        fails++;
    }

    /* ---- 2. a preset load stops what is sounding, quietly ---------------- */
    api->set_param(inst, "preset", "18");       /* soft pad, long */
    api->on_midi(inst, on, 3, 0);
    double pk = run(0.5, nullptr);
    api->set_param(inst, "preset", "11");       /* big bell: a different sound */
    double jump = 0.0;
    run(0.05, &jump);                           /* the ~8 ms stop happens in here */
    double tail = run(0.20, nullptr);           /* well inside the pad-s own decay */
    printf("  sounding %.1f dBFS -> 0.25 s after a preset load: %.1f dBFS, largest jump %.5f\n",
           db(pk), db(tail), jump);
    if (db(tail) > db(pk) - 30.0) {
        printf("  FAIL: the previous sound is still ringing after the preset changed\n");
        fails++;
    }
    if (jump > 0.05) {
        printf("  FAIL: the stop has an edge in it (%.5f) -- that is a click, not a release\n", jump);
        fails++;
    }

    if (fails) return 1;
    printf("  PASS: a note stops when released and when the preset changes, without a click\n");
    return 0;
}
