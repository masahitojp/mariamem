#!/bin/sh
set -eu
SOURCE=$(pwd -P)
TASK=$(cd .. && pwd -P)
REPOSITORY=$(git rev-parse --path-format=absolute --git-common-dir)
REPOSITORY=${REPOSITORY%/.git}
exec docker run --rm --init --name mariamem-v06-multi-final-guest \
 -v "$REPOSITORY:$REPOSITORY:ro" \
 -v "$TASK/temp:$TASK/temp" -v "$TASK/temp/final-linux-root:/root" \
 -v "$TASK/temp/final-linux-work:/work" -v "$TASK/temp/final-builder-build:$SOURCE/build" \
 -v "$SOURCE/build/downloads:$SOURCE/build/downloads" \
 -v "$TASK/evidence:$TASK/evidence" -e MARIAMEM_PHASE_TRACE="$TASK/evidence/final-guest-phases.jsonl" \
 -e GIT_CONFIG_COUNT=1 -e GIT_CONFIG_KEY_0=safe.directory -e GIT_CONFIG_VALUE_0='*' \
 -w "$SOURCE" sha256:3ded805d8dcae3ffdf39515c3f0540b27b695719570903594452f8787abe570f \
 python3 scripts/build_generated_guest.py --development-output "$TASK/temp/final-guest"
