# Snapshot protocol model checks

Run the bounded TLA+ models with the official TLC v1.8.0 release and Java 11 or later.

```sh
sh tests/formal/snapshot/check.sh /absolute/path/to/tla2tools.jar
```

The run used [tla2tools.jar from v1.8.0](https://github.com/tlaplus/tlaplus/releases/tag/v1.8.0), SHA-256
`fdffef247f563ef6edbfd44958d2a82db79e7564e07cb673262d896353fa6713`.
Development checks run the script for changes to the model and Snapshot
transport boundary, or when the changed paths cannot be determined.
The script checks for specific expected violations in the counterexample cases.
It returns a failure if TLC reports another error or misses an expected violation.

- `Snapshot.tla` covers one connection and one Snapshot. It distinguishes a client
  reading the final OK from the host recording the write and the guest processing
  the ACK. The old busy policy should produce a false busy. The bounded policy
  succeeds under timely progress and lets the caller recover from unread rows.
  The cancellation cases check whether the source can still be used.
- `SharedTransport.tla` starts with one connection's output window full. It
  requires the other connection to complete SQL, retire and complete SQL again
  on a replacement. It also requires the capture rejection to reach the caller
  while the first connection still has unread output. A hypothetical host reader
  that waits for the client's socket write makes both progress properties fail.

In the host, `readLoop` queues SQL output in `session.pushOutput`. A separate
session goroutine writes it to the client and sends the ACK. The guest's control
loop can reject capture while the SQL worker waits for output credit. The models
treat these operations as discrete events and assume weak fairness for enabled
work. They omit actual queue sizes, mutex interleavings, RPC durations and
post-acceptance shutdown. Permanent silence in the one-connection model is a
fault assumption. `SharedTransport.tla` models an orderly disconnect of the
other client. An abrupt disconnect during the stalled client's response is a
different path, where the guest can invalidate the instance.

The real-guest regression exercises a second connection, its orderly disconnect
and replacement, a non-consuming capture rejection, then a successful retry
and Fork after the first client drains its results.

```sh
go test -tags=integration -p 1 -count=1 -run '^TestSnapshotActualGuestBusyMultiResultStalledWriteAndTransactionActive$/^stalled_host_write_busy$' ./tests/gointegration
```

`FailureCleanup.tla` starts at the failure boundary shared by a lost fence
reply and a failure after stop acceptance. It separates failure detection,
returning the consuming error, guest completion and disposal. The old policy
cannot return if the guest never completes. The new policy can return with
a retained owner and can release resources only after completion. The model
assumes weak fairness for enabled host actions and checks eventual disposal
when guest completion is enabled. The Go tests exercise both failure points
and the public API's parent Fork lease.
