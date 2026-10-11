#!/bin/sh
set -eu
REPOSITORY=/Users/masahito/src/mysqlmem/publish/mariamem
WORK=$REPOSITORY/build/experiment-work/v05-stable-guest-feasibility
SOURCE=$WORK/worktree
exec docker run --rm --init --name mariamem-v05-stable-guest -v "$REPOSITORY:$REPOSITORY:ro" -v "$WORK/temp:$WORK/temp" -v "$WORK/temp/linux-root:/root" -v "$WORK/temp/linux-work:/work" -v "$WORK/temp/builder-build:$SOURCE/build" -v "$WORK/evidence:/evidence" -e MARIAMEM_PHASE_TRACE=/evidence/guest-phases.jsonl -w "$SOURCE" mariamem-wasix-build:0.4.7 python3 scripts/build_generated_guest.py --development-output "$WORK/temp/dev-guest"
