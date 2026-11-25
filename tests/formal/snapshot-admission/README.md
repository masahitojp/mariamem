# Snapshot admission and cancellation

This model checks the public `Database.Snapshot` admission and cancellation state transitions for [mariamem #255](https://github.com/masahitojp/mariamem/issues/255). It has two concurrent `Snapshot` callers and a concurrent `Close` request.

| Model event | Runtime operation |
| --- | --- |
| `StartOrEnter` | Acquires `db.mu`, checks `invalidLocked` / `closed` / `closing` / `ctx.Err()`, and either claims `snapDone` to call the backend without holding `db.mu` or parks as a waiter. |
| `WaitCancel` | Under `SnapSlot`, a waiting caller observes `<-ctx.Done()` without holding `db.mu` and returns immediately without calling the backend. |
| `WaitWake` | After `snapDone` closes, a waiting caller re-acquires `db.mu` and re-checks state and `ctx.Err()`. |
| `BackendFinishConsume` / `BackendFinishBusy` | The leading backend `SnapshotHeap`/`SnapshotKeep` completes either consuming the DB or rejecting with a precondition error (leaving the DB open), then clears and closes `snapDone`. |
| `RequestClose` / `CompleteDeferredClose` | `Close()` defers backend teardown until an in-flight `snapDone` closes, then skips `server.Close` if the leading snapshot already consumed the DB. |

With `Design = "MutexHeld"`, TLC finds a counter-example violating `CanceledWaiterProgress`: a follower whose context expires while a leader stays in the backend cannot return. With `Design = "SnapSlot"`, TLC verifies all five safety invariants (`SingleBackendCapture`, `SingleOwner`, `CanceledNeverOwns`, `BusyPreservesOpenDB`, `NoCloseDuringBackendCapture`) and `CanceledWaiterProgress` with zero errors.

## Run

Use the [official TLC v1.8.0 jar](https://github.com/tlaplus/tlaplus/releases/tag/v1.8.0) with Java 11 or later. The tested jar SHA-256 is `fdffef247f563ef6edbfd44958d2a82db79e7564e07cb673262d896353fa6713`.

```sh
sh tests/formal/snapshot-admission/check.sh /absolute/path/to/tla2tools.jar
```

The script succeeds when `MutexHeld` reports the expected liveness violation and `SnapSlot` passes all invariants and progress checks.
