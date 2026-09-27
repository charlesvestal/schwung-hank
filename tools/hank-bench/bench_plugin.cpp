/* Measurement-only wrapper. The deployed plugin retains its int16 ABI. */
#include "../../src/dsp/hank_plugin.cpp"

extern "C" void hank_bench_render_float(void *instance, float *out, int frames) {
    static_cast<Instance *>(instance)->engine.render(out, frames);
}
