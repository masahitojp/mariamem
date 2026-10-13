#!/bin/sh
set -eu
REPOSITORY=$(git rev-parse --path-format=absolute --git-common-dir)
REPOSITORY=${REPOSITORY%/.git}
SOURCE=$(pwd -P)
TASK=$(cd .. && pwd -P)
exec docker run --rm --init --name mariamem-v050-ad-guest \
 -v "$REPOSITORY:$REPOSITORY:ro" \
 -v "$TASK/temp:$TASK/temp" -v "$TASK/temp/linux-root:/root" \
 -v "$TASK/temp/linux-work:/work" -v "$TASK/temp/builder-build:$SOURCE/build" \
 -v "$SOURCE/build/downloads:$SOURCE/build/downloads" \
 -v "$TASK/evidence:/evidence" -e MARIAMEM_PHASE_TRACE=/evidence/guest-phases.jsonl \
 -w "$SOURCE" mariamem-wasix-build:0.4.7 python3 scripts/build_generated_guest.py
