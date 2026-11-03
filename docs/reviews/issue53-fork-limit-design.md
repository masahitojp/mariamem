# Issue #53 — explicit Snapshot Fork capacity

Status: design proposal, 2026-11-03. Implementation is not started or approved
by this document. [Issue #53](https://github.com/masahitojp/mariamem/issues/53)
owns the checklist and currently belongs to v0.6.1; this proposal does not move
the milestone or approve a release. Pre-starting unused children is
[Issue #84](https://github.com/masahitojp/mariamem/issues/84), not this work.

## Decision proposed

Add an opt-in, immutable per-Snapshot child limit to Go and Python. Acquire a
slot before starting a DB, retain it through disposal, and wait cancellably
when full. Leave unspecified limits unbounded to preserve existing direct-API
behavior. Keep the Go fixture's existing default of two and its outer admission
gate; do not add a second capacity wait inside that fixture.

This bounds concurrent children without claiming lower per-Fork CPU, a memory
ceiling or faster tests. The main concern is lifecycle complexity: consuming a
child into another Snapshot, Live replacement and Python handoff all escape a
simple "release on Close" implementation. The proposal below includes explicit
rules and finite acceptance cases for these boundaries. In particular, it
proposes rejecting cross-host handoff only for a capped Snapshot; this new
combination restriction needs Human agreement before implementation. If capped
handoff is required now, revise the design around cross-host lease ownership;
do not silently ship an unenforced limit.

## Inspected sources

Local product source_commit: `8f42948340265ce38fde2d1fa6b2f82bf14ae9d2`
(main inspected before writing; not a claim of implementation acceptance).

- [Snapshot ownership contract](../decisions/snapshot-product-contract.md),
  `snapshot.go`, `mariamem.go`: consuming capture, concurrent startup, parent
  Close preserves successful children, Close keeps its first cleanup result.
- `internal/control/shared.go`, `python/mariamem/{__init__,snapshot,_session}.py`:
  Python has a separate Go-host baseline owner, concurrent control requests,
  cancellation and late-response cleanup; its explicit different-host option
  currently exports/imports a private baseline.
- `live.go`, `internal/control/live.go`, `internal/live/endpoint.go`:
  both frontends create private children. Reset starts a replacement before
  retiring the old child. Python Live does not call public Go Snapshot.Fork.
- `mariamemtest/fixture.go`: existing cap covers acquisition through SQL-pool
  and DB cleanup, defaults to two, wakes waiters on fixture Close/debt.

pgmem reference source_commit:
`a61005d37d01e6671f814fe8ca828222e8147df4`, GitHub commit API tree
`6989b187a4b744fb06678d7673c9f29e11a19bd1` (the source already cited in #53).
Source inspection only; no upstream test or performance run was performed.

| Reference | What informs this proposal |
| --- | --- |
| [snapshot.go](https://github.com/shibukawa/pgmem/blob/a61005d37d01e6671f814fe8ca828222e8147df4/snapshot.go) | Per-Snapshot channel of slots, acquire before boot, return on boot failure/child close, context-aware capacity wait. |
| [forks.go](https://github.com/shibukawa/pgmem/blob/a61005d37d01e6671f814fe8ca828222e8147df4/forks.go) | Memory-derived default; deliberately not copied here. Its PostgreSQL memory estimate is not a MariaDB budget. |
| [Python client](https://github.com/shibukawa/pgmem/blob/a61005d37d01e6671f814fe8ca828222e8147df4/packages/python/src/pgmem/_client.py) | `snapshot(max_forks=...)`, host-owned slots and `fork(timeout=...)` returning `pool_timeout`. |
| [Published limits](https://shibukawa.github.io/pgmem/limits/#fork-capacity-and-waiting) | User-facing distinction between slot wait and startup; a mutable documentation reference, not the pinned code identity. |

Do not copy upstream lifetime semantics wholesale: pgmem restarts its source
after capture, whereas mariamem consumes it. At the inspected pgmem revision,
Close stores a flag but does not notify capacity waiters, and Fork checks that
flag only before waiting. mariamem requires a Close wakeup plus an atomic
admission recheck. This is a source observation, not a reproduced upstream bug
report or a statement about later pgmem revisions.

## Proposed user API

Go adds `MaxForks int` to the existing `SnapshotOptions`:

```go
saved, err := db.Snapshot(ctx, mariamem.SnapshotOptions{MaxForks: 4})
if err != nil { return err }
defer saved.Close()

acquireCtx, cancel := context.WithTimeout(ctx, 10*time.Second)
defer cancel()
child, err := saved.Fork(acquireCtx) // waits if four children occupy slots
if err != nil { return err }
defer child.Close()                 // SQL pools/connections close first
```

Go `0` means unbounded, positive values are explicit caps, negatives are invalid.
Python adds `Database.snapshot(*, max_forks=None, rollback=False, timeout=120)`
and `Snapshot.fork(*, timeout=None, **options)`:

```python
with source.snapshot(max_forks=4) as saved:
    with saved.fork(timeout=10, startup_timeout=120) as child:
        use_database(child)  # close SQL connections before leaving this block
```

Python `None` means unbounded; a positive built-in integer sets a cap.
Reject zero, negatives, bool, float and string with ValueError before consuming
the source. Go validation also precedes host capture. Do not silently coerce.
Validate Python fork timeouts as positive finite numbers, excluding bool;
`None` waits indefinitely for capacity. No mutable setter or public Wait API.

For direct `Database(snapshot=saved)` / `start(snapshot=saved)`, enforce the
same host-owned limit. Add `fork_timeout=None` to that constructor as the
equivalent slot timeout; a non-None value without a Snapshot is invalid.
`Snapshot.fork(timeout=...)` maps to it; reject a duplicate `fork_timeout` in
its options rather than accepting two conflicting deadlines.

### Timeouts and diagnostics

- Go's existing context covers capacity waiting and startup, not child lifetime;
  `Options.StartupTimeout` begins after admission, and the earlier deadline wins.
- Python fork `timeout` bounds only slot waiting, matching the pgmem naming.
  Existing `startup_timeout` begins after admission. Capture `timeout` keeps its
  existing meaning. Explain this language difference beside the examples.
- Capacity timeout: Go wraps `context.DeadlineExceeded` and retains errors.Is;
  Python raises existing HostError with `code=pool_timeout`, `stage=fork_wait`,
  `closed=False` (parent remains usable). Cancelled Go requests retain
  context.Canceled. Parent Close returns closed; cleanup debt returns unusable.
- Report configured cap and occupied slots, and the action "close owned children
  or increase max_forks". Distinguish capacity waiting from startup failure.
  Do not diagnose OOM or a leaked child without evidence; no periodic log service.

Python must not keep the current `startup_timeout + 15` response deadline while
waiting for a slot: that would terminate a valid long queue wait. For capped
same-host Fork, let the host own wait/start deadlines and await the terminal
reply (`response_timeout=None`); EOF/fatal-host failure and KeyboardInterrupt
still use existing cancellation/late-owner paths. This does not promise a hard
wall deadline for uncooperative cleanup. The unbounded legacy path keeps its
existing response watchdog. A finite user wait timeout does not justify
releasing a slot before a late-started child has actually been disposed.

## Accounting and ownership

For each capped Snapshot, `occupied <= MaxForks` at all times. Count admitted
startup, returned DBs, unclaimed late-created DBs and cleanup still in progress.
Queued requests, the immutable baseline and its already-consumed source do not
occupy slots. Live children use this same counter. Independent snapshots have
independent caps; root Start, descendants' own snapshots, separate Python hosts
and xdist workers do not share a global budget.

| Transition | Slot / parent action |
| --- | --- |
| Request while full | Wait without allocating a runtime or holding the backing/manager lock. |
| Admit | Atomically check open, healthy and available; take one lease and pin backing for startup. |
| Successful startup | Transfer the lease to the child before publishing it. |
| Startup failure/cancel before publication | Dispose partial ownership, then return the lease once; retain original and cleanup errors. |
| Successful DB Close | Return once after runtime workers and owned resources finish cleanup. |
| Child Snapshot succeeds | Source runtime is disposed; return its original-parent lease. The new immutable baseline has its own explicitly supplied limit, default unbounded. |
| Capture rejects busy/transaction/invalid options | Source stays alive and retains its lease. |
| Capture consumes source but fails | Return only on confirmed disposal; consumed is not itself proof of cleanup. |
| Cleanup incomplete/uncertain | Retain the lease, poison that capped parent's admission and wake waiters with the cause. Never turn `closed=True` into proof of disposal. |
| Parent Close | Stop new admission and wake queued calls immediately; wait only for admitted startups' backing use, then close backing. Do not close/wait for successful children. |

Repeated/concurrent child Close, capture and fatal-worker cleanup share one
lease completion path. A later Live disposal retry can discharge its lease,
but a poisoned parent does not automatically resume admission in this version.
Healthy siblings keep their existing lifetime. Parent Close reports retained
debt already known when it completes; a later child error remains that child's
error and does not retroactively change an earlier Close result.

Slot waits never hold the existing Snapshot RLock. Otherwise Snapshot.Close
could wait behind a blocked Fork while the user waits for Close before closing
children. A small mutex/state-notification admission owner linearizes Close,
cancel, available-slot checks and startup registration. No strict FIFO fairness
promise. Recheck cancellation before admission; whichever operation linearizes
first wins a concurrent Close/admission race. An admitted startup may finish
successfully while Close waits, as in the current ownership contract.

The limiter is independent of the parent backing lifetime: children must still
release safely after parent Close. No waiting on child-owned locks under the
limiter/manager lock. No cap-sized channel allocation for an arbitrarily large
user number; keep count plus change notification instead.

### Live and development-host handoff

**Live is accounted for, not an unmetered bypass.** A finite cap must be at least
two to create Live; cap one rejects before starting a child (`invalid_options`,
`live_precondition`). Live creation uses a nonblocking reservation: if full,
return busy without creating an endpoint. Unlimited snapshots keep their path.

Reset needs one extra slot because old and replacement coexist. Reserve it
nonblockingly under the Live operation gate, before draining/changing state.
If unavailable, return busy at `live_capacity`, preserving current generation,
SQL availability and old child. If available, retain the reservation through
drain/startup; release it on a rejected drain or failed preparation after cleanup.
Transfer it to the replacement once started. Retire the old lease only after
successful old-child cleanup. A failed reset after replacement begins retains
the existing failed-endpoint contract. Cap two is sufficient for one Live alone,
but is not a reservation guaranteeing resets alongside other children.

**Different-host handoff:** a capped Snapshot rejects Python host_binary
overrides that would select a different Session, before handoff/export or a
replacement host is launched (`unsupported`, `fork_handoff`, parent preserved).
The host's handoff operation also rejects a capped baseline. Unlimited snapshots
retain existing cross-host behavior. Do not add a Python-only semaphore that
releases on timeout while another host may still be starting the DB. Supporting
capped cross-host children needs a separate lease/acknowledgment design.

## Implementation boundaries proposed

1. One internal admission/lease primitive shared by public Go Snapshot and
   control-manager baseline. It is policy/ownership code, not guest code.
2. Attach leases to both child owner types and all consumed-capture, fatal,
   startup-failure and Close paths. Where existing cleanup returns only an
   undifferentiated error, add a private disposal outcome; do not infer success
   from an error code. Audit ignored startup cleanup errors before reuse.
3. Shared control adds max_forks and fork-wait timeout fields and a capability
   `fork-limit-v1`. Python checks it before capped capture, rejecting an old host
   without consuming the DB; never let an old host silently ignore the limit.
   Preserve cancel/EOF/late-response handling and session retain/release counts.
4. Live's factory gets a private reservation boundary for creation/reset. Both
   Go and Python adapters consume the same primitive, without a second lease.
5. Go fixture keeps its existing outer cap and unlimited private Snapshot.
   Its SQL-pool cleanup/debt/Close semantics are broader than bare DB slots;
   replacing that gate is unnecessary for #53. Default two stays unchanged.
6. Add session-scoped pytest fixture `mariamem_max_forks` (default None), passed
   by the supplied `mariamem_snapshot` to capture. Validate before its preparation
   callback/command. Custom snapshot fixtures can pass max_forks directly.
   xdist limits apply independently per worker; no CLI auto-sizing or D1 redesign.

Guest/WASM/generated source, wire connection count, runtime SQL behavior,
automatic sizing, prewarming/pooling and performance tuning are outside this
change. This is Go host/lifecycle plus Python API and fixture work.

## Fixed acceptance and stopping point

Tests below are required future work, **not PASS claims**. Use deterministic
barriers/fakes for precise ordering and actual guest smoke for public behavior.
No RSS campaign, queue performance campaign or new qualification pipeline.

| Boundary | Finite acceptance |
| --- | --- |
| Inputs/compatibility | Omitted/zero Go and None Python keep legacy behavior; positive caps; invalid values preserve source; old-host capability rejects before capture; capped handoff refuses before export/start while unlimited handoff remains covered. |
| Admission | Caps 1 and 2 with four requesters; prove starting+live+cleaning never exceeds cap; release permits later progress; separate snapshots do not share the counter. |
| Wait/Close races | Go deadline/cancel and Python wait expiry/interrupt; Close wakes blocked requests despite live children; no RLock deadlock; admitted startup/backing race and repeated Close; SQL works on child after parent Close. |
| Disposal | Startup failure before/after allocation; cleanup failure poisons admission; original cause retained; double Close cannot release twice; consumed/preserved capture success/failure and late successful replies each have exactly one owner. |
| Live | Cap one rejects; cap two create/reset passes; ordinary Fork can exhaust spare slot; reset busy preserves generation/data and becomes possible after release; drain failure returns reservation; replacement/cleanup failure does not over-admit. |
| Python entry | Both fork spellings enforce cap; Session refs/cancel/late cleanup balanced; pytest option passes through without changing None/callable/PrepareCommand behavior; worker-local default remains. |
| Existing Go fixture | Default two, configured cap, pool-before-DB cleanup, debt stops admission and Close wakes waiters remain; prove no inner capacity wait is configured. |

Use existing Go unit/race and Python unit owners, then a small public-API actual
guest sequence (cap1/cap2, SQL isolation, timeout, child capture, parent Close,
Live reset) on macOS arm64 and Ubuntu x86_64; Python3.11/3.14 wrappers. Existing
platform CI/release owners should carry these cases; no new full resource matrix.
Bind receipts to the tested candidate. Runtime cleanup failure injection remains
controlled-owner evidence; do not claim to reproduce real-engine OOM.

Completion: the fixed cases pass, Go/Python usage and errors are documented,
and user-visible behavior/limitations are in unreleased notes. Report unresolved
cases as unfinished; do not add performance requirements or #84 to this exit.
Integration and release follow their own decisions.

This design task stops at source inspection and this proposal, with zero builds,
runtime executions and CI submissions. Before implementation, the Human decides
whether to accept the proposed defaults, Live capacity behavior and bounded
cross-host restriction. If not, revise those rules first rather than expanding
implementation through incidental discoveries.
