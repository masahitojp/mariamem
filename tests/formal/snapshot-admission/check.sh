#!/bin/sh
set -eu
jar=${1:?usage: sh check.sh /absolute/path/to/tla2tools.jar}
cd "$(dirname "$0")"
scratch=$(mktemp -d)
trap 'rm -rf "$scratch"' EXIT
cp SnapshotAdmission.tla "$scratch/"
cd "$scratch"

for design in MutexHeld SnapSlot; do
    cat > SnapshotAdmission.cfg <<CONFIG
SPECIFICATION Spec
CONSTANT Design = "$design"
INVARIANT TypeOK
INVARIANT SingleBackendCapture
INVARIANT SingleOwner
INVARIANT CanceledNeverOwns
INVARIANT BusyPreservesOpenDB
INVARIANT NoCloseDuringBackendCapture
PROPERTY CanceledWaiterProgress
CHECK_DEADLOCK FALSE
CONFIG
    status=0
    java -XX:+UseParallelGC -cp "$jar" tlc2.TLC -workers 1 -metadir "states-$design" SnapshotAdmission.tla > "$design.log" 2>&1 || status=$?
    printf '\n=== Design=%s ===\n' "$design"
    cat "$design.log"
    if [ "$design" = MutexHeld ]; then
        [ "$status" -ne 0 ]
        grep -Fq 'Temporal property CanceledWaiterProgress was violated.' "$design.log"
    else
        [ "$status" -eq 0 ]
        grep -Fq 'Model checking completed. No error has been found.' "$design.log"
    fi
done
