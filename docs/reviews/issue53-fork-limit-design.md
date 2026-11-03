# Issue #53 — bounded Snapshot Fork capacity

Status: concrete design proposal, 2026-11-03. The Human selected an automatic,
finite default and requested continuing the design. This revision proposes a
256 MiB budget per child and preserves development-host handoff using leases.
These are design choices for review, not implemented or measured new behavior.
[Issue #53](https://github.com/masahitojp/mariamem/issues/53)
owns the checklist and currently belongs to v0.6.1; this proposal does not move
the milestone or approve a release. Pre-starting unused children is
[Issue #84](https://github.com/masahitojp/mariamem/issues/84), not this work.

## Decision proposed

Add an immutable per-Snapshot child limit to Go and Python. Acquire a
slot before starting a DB, retain it through disposal, and wait cancellably
when full. When unspecified, derive a finite limit from the host's memory budget,
following pgmem's approach. Positive values override it. There is no unlimited
mode or hidden unlimited fixture path. This intentionally changes existing direct
API behavior: requests can now wait even without a new option. Document this
change, timeout guidance and nested-child deadlock avoidance in usage/release notes.
Keep the existing Go fixture's explicit effective default of two, with its
private Snapshot set to that same finite cap; see the invariant below.

This bounds concurrent children without claiming lower per-Fork CPU, a memory
ceiling or faster tests. The main concern is lifecycle complexity: consuming a
child into another Snapshot, Live replacement and Python handoff all escape a
simple "release on Close" implementation. The proposal below includes explicit
rules and finite acceptance cases for these boundaries. Preserve cross-host
handoff with a source-host lease lasting until target disposal; do not remove
that accepted behavior. Its extra ownership plumbing is the strongest cost
objection to this design, but disabling an existing tested path or letting it
bypass the cap would change the agreed scope. Keep that plumbing private and
bounded to the current Python handoff, not a distributed resource service.

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
- `tests/test_owned_snapshot.py`: actual other-binary handoff and resnapshot
  ownership have existing regression tests. `mariamemtest/http.go` and
  `python/mariamem/e2e.py` hide their baseline creation, so their configuration
  needs an explicit cap override when an automatic result of one prevents Live.

pgmem reference source_commit:
`a61005d37d01e6671f814fe8ca828222e8147df4`, GitHub commit API tree
`6989b187a4b744fb06678d7673c9f29e11a19bd1` (the source already cited in #53).
Source inspection only; no upstream test or performance run was performed.

| Reference | What informs this proposal |
| --- | --- |
| [snapshot.go](https://github.com/shibukawa/pgmem/blob/a61005d37d01e6671f814fe8ca828222e8147df4/snapshot.go) | Per-Snapshot channel of slots, acquire before boot, return on boot failure/child close, context-aware capacity wait. |
| [forks.go](https://github.com/shibukawa/pgmem/blob/a61005d37d01e6671f814fe8ca828222e8147df4/forks.go) | Memory-derived default and finite CPU fallback inform this revision. Its PostgreSQL per-Fork estimate is not a MariaDB budget. |
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

Go `0` means automatic, positive values are explicit caps, negatives are invalid.
Python adds `Database.snapshot(*, max_forks=None, rollback=False, timeout=120)`
and `Snapshot.fork(*, timeout=None, **options)`:

```python
with source.snapshot(max_forks=4) as saved:
    with saved.fork(timeout=10, startup_timeout=120) as child:
        use_database(child)  # close SQL connections before leaving this block
```

Python `None` means automatic; a positive built-in integer sets a cap.
Reject zero, negatives, bool, float and string with ValueError before consuming
the source. Go validation also precedes host capture. Do not silently coerce.
Validate Python fork timeouts as positive finite numbers, excluding bool;
`None` waits indefinitely for capacity. No mutable setter or public Wait API.
An unlimited wait duration is distinct from an unlimited number of DBs.

### Automatic default: concrete sizing proposal

Resolve the default once at Snapshot creation in the Go owner, including for
Python. Do not run a Python memory estimator separately or resize a live limit.
Expose the resolved positive integer as Go `Snapshot.MaxForks()` and Python
read-only `snapshot.max_forks`, and include it in wait diagnostics.

Proposed formula follows pgmem:

```text
M = minimum known positive finite limit of:
    physical RAM, effective Linux cgroup memory limit, Go runtime memory limit
N = max(1, floor((M / 4) / B))
if no usable M is available: N = max(1, GOMAXPROCS(0))
B = 256 MiB (initial MariaDB-specific budgeting policy)
```

The memory sources are limits, not a claim of presently free RAM. The Go runtime
memory limit is a sizing input, not enforcement over all guest mappings. Use
effective cgroup v1/v2 limits, including tighter ancestors; ignore unavailable,
invalid and unlimited values, and clamp arithmetic safely to a positive int.
A single unavailable source must not discard the other usable limits. Explicit
positive MaxForks overrides the estimate and stays finite. A minimum of one is
not a promise that one DB can fit in an extremely small host.

The fraction, fallback and B are proposed sizing policy; only finite automatic
default/admission-before-start is the Human decision recorded here. Do not add
an arbitrary ceiling of four based on the earlier unconfirmed plateau claim.
No continuous memory monitoring, eviction, OS memory reservation or OOM guarantee.
Multiple snapshots/workers can each spend their own budget; this is not a global
memory controller. Document that larger seed/SQL workloads may require a lower
explicit MaxForks, and that a child held while synchronously requesting another
under an exhausted budget can block until cancellation/deadline.

The estimate is a policy choice informed by existing observations, not a measured
upper bound or an optimum:

- The [post-merge observation](https://github.com/masahitojp/mariamem/blob/590e2fc7572c016be2d5969f1fd66c1fe8296ae7/benchmarks/alignment-postmerge.md)
  on product source ca7d6216 measured about76.8 MiB current-RSS increment for one
  held child, small1,000-row workload, macOS/M1 only. This is not peak footprint,
  an Ubuntu estimate or an upper bound for a busy child.
- The older [memory envelope](../../benchmarks/memory-session-envelope.md) used
  Wasmer7.4.2/separate processes. Its roughly320 MiB/DB Ubuntu result must not
  be relabelled as the current generated-Go/shared-host Fork cost.
- The [v0.6.0 retained-child report](https://github.com/masahitojp/mariamem/blob/79d0b1c652786cc45e88610856d4214f110211a8/benchmarks/fork-resources.md)
  observed about76.8 MiB for one child and311 MiB for four on macOS/M1,
  using Go1.27.3. It independently supports the order of magnitude, not a
  new-platform claim or an additive sample with the post-merge cohort.
- The [parallel report](https://github.com/masahitojp/mariamem/blob/5096a0c4931e2d30b56e1d1160b3e334f35df396/benchmarks/parallel-pressure.md)
  observed whole-process sampled peaks around379/700 MiB at P4/P8 in its
  small workload. These are neither child peaks nor values to divide into a
  universal child size; they warn against treating retained RSS as the full cost.

256 MiB is roughly three times the observed small retained-child increment.
It deliberately spends fewer slots than choosing128 MiB;512 MiB would halve the
result again without new evidence that that additional restriction is needed.
Those alternatives are scheduling tradeoffs, not proven safe/unsafe boundaries.
Keep three quarters of the selected memory limit outside this per-Snapshot
estimate. Large seed copies, query allocations, other snapshots/processes and
in-flight startup can exceed the estimate: lower explicit MaxForks when needed.
An automatic cap is a finite backpressure default, not an OOM prevention claim.

| Selected memory limit M | Proposed automatic cap N |
| --- | ---: |
| 512 MiB | 1 |
| 1 GiB | 1 |
| 2 GiB | 2 |
| 4 GiB | 4 |
| 7 GiB | 7 |
| 16 GiB | 16 |

These are arithmetic examples, not measured machines, recommended parallelism
or proof that16 children fit on every16 GiB host. A16 GiB physical host with a
2 GiB effective cgroup/runtime limit selects2. Do not lower the sample limit to4
because of the previous unconfirmed plateau, or claim the limit is CPU-optimal.

No further resource campaign is required to choose this explicitly heuristic
initial policy. Current-guest Ubuntu busy/large-fixture peak memory is still
unverified by this design; do not manufacture that evidence or broaden #53 into
resource characterization. During the already-planned two-platform public-API
smoke, record the selected inputs/cap and run the fixed cap1/cap2 scenarios;
do not fill a large automatic cap merely to demonstrate that it exists. Change
the budget if a concrete ordinary workload shows the default over-admits or
unnecessarily restricts it; record a new decision instead of silently tuning.

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
waiting for a slot: that would terminate a valid long queue wait. For
same-host Fork, let the host own wait/start deadlines and await the terminal
reply (`response_timeout=None`); EOF/fatal-host failure and KeyboardInterrupt
still use existing cancellation/late-owner paths. This does not promise a hard
wall deadline for uncooperative cleanup. Root Start keeps its existing response
watchdog. A finite user wait timeout does not justify
releasing a slot before a late-started child has actually been disposed.

## Accounting and ownership

For each Snapshot, `occupied <= resolved MaxForks` at all times. Count admitted
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
| Child Snapshot succeeds | Source runtime is disposed; return its original-parent lease. The new immutable baseline resolves its own explicit or automatic limit. |
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

**Live is accounted for, not an unmetered bypass.** The resolved cap must be at least
two to create Live; cap one rejects before starting a child (`invalid_options`,
`live_precondition`). Live creation uses a nonblocking reservation: if full,
return busy without creating an endpoint. An automatic result of one does not
silently grow to two for Live; report the requirement to the caller. This Live
policy remains proposed, including its effect on previously optionless callers.

Reset needs one extra slot because old and replacement coexist. Reserve it
nonblockingly under the Live operation gate, before draining/changing state.
If unavailable, return busy at `live_capacity`, preserving current generation,
SQL availability and old child. If available, retain the reservation through
drain/startup; release it on a rejected drain or failed preparation after cleanup.
Transfer it to the replacement once started. Retire the old lease only after
successful old-child cleanup. A failed reset after replacement begins retains
the existing failed-endpoint contract. Cap two is sufficient for one Live alone,
but is not a reservation guaranteeing resets alongside other children.

**Different-host handoff: preserve, with an origin-owned lease.** Supersedes the
earlier rejection proposal. The existing explicit Python host_binary override
continues to work with matching guest identity and the new control capability.
It consumes a slot on its original Snapshot, not an unrelated target-host cap.

1. Before creating a target Session or exporting files, ask the source host to
   acquire one slot with the same fork wait timeout. Atomically admit and export
   under the existing backing protection; return the private transfer and a
   unique lease handle. Failed export returns the slot only after cleanup.
2. The lease owns admission state independently of the Snapshot registry entry.
   Closing the parent after export must not erase the lease or invalidate a
   successful child's lifetime. The Python pending-transfer owner retains both
   Sessions as needed; the source Session now lasts until lease settlement,
   whereas previously it was released immediately after transfer.
3. Target startup has its existing startup deadline. The lease transfers to the
   target DB owner before publication, and follows child Close or consumed
   capture. The host returns an explicit private disposal outcome. Python sends
   a release acknowledgement to the source only after confirmed target disposal
   and removal of its handoff scratch. A preserved capture retains the lease.
4. Timeout/KeyboardInterrupt does not release speculatively. The pending request
   and existing late-response cleanup inherit the transfer owner. A source
   export reply abandoned before target creation is safe to settle after local
   scratch cleanup; a target reply abandoned after creation must close its DB
   before settlement. Error replies can also carry disposal ownership/outcome.
5. Unknown target cleanup poisons source admission and retains its lease. A
   protocol failure alone is not target process exit. Confirmed target process
   exit/reap can settle its runtime ownership; directory cleanup is separately
   required. Source-host death prevents further source admission but does not
   kill the independent target child; its owner still closes/reaps it normally.
   Do not kill a shared target host to recover one child's slot: derived
   baselines/children may own that host independently.
6. Private release/abandon acknowledgements are idempotent and bound to their
   issued lease identity. Duplicate/unknown acknowledgements never decrement an
   unrelated slot. A failed source acknowledgement is reported as cleanup debt,
   not ignored; no dropped Python reference is treated as a release.

Keep lease records for outstanding ownership only, while preventing duplicate
settlement; do not grow an unbounded per-Fork history. No public exported lease,
saved Snapshot, remote service, lease expiry or crash-recovery promise is added.
This is a design, not an implemented proof that these races are handled. The
fixed handoff cases below must pass before claiming #53 complete.

## Implementation boundaries proposed

1. One internal admission/lease primitive shared by public Go Snapshot and
   control-manager baseline. It is policy/ownership code, not guest code.
2. Attach leases to both child owner types and all consumed-capture, fatal,
   startup-failure and Close paths. Where existing cleanup returns only an
   undifferentiated error, add a private disposal outcome; do not infer success
   from an error code. Audit ignored startup cleanup errors before reuse.
3. Shared control adds max_forks and fork-wait timeout fields and a capability
   `fork-limit-v1`. Python checks it before every capture, rejecting an old host
   without consuming the DB; never let an old host silently ignore the limit.
   Preserve cancel/EOF/late-response handling and session retain/release counts.
   Add private handoff lease creation/settlement and disposal outcomes; require
   the capability on an alternate target before using it. If that check fails,
   dispose the new Session and settle the source lease before returning the error.
4. Live's factory gets a private reservation boundary for creation/reset. Both
   Go and Python adapters consume the same primitive, without a second lease.
5. Go fixture keeps its existing outer cap and passes the same resolved positive
   value into its private Snapshot (existing default two, or explicit MaxForks).
   Its SQL-pool cleanup/debt/Close semantics are broader than bare DB slots;
   replacing that gate is unnecessary for #53. Maintain and test
   `inner occupied <= outer occupied <= cap`: acquire outer before inner, close
   the DB before returning outer, stop admission on cleanup debt. Thus the inner
   limit enforces safety but adds no second capacity wait in healthy operation.
   There is no private disable-limit flag. Default two stays unchanged.
6. Add session-scoped pytest fixture `mariamem_max_forks` (default None), passed
   by the supplied `mariamem_snapshot` to capture. Validate before its preparation
   callback/command. Custom snapshot fixtures can pass max_forks directly.
   None selects the host's automatic default. xdist limits apply independently
   per worker; no extra CLI setting or D1 redesign.
7. The owned E2E entries need a usable override: add `MaxForks` to Go HTTPConfig
   and `max_forks` to Python e2e.Config, with zero/None selecting the shared
   automatic policy. Validate explicit values before preparation and pass them
   to capture. An explicit1 rejects for this Live-based entry before starting
   the source; an auto result1 reports the Live requirement without silently
   expanding its budget. Include an explicit2 guide example. Existing app hooks,
   stable-endpoint semantics and failure admission remain unchanged.

Guest/WASM/generated source, wire connection count, runtime SQL behavior,
prewarming/pooling and performance tuning are outside this change. One-time
default sizing is now inside scope by Human direction; ongoing resource-model
tuning remains separate. This is Go host/lifecycle plus Python API/fixture work.

## Fixed acceptance and stopping point

Tests below are required future work, **not PASS claims**. Use deterministic
barriers/fakes for precise ordering and actual guest smoke for public behavior.
No RSS campaign, queue performance campaign or new qualification pipeline.

| Boundary | Finite acceptance |
| --- | --- |
| Inputs/compatibility | Omitted/zero Go and None Python select a positive automatic cap; explicit caps override it; no unlimited sentinel; invalid values preserve source; old-host capability rejects before capture. |
| Default resolution | Inject finite/missing/unlimited/malformed memory sources, tighter cgroup ancestors, tiny and huge limits; test minimum/fallback/overflow and one-time resolution; expose exact resolved cap; Go and Python use the same policy. No current-free-memory or OOM guarantee inferred. |
| Admission | Caps 1 and 2 with four requesters; prove starting+live+cleaning never exceeds cap; release permits later progress; separate snapshots do not share the counter. |
| Wait/Close races | Go deadline/cancel and Python wait expiry/interrupt; Close wakes blocked requests despite live children; no RLock deadlock; admitted startup/backing race and repeated Close; SQL works on child after parent Close. |
| Disposal | Startup failure before/after allocation; cleanup failure poisons admission; original cause retained; double Close cannot release twice; consumed/preserved capture success/failure and late successful replies each have exactly one owner. |
| Live | Cap one rejects; cap two create/reset passes; ordinary Fork can exhaust spare slot; reset busy preserves generation/data and becomes possible after release; drain failure returns reservation; replacement/cleanup failure does not over-admit. |
| Python entry | Both fork spellings enforce cap; Session refs/cancel/late cleanup balanced; pytest option passes through without changing None/callable/PrepareCommand behavior; worker-local default remains. |
| Handoff | Under cap1 a remote child blocks a same-host sibling until actual cleanup; parent Close preserves target SQL; resnapshot releases original slot only after consumed disposal; export failure, unsupported target, cancel before export response and after target creation, late success, unknown cleanup, target death and source death retain one owner; duplicate settlement cannot underflow. Retain existing different-binary/resnapshot real-host tests. |
| Existing Go fixture | Default two, configured cap, pool-before-DB cleanup, debt stops admission and Close wakes waiters remain; prove matching finite caps and inner/outer occupancy invariant without an extra healthy capacity wait. |
| Owned E2E entry | Explicit2 reaches the baseline, invalid1 rejects before preparation, automatic1 produces actionable Live failure, default/override still preserve first/second case reset and hook cleanup. |

Use existing Go unit/race and Python unit owners, then a small public-API actual
guest sequence (cap1/cap2, SQL isolation, timeout, child capture, parent Close,
Live reset and existing cross-host roundtrip/resnapshot) on macOS arm64 and
Ubuntu x86_64; Python3.11/3.14 wrappers. Existing
platform CI/release owners should carry these cases; no new full resource matrix.
Bind receipts to the tested candidate. Runtime cleanup failure injection remains
controlled-owner evidence; do not claim to reproduce real-engine OOM.

Completion: the fixed cases pass, Go/Python usage and errors are documented,
and user-visible behavior/limitations are in unreleased notes. Report unresolved
cases as unfinished; do not add performance requirements or #84 to this exit.
Integration and release follow their own decisions.

This design task stops at source inspection and this proposal, with zero builds,
runtime executions and CI submissions. The concrete recommendation is the
256 MiB/quarter-memory default, unchanged proposed Live reservation behavior and
preserved cross-host handoff with leases. The finite automatic-default direction
is already decided. Review the concrete lifecycle/API choices before product
implementation; no further measurement is made a prerequisite by this proposal.
If lease implementation reveals an unowned late-outcome path, stop and report
that exact boundary instead of removing handoff or adding another campaign.
