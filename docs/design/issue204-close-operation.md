# Shared Close operation (#204)

Implementation baseline: `85bdb4573451388289d8eda6450c35157372dcba`
(#203's isolated ownership candidate). Main has not adopted #203. This is a
connected experiment candidate, not main integration or product acceptance.
Read issue203-cleanup-ownership.md for resource ownership/retry constraints.

## State and ownership

Under Database.mu, beginCloseLocked records any pre-existing failure, marks the
DB closed and publishes one closeOperation. Only its actor calls initial backend
Close, removes temporary state and settles the lease. The caller's context is
not the actor's lifetime: shutdown uses the configured ShutdownTimeout, and
canceling one waiter cannot abandon the shared operation.

Close remains synchronous and idempotent. closeLocked temporarily releases mu
while waiting, then reacquires it for existing locked callers. watch also joins
this operation and still returns after cleanup attempt completion, preserving
its existing deterministic contract. A watcher arriving after intentional Close
does not turn normal termination into ErrUnusable. A prior unexpected failure
is retained independently of the final Close error.

Live's private retry path first joins an in-flight initial operation. After its
completion, Live retains its existing explicit retry semantics. No Reset or
public Live contract is redesigned.

The operation has three distinct observations:

- stopped: backend stopped confirmation or stop failure; stopErr is published
  before this channel closes;
- done: initial cleanup attempt result; Wait(ctx) returns this immutable result
  or the individual waiter's cancellation;
- Disposed(): done, all retained cleanup owners complete, and server disposal
  confirmed. Later reclamation can change this answer without rewriting err.

Normal pending cleanup keeps the existing Fork lease occupied without marking
the pool blocked. Actual retained cleanup debt still uses the existing failed
cleanup admission rules. The parent Snapshot may close while its child cleans
up; this does not drain or settle that child. Existing children remain owners.

## Backend handoff for #205

The internal host Server may implement:

```
CloseWithStopped(ctx context.Context, notify func(error)) error
```

It must stop admission, join guest root/all workers, close peer transport and
join the reader and host session workers before calling notify(nil). Notification
of a stop error is not permission to free a still-running guest. The method
continues the owned cleanup and returns its final attempt result. Existing
Server.Close must retain its synchronous contract. Database tolerates duplicate
notifications by accepting the first only; the backend should notify once.

Until #205 implements this boundary, Database calls ordinary backend.Close and
publishes stopped after that returns. A failed return is reported as a stop
error, never as a successful early boundary. Consequently this candidate alone
does not make actual guest cleanup asynchronous. The staged backend tests prove
the consumer side; #205 and #206 must validate the real producer/connection.

stopForCleanup(ctx) returns the common operation after stopped. On cancellation
after initiation it returns the operation and cancellation error; recovery stays
owned. An already-canceled request does not initiate a new operation.

## Verification scope

Controlled tests exercise watcher-first and user-first shutdown, concurrent and
repeated Close, canceled waits, new request rejection, late disposal without
rewriting a failed result, occupied/available capacity and parent Snapshot.Close
while a next Fork is waiting. The staged backend has independently gated stopped
and release events. This is not real guest early-stop verification.

Existing Database, fixture and Live tests remain enabled. The original runtime
exit test caught an initial watcher regression; watch's synchronous completion
was restored rather than changing that oracle. Public source includes only the
two explicit new root Go filenames. Generated runtime/layout/license inputs are
unchanged from #203.

Reproduce with Go1.26.10:

```
go test -p 1 . ./mariamemtest ./internal/forklimit ./internal/disposal
go test -race -p 1 -count=1 .
```

Run scripts/check_public.py, verify_generated_runtime.py,
update_evidence_records.py --check and git diff --check as boundary checks.
No performance result, opposite-platform qualification, public async API or
release is claimed.
