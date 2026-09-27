#!/usr/bin/env bash
# Deploy Hank to a Move on the network. Sound generators need no restart.
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DEVICE="${MOVE_HOST:-ableton@move.local}"
DEST="/data/UserData/schwung/modules/sound_generators/hank"

[ -d "$REPO_ROOT/dist/hank" ] || { echo "run ./scripts/build.sh first"; exit 1; }

echo "Installing to $DEVICE:$DEST"
ssh "$DEVICE" "mkdir -p $DEST"
scp -q "$REPO_ROOT"/dist/hank/* "$DEVICE:$DEST/"
echo "Done. Re-select the module in the Signal Chain to pick up a new dsp.so."
