#!/usr/bin/env bash
# Build Hank for Move (ARM64). Uses Docker to cross-compile unless
# CROSS_PREFIX is already set (e.g. on a native ARM Linux box).
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
# ITS OWN IMAGE, not the shared move-anything-builder: that one already exists
# on most machines WITHOUT python3, and docker only builds an image when it is
# missing -- so a shared name silently runs the stale image and the codegen
# step dies with "python3: command not found".
IMAGE_NAME="hank-builder"

if [ -z "${CROSS_PREFIX:-}" ] && [ ! -f "/.dockerenv" ]; then
    echo "=== Hank Build (via Docker) ==="
    if ! docker image inspect "$IMAGE_NAME" &>/dev/null; then
        echo "Building Docker image (first time only)..."
        docker build -t "$IMAGE_NAME" -f "$SCRIPT_DIR/Dockerfile" "$REPO_ROOT"
    fi
    docker run --rm -v "$REPO_ROOT:/build" -u "$(id -u):$(id -g)" -w /build \
        "$IMAGE_NAME" ./scripts/build.sh
    exit 0
fi

CROSS_PREFIX="${CROSS_PREFIX:-aarch64-linux-gnu-}"
cd "$REPO_ROOT"

echo "=== Building Hank ==="
echo "Cross prefix: $CROSS_PREFIX"

# GENERATED SOURCES FIRST, and this order is load-bearing: module.json and the
# preset table are both generated, so building without regenerating would ship
# a binary that disagrees with its own contract.
#
# Both outputs are committed, so a toolchain without python3 can still build --
# but it must not do so SILENTLY, or a stale contract ships unnoticed.
if command -v python3 >/dev/null 2>&1; then
    python3 tools/gen_module_json.py
    python3 presets/gen_presets.py
else
    echo "WARNING: no python3 -- using the COMMITTED module.json and hank_presets.h."
    echo "         Re-run with python3 available if you changed either generator."
    for f in src/module.json src/dsp/hank_presets.h; do
        [ -f "$f" ] || { echo "ERROR: $f missing and cannot be generated"; exit 1; }
    done
fi

mkdir -p build dist/hank

echo "Compiling DSP..."
${CROSS_PREFIX}g++ -O3 -shared -fPIC -std=c++14 \
    -ffast-math -fno-gnu-unique \
    src/dsp/hank_plugin.cpp \
    src/dsp/hank_engine.cpp \
    -o build/dsp.so \
    -Isrc/dsp -lm -Wl,--exclude-libs,ALL

# `cat` rather than `cp`: ExtFS + Docker bind mounts hit deallocation errors on
# copy, which is a known trap in this fleet's build scripts.
echo "Packaging..."
cat src/module.json    > dist/hank/module.json
cat src/help.json      > dist/hank/help.json
cat src/ui.js          > dist/hank/ui.js
cat src/ui/canvas.js   > dist/hank/canvas.js
cat build/dsp.so       > dist/hank/dsp.so
chmod +x dist/hank/dsp.so

cd dist
tar -czf hank-module.tar.gz hank/
cd ..

echo ""
echo "=== Build Complete ==="
file build/dsp.so
echo "Tarball: dist/hank-module.tar.gz"
