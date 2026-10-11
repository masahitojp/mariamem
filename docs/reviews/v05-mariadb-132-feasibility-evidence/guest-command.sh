#!/bin/sh
set -eu
REPOSITORY=/workspace/mariamem
WORK=$REPOSITORY/build/experiment-work/v05-mariadb-132-feasibility
SOURCE=$WORK/worktree
exec docker run --rm --init --memory=6g --name mariamem-v05-preview-guest -v "$REPOSITORY:$REPOSITORY:ro" -v "$WORK/temp:$WORK/temp" -v "$WORK/temp/linux-root:/root" -v "$WORK/temp/linux-work:/work" -v "$WORK/temp/builder-build:$SOURCE/build" -v "$WORK/evidence:/evidence" -e MARIAMEM_PHASE_TRACE=/evidence/guest-phases.jsonl -w "$SOURCE" mariamem-wasix-build:0.4.7 python3 scripts/build_generated_guest.py --development-output "$WORK/temp/dev-guest"
