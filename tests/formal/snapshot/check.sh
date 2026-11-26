#!/bin/sh
set -eu

jar=${1:?usage: sh check.sh /absolute/path/to/tla2tools.jar}
cd "$(dirname "$0")"
scratch=$(mktemp -d)
trap 'rm -rf "$scratch"' EXIT
cp Snapshot.tla SharedTransport.tla FailureCleanup.tla "$scratch/"
cd "$scratch"

run() {
    name=$1 scenario=$2 policy=$3 schedule=$4 interrupt=$5
    property=$6 expected=$7
    cat > Case.cfg <<CONFIG
SPECIFICATION Spec
CONSTANTS
    Scenario = "$scenario"
    Policy = "$policy"
    Schedule = "$schedule"
    Interrupt = "$interrupt"
INVARIANT Ownership
$property
CHECK_DEADLOCK FALSE
CONFIG
    check_model Snapshot "$name" "$expected"
}

check_model() {
    module=$1 name=$2 expected=$3
    status=0
    java -XX:+UseParallelGC -cp "$jar" tlc2.TLC -workers 1 -metadir "states-$name" \
        -config Case.cfg "$module.tla" > "$name.log" 2>&1 || status=$?
    if [ "$expected" = pass ]; then
        matched='Model checking completed. No error has been found.'
        [ "$status" -eq 0 ] || { cat "$name.log"; exit 1; }
    else
        matched=$expected
        [ "$status" -ne 0 ] || { cat "$name.log"; exit 1; }
    fi
    if ! grep -Fq "$matched" "$name.log"; then cat "$name.log"; exit 1; fi
    printf '\n=== %s ===\n' "$name"
    if [ "$expected" = pass ]; then grep -E '^Model checking completed|^[0-9]+ states generated' "$name.log"
    else sed -n '/^Error:/,/states generated/p' "$name.log"
    fi
}

run old-update update old timely none 'INVARIANT NoFalseBusy' 'Invariant NoFalseBusy is violated'
run fixed-timely update bounded timely none 'PROPERTY Succeeds' pass
run fixed-late update bounded late-write none 'INVARIANT NoFalseBusy' 'Invariant NoFalseBusy is violated'
run unread rows bounded timely none 'PROPERTIES UnreadReturns RowsCanDrain' pass
run unread-without-expiry rows no-expiry timely none 'PROPERTY UnreadReturns' 'Temporal property UnreadReturns was violated.'
run ack-stalled update bounded ack-stall none 'PROPERTY Returns' 'Temporal property Returns was violated.'
run fence-stalled update bounded fence-stall none 'PROPERTY Returns' 'Temporal property Returns was violated.'
run cancel-ack update bounded ack-stall cancel-before-send 'PROPERTY Returns' pass
run cancel-fence update bounded fence-stall cancel-fence 'PROPERTY Returns' pass
run disconnect-fence update bounded fence-stall disconnect-fence 'PROPERTY Returns' pass

run_transport() {
    name=$1 coupled=$2 property=$3 expected=$4
    cat > Case.cfg <<CONFIG
SPECIFICATION Spec
CONSTANT WaitForClientInHostReader = $coupled
$property
CHECK_DEADLOCK FALSE
CONFIG
    check_model SharedTransport "$name" "$expected"
}

run_transport independent-reader FALSE 'PROPERTIES CaptureReturns PeerReturns' pass
run_transport coupled-reader-capture TRUE 'PROPERTY CaptureReturns' 'Temporal property CaptureReturns was violated.'
run_transport coupled-reader-peer TRUE 'PROPERTY PeerReturns' 'Temporal property PeerReturns was violated.'

run_cleanup() {
    name=$1 early=$2 finishes=$3 expected=$4
    cat > Case.cfg <<CONFIG
SPECIFICATION Spec
CONSTANTS
    ReturnBeforeJoin = $early
    GuestCanFinish = $finishes
INVARIANT Ownership
PROPERTIES ReturnsOnFailure DisposesAfterJoin
CHECK_DEADLOCK FALSE
CONFIG
    check_model FailureCleanup "$name" "$expected"
}

run_cleanup failure-old-stalled FALSE FALSE 'Temporal property ReturnsOnFailure was violated.'
run_cleanup failure-returns-stalled TRUE FALSE pass
run_cleanup failure-disposes-after-join TRUE TRUE pass
