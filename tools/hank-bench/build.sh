#!/usr/bin/env bash
# Build the host-native measurement binaries.
#
# These were built ad hoc for a long time, which is exactly how a stale
# dsp_native.so gets measured and reported as a result. ExtFS has 1-second
# mtime granularity, so the objects are REMOVED first rather than trusted to
# look out of date, and every compile gates the next on its own exit status.
set -euo pipefail
cd "$(dirname "$0")/../.."
mkdir -p build
CXX=${CXX:-clang++}
FLAGS="-O2 -std=c++14 -ffast-math -Isrc/dsp"

rm -f build/dsp_native.so build/hank_render build/curve_check
$CXX $FLAGS -shared -fPIC src/dsp/hank_engine.cpp tools/hank-bench/bench_plugin.cpp \
     -o build/dsp_native.so
$CXX $FLAGS tools/hank-bench/hank_render.cpp -o build/hank_render
$CXX $FLAGS tools/hank-bench/mono_test.cpp -o build/mono_test
$CXX $FLAGS tools/hank-bench/state_recall.cpp -o build/state_recall
$CXX $FLAGS tools/hank-bench/note_lifecycle.cpp -o build/note_lifecycle
$CXX $FLAGS tools/hank-bench/curve_check.cpp src/dsp/hank_engine.cpp -o build/curve_check
test -s build/dsp_native.so && test -x build/hank_render
echo "bench binaries rebuilt: $(date '+%H:%M:%S')"
