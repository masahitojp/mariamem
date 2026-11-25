#!/bin/sh
set -eu
jar=${1:?usage: sh check.sh /absolute/path/to/tla2tools.jar}
cd "$(dirname "$0")"
scratch=$(mktemp -d)
trap 'rm -rf "$scratch"' EXIT
cp ThreadList.tla "$scratch/"
cd "$scratch"

for fence in FALSE TRUE; do
    cat > ThreadList.cfg <<CONFIG
SPECIFICATION Spec
CONSTANT Fence = $fence
INVARIANT NoStrandedWaiter
PROPERTY WaiterProgress
CHECK_DEADLOCK FALSE
CONFIG
    status=0
    java -XX:+UseParallelGC -cp "$jar" tlc2.TLC -workers 1 -metadir "states-$fence" ThreadList.tla > "$fence.log" 2>&1 || status=$?
    printf '\n=== Fence=%s ===\n' "$fence"
    cat "$fence.log"
    if [ "$fence" = FALSE ]; then
        [ "$status" -ne 0 ]
        grep -Fq 'Invariant NoStrandedWaiter is violated.' "$fence.log"
    else
        [ "$status" -eq 0 ]
        grep -Fq 'Model checking completed. No error has been found.' "$fence.log"
    fi
done
