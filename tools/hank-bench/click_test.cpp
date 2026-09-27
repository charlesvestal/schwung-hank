/* Measures the two discontinuities the preset corpus cannot see.
 *
 * The corpus renders one note with every param set before it starts, so it is
 * blind to both by construction: it never steals a voice and it never moves a
 * control while sounding.
 *
 * SELF-NORMALISING, because every cross-configuration control tried here was
 * unfair. Comparing a stealing patch against a sustained chord charges note
 * ATTACKS to stealing; comparing against the same notes with more voices
 * changes the summed level instead. So each event is scored against the same
 * signal moments before it: the step at the known event sample, over the median
 * step of the preceding window. A continuous event scores ~1.
 */
#include "hank_engine.h"
#include <cstdio>
#include <cstdlib>
#include <cmath>
using namespace hank;

static int cmpf(const void *a, const void *b) {
    float x = *(const float *)a, y = *(const float *)b;
    return x < y ? -1 : (x > y ? 1 : 0);
}
/* THE MAXIMUM of the preceding window, not the median and not a percentile.
 *
 * The question a click test asks is "is this step bigger than steps this signal
 * ALREADY takes". Anything below the top of the recent range is, by definition,
 * a step the waveform was going to take anyway.
 *
 * A bright FM waveform's median slope is small -- most samples sit on the flat
 * parts of the cycle -- while the steepest legitimate samples are many times
 * that. Scoring against the median, and then against p95, both reported a
 * discontinuity at a steal where a sample-by-sample dump showed the output
 * perfectly continuous: the event simply landed on a steep part of the cycle. */
static float maxStepWin(const float *x, int from, int n) {
    static float t[4096];
    for (int i = 0; i < n; i++) t[i] = fabsf(x[from + i] - x[from + i - 1]);
    qsort(t, n, sizeof(float), cmpf);
    return t[n - 1];
}

int main() {
    const int BLK = 128;
    static float buf[BLK * 2];
    static float hist[BLK * 64];
    int fails = 0;

    /* ---- 1. voice stealing -------------------------------------------- */
    {
        Engine e; Params &p = e.params();
        p.voice_count = 2; p.res = 0.8f; p.cutoff = 0.35f; p.mix = 0.0f;
        p.op2_level = 0.6f; p.op1_s = 1.0f; p.op2_s = 1.0f; p.volume = 0.5f;
        e.noteOn(60, 100); e.noteOn(64, 100);
        for (int b = 0; b < 40; b++) e.render(buf, BLK);      /* settle */
        int hn = 0, stealAt = -1;
        for (int b = 0; b < 20; b++) {
            /* THE STEALING NOTE IS ADJACENT IN PITCH, deliberately. A note
             * seven semitones up has a 1.5x higher frequency and therefore a
             * legitimately 1.5x steeper waveform, which scores as a 1.5x
             * "discontinuity" that no fix can ever remove. Stealing with a
             * neighbouring pitch holds the slope constant so the only thing
             * left to measure is the discontinuity itself. */
            if (b == 5) { e.noteOn(61, 100); stealAt = hn; }  /* 3rd note steals */
            e.render(buf, BLK);
            for (int i = 0; i < BLK; i++) hist[hn++] = buf[i * 2];
        }
        const float med = maxStepWin(hist, stealAt - 256, 255);
        float peak = 0.0f;
        for (int i = stealAt; i < stealAt + 4; i++) {
            float d = fabsf(hist[i] - hist[i - 1]); if (d > peak) peak = d;
        }
        const float ratio = med > 0 ? peak / med : 0.0f;
        printf("steal      step at event %.6f vs preceding max %.6f  -> %.2fx\n",
               peak, med, ratio);
        if (ratio > 1.2f) { printf("  FAIL: discontinuity at the steal\n"); fails++; }
    }

    /* ---- 2. parameter step while sounding ------------------------------ */
    {
        Engine e; Params &p = e.params();
        p.voice_count = 4; p.op2_level = 0.5f; p.op1_s = 1.0f; p.op2_s = 1.0f;
        p.volume = 0.2f; p.cutoff = 0.3f;
        e.noteOn(60, 100);
        for (int b = 0; b < 60; b++) e.render(buf, BLK);      /* settle */
        int hn = 0, jumpAt = -1;
        for (int b = 0; b < 20; b++) {
            if (b == 8) { p.volume = 0.9f; jumpAt = hn; }     /* a hard knob jump */
            e.render(buf, BLK);
            for (int i = 0; i < BLK; i++) hist[hn++] = buf[i * 2];
        }
        const float med = maxStepWin(hist, jumpAt - 256, 255);
        float peak = 0.0f;
        for (int i = jumpAt; i < jumpAt + 4; i++) {
            float d = fabsf(hist[i] - hist[i - 1]); if (d > peak) peak = d;
        }
        const float ratio = med > 0 ? peak / med : 0.0f;
        printf("param jump step at event %.6f vs preceding max %.6f  -> %.2fx\n",
               peak, med, ratio);
        if (ratio > 1.2f) { printf("  FAIL: volume steps instead of slewing\n"); fails++; }
    }

    printf(fails ? "FAILURES: %d\n" : "all clean\n", fails);
    return fails ? 1 : 0;
}
