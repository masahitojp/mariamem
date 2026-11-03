# Issue #53 — bounded Snapshot Fork capacity

Status: implementation authorized, 2026-11-03. After the lock, Live recovery and
numeric-range additions at `a4929d12`, the Human requested proceeding with this
design. The first implementation checkpoint is recorded in
[the implementation record](issue53-fork-limit-implementation.md). Public entry
Go Snapshot/Live and the Go helpers now use the limiter. Shared-control/Python
entry wiring and the full acceptance table below remain unfinished.
The design selects a 256 MiB budget per child and preserves development-host
handoff using leases. Authorization is not a claim of measured new behavior.
[Issue #53](https://github.com/masahitojp/mariamem/issues/53)
owns the checklist and currently belongs to v0.6.1; this proposal does not move
the milestone or approve a release. Pre-starting unused children is
[Issue #84](https://github.com/masahitojp/mariamem/issues/84), not this work.

## Approved implementation direction

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
- D1 `python/mariamem/django/{_database,_lifecycle,_cases,_runner,pytest_plugin,_xdist}.py`:
  run baseline, consumed class-setup source, class baseline, per-test children
  and final Django DROP child all use the same Snapshot/Fork product surface.
  D1 is an explicit target, not covered implicitly by generic Python fixtures.

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

Go `0` means automatic; explicit caps are integers1 through2,147,483,647
(`MaxInt32`) inclusive. Negative and larger values are invalid, even on64-bit Go.
Python adds `Database.snapshot(*, max_forks=None, rollback=False, timeout=120)`
and `Snapshot.fork(*, timeout=None, **options)`:

```python
with source.snapshot(max_forks=4) as saved:
    with saved.fork(timeout=10, startup_timeout=120) as child:
        use_database(child)  # close SQL connections before leaving this block
```

Python `None` means automatic; a built-in integer in1..2,147,483,647 sets a cap.
Reject zero, negatives, larger integers, bool, float and string with ValueError before consuming
the source. Go validation also precedes host capture. Do not silently coerce.
Validate Python fork wait timeouts as positive finite numbers no greater than
2,147,483,647 seconds, excluding bool;
`None` waits indefinitely for capacity. No mutable setter or public Wait API.
An unlimited wait duration is distinct from an unlimited number of DBs.

### Numeric boundaries and request-local rejection

Use the same MaxInt32 capacity ceiling in Go, Python, fixtures, D1/E2E settings
and the control owner. Clamp automatically calculated capacities to that ceiling;
reject explicit overflow rather than clamp it. This ceiling is representational,
not a recommendation to allocate that many DBs. A large accepted cap must not
preallocate a cap-sized buffer or channel.

For the new Python fork-wait settings, accept only built-in int/float in
`0 < seconds <= 2,147,483,647`; optional None is allowed only on the direct API.
Check the magnitude of arbitrary-precision integers BEFORE converting to float
or duration. Reject NaN/infinity, bool, underflow-to-zero and out-of-range values
before any reservation, host launch or capture. Serialize an accepted duration
as integer nanoseconds plus `ns`, rounding positive subnanosecond values up to1ns
without intermediate floating-point overflow. This bound and the existing
15/25-second watchdog margins fit signed64-bit duration arithmetic. Do not emit
float exponent text such as `1e-09s` for Go duration parsing.

This defines the new capacity/wait settings, not a new restriction on arbitrary
Go context deadlines or all existing SDK timeout options. Existing duration
fields retain their validation; do checked arithmetic wherever new code adds a
watchdog margin. A timed-out wait must not wrap into a negative/infinite timeout.

The host must also reject a well-framed request with a valid request ID and an
out-of-range capacity/duration WITHOUT ending the shared Session. Decode the new
fields into raw JSON / json.Number or an equivalent checked representation,
then validate within the request handler before narrowing to Go int/duration.
Do not put the new capacity directly into an int field in the outer fatal JSON
decoder. Return `invalid_options`, `snapshot_options` or `fork_options` as
appropriate, `closed=false`, with no admission or source consumption. For capture,
internal omitted/zero capacity selects auto; other wrong types/ranges fail.

Invalid JSON framing, an unusable request ID and other existing fatal transport
violations retain their protocol treatment. This proposal distinguishes field
validation from malformed transport; it does not promise recovery from every
invalid frame. The overflow tests below are future coverage, not a claim that
the not-yet-added field currently reproduces a product bug.

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

**CPU / latency limitation (G2):** auto is a memory-budget heuristic, not a
CPU-optimal or latency-optimal concurrency setting. A16 GiB memory limit may
select16 even on a much smaller CPU allocation. For latency-sensitive suites,
set an explicit positive MaxForks and compare whole-suite and tail behavior
under the intended workload. Usage docs and unreleased notes must say this next
to the automatic-default example, not only in this design. Neither this formula
nor passing CI proves a performance improvement.

The observed eight guest worker starts per DB are not eight continuously running
CPU cores or dedicated OS threads: `code/base/base.go:ThreadLaunch/ThreadSpawn`
runs guest workers as goroutines. [Go's scheduler](https://go.dev/blog/container-aware-gomaxprocs)
multiplexes those goroutines; GOMAXPROCS limits simultaneous Go execution in one
process, not the total number of guest workers. More children can still add
queueing, synchronization and CPU costs. The cited P4/P8 report observed lower
wall but higher CPU at P8 in all three paired rounds; it does not establish a
universal P4 plateau or extrapolate P16. Thread-count multiplication alone is
not a sizing oracle.

An alternative `min(memory_cap, CPU_budget)` remains a possible policy change,
not selected by this revision. It would need explicit treatment of affinity,
container quotas, user GOMAXPROCS overrides and multiple hosts/workers, and can
unnecessarily limit I/O-heavy workloads. No new CPU campaign or implicit change
to the agreed automatic formula is introduced to close the documentation gap.

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

**Python response watchdog (G3):** retract the earlier `response_timeout=None`
proposal for Fork. A live but nonresponding host must cause a finite control
error even when the user permits indefinite capacity waiting. Separate capacity
acquisition from runtime startup; an unlimited slot wait never means an unlimited
wait for one host reply.

1. A private nonblocking `fork_reserve` request returns full, closed/debt, or a
   unique reserved lease. Each request has a5-second send/reply watchdog,
   shortened by the remaining finite slot-wait budget. While responsive replies
   say full, retry at250ms intervals (sleep no longer than remaining budget).
   Check local Snapshot closure and interruption between attempts. There is only
   one outstanding reservation attempt per caller, not an accumulating poll queue.
2. `fork(timeout=None)` may repeat responsive full replies indefinitely. A
   finite timeout uses a monotonic deadline over all attempts/sleeps. Ordinary
   full-pool expiry is `pool_timeout/fork_wait`; an unresponsive control exchange
   reports a control TimeoutError with `fork_reserve` context, not a false
   diagnosis that the user merely forgot to close a child.
3. Once reserved, send startup with that lease and retain the existing
   `startup_timeout + 15` response watchdog. The host applies startup_timeout
   after admission. A changed capacity cannot cause startup to wait again.
   Preserve the current bounded db_close/Session-reap handling. Cleanup may
   outlast the caller's deadline; report that debt rather than claim disposal.
4. The host holds no backing RLock across RPCs. Parent Close invalidates unused
   reservations and wakes/fails their owners; start atomically consumes a live
   reservation and pins backing. Already-started children retain their lifetime.
   Reservation tokens cannot be replayed, double-consumed or settle a different
   child's lease. Close does not wait for an abandoned pre-start reservation.
5. Timeout/cancel transfers ownership to the pending/late-reply owner. A late
   unused reservation must be cancelled; a late-created DB must be closed before
   its lease is released. Neither an elapsed watchdog nor `closed=True` proves
   resource disposal. Do not retry an ambiguous reservation automatically.

Apply bounded control exchanges to handoff reservation/export/start/settlement
as well: reserve5s; export uses startup_timeout+15; target startup uses its
startup_timeout+15; settlement uses5s. They are separate bounds, not a claimed
single end-to-end timeout. A caller cannot block forever while writing a control
request or sending cancellation: the watchdog must cover submission/write as
well as reply. Use a Session-owned bounded writer/submission mechanism and
best-effort nonblocking cancel scheduling, not one leaking thread per timeout.
Keep a blocked writer owned until transport closure/reap; do not close the
shared host merely to satisfy one request's deadline. This affected transport
boundary needs the stuck-reader test below, not just a fake delayed reply.

The supplied pytest fixture gets a session-scoped `mariamem_fork_timeout`, default
30 seconds, requiring a positive finite value, and passes it to every fork.
It cannot select an infinite wait. A closed-over child exhausting cap1 produces
a readable fixture acquisition failure and stops admission according to P1.
Custom direct API code can deliberately choose None, with explicit ownership
responsibility. Root Start's current watchdog is retained.

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
| Python reserved, not started | Count the slot, but do not hold a backing lock across requests; parent Close revokes the reservation. Startup atomically rechecks and consumes it. |
| Successful startup | Transfer the lease to the child before publishing it. |
| Startup failure/cancel before publication | Dispose partial ownership, then return the lease once; retain original and cleanup errors. |
| Successful DB Close | Return once after runtime workers and owned resources finish cleanup. |
| Child Snapshot succeeds | Source runtime is disposed; return its original-parent lease. The new immutable baseline resolves its own explicit or automatic limit. |
| Capture rejects busy/transaction/invalid options | Source stays alive and retains its lease. |
| Capture consumes source but fails | Return only on confirmed disposal; consumed is not itself proof of cleanup. |
| Cleanup incomplete/uncertain | Retain the lease, block that parent's admission and wake waiters with the cause. Never turn `closed=True` into proof of disposal; only the explicit checked Live recovery below can reopen it. |
| Parent Close | Stop new admission and wake queued calls immediately; wait only for admitted startups' backing use, then close backing. Do not close/wait for successful children. |

Repeated/concurrent child Close, capture and fatal-worker cleanup share one
lease completion path. A later Live disposal retry can discharge its lease.
No background completion automatically resumes blocked admission. Explicit Live
Reset can reopen it only by the recovery checks below; this supersedes any
reading of the initial proposal as irreversible poisoning for recoverable Live.
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

**Python parent lock (P1):** the current different-host branch in
`python/mariamem/__init__.py` launches the target and requests handoff inside
`with snapshot._lock`. That lock scope must not survive the new capacity wait.
Apply this ordering to both ordinary and different-host Fork:

1. Under snapshot._lock, reject closed, copy the source Session, immutable handle
   and needed options, and retain the Session. Establish one pending-operation
   owner that owes that reference. Do not send an RPC or start a target here.
2. Release snapshot._lock before capacity polling, waiting on a reply, sleeping,
   target Session construction, export, startup or cleanup/release. A local
   closed-state recheck may briefly take the lock, but performs no blocking work.
3. Snapshot.close marks closed and signals a dedicated admission-close event
   under that same lock, then performs its host RPC outside it. The capacity
   retry interval waits on this event, not an uninterruptible sleep and not the
   existing _close_done event (which only signals completed remote cleanup).
4. Observe closure before issuing the next request; the host's atomic
   close/reserve/export boundary resolves in-flight races. A late unused lease
   is cancelled. An export/start already admitted under the host contract keeps
   its existing independent child lifetime. A new Python recheck alone does not
   substitute for the host-side admission check.
5. Release the retained Session exactly once outside snapshot._lock on failure,
   or transfer it to the remote-child/late-response cleanup owner on success or
   interruption. Parent Close cannot reap the source Session out from under the
   pending request, and waiting cannot prevent parent Close from taking the lock.

The required race test observes a full response at cap1 while the original child
stays alive, calls parent Close on another thread, and joins both Close and the
waiting different-host Fork BEFORE closing that child. The waiter must fail
closed, not succeed or time out waiting for child release; no target host/export
may have started. The original child still executes SQL after parent Close.
Use explicit barriers and an outer test deadline; the old non-capacity handoff
tests do not detect this combination. Stuck-host response timing remains covered
separately by G3 rather than being called an immediate Close wakeup guarantee.

### Live and development-host handoff

**Live is accounted for, not an unmetered bypass.** The resolved cap must be at least
two to create Live; cap one rejects before starting a child (`invalid_options`,
`live_precondition`). Live creation uses a nonblocking reservation: if full,
return busy without creating an endpoint. An automatic result of one does not
silently grow to two for Live; report the requirement to the caller. This Live
policy remains proposed, including its effect on previously optionless callers.

For a healthy endpoint, Reset needs one extra slot because old and replacement coexist. Reserve it
nonblockingly under the Live operation gate, before draining/changing state.
If unavailable, return busy at `live_capacity`, preserving current generation,
SQL availability and old child. If available, retain the reservation through
drain/startup; release it on a rejected drain or failed preparation after cleanup.
Transfer it to the replacement once started. Retire the old lease only after
successful old-child cleanup. A failed reset after replacement begins retains
the existing failed-endpoint contract. Cap two is sufficient for one Live alone,
but is not a reservation guaranteeing resets alongside other children.

**Explicit recovery after cleanup failure (P2):** preserve the existing explicit
Reset recovery intent. A failed endpoint permits Reset and Close; it is not
permanently Close-only. Under its operation gate, first reject a closed parent,
then retry the disposal of its retained pending children AND any current/old
child whose disposal failed. Keep owners/leases until completion is confirmed.
Do this BEFORE reserving replacement capacity, since unresolved cleanup may be
occupying both slots at cap2. A closed-parent check may not reject solely for
recoverable cleanup debt before these retries can run.

After successful retries, request an atomic recovery/reservation from the parent
limiter. It may resume only if the parent is still open, ALL its recorded cleanup
debt is resolved and a slot is available; closure or a concurrently added debt
must win over stale success. Debt from another child/Live/remote transfer cannot
be forgiven by this endpoint. Ordinary live children are still counted but need
not be closed. If any debt remains, return the retained cause and keep admission
blocked; if just capacity is full, return busy and keep this endpoint failed.
Reserve the new child's slot in the same successful recovery transition to
avoid another waiter taking it between reopening and acquisition.

Only a committed replacement makes Live ready and advances its generation;
the failed Reset's original error remains a failure. Retry failure retains
ownership and blocks admission; there is no slot borrowing or discarded error.
Normal healthy Reset's capacity-busy path still preserves the usable old child.
Parent/Live Close is irreversible. This private recovery path does not add a
public Snapshot.resume API, rewrite Database.Close's stored-result contract, or
clear P1/D1/Go fixture test-admission latches after a failed test cleanup.

**Different-host handoff: preserve, with an origin-owned lease.** Supersedes the
earlier rejection proposal. The existing explicit Python host_binary override
continues to work with matching guest identity and the new control capability.
It consumes a slot on its original Snapshot, not an unrelated target-host cap.

1. Before creating a target Session or exporting files, acquire one source-host
   reservation with the bounded protocol above. Export atomically consumes that
   reservation under existing backing protection; return the private transfer
   and its unique lease handle. Failed export returns the slot only after cleanup.
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
5. Unknown target cleanup blocks source admission and retains its lease. A
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

### D1 prepared Django lifecycle (G1)

Add `max_forks=None` and `fork_timeout=30` to the declaration-only
`prepared_database(...)` entry. Validate at declaration without starting a host;
max_forks follows the SDK rules and fork_timeout must be positive and finite.
Keep these settings separate from `options` forwarded to root start. Thread them
through Configuration/Owners: every run or class capture passes max_forks, and
every ordinary or teardown Fork passes fork_timeout. D1 uses the same SDK limit
and watchdog; it has no independent semaphore or bypass. Publish these settings
in docs/django-prepared.md with a cap1 example.

Auto is resolved by the owning Go host at each successful capture: the run
baseline and each class baseline have distinct immutable budgets. It is not
inherited from the original resolved number or shared across all classes. An
explicit max_forks=1 is applied to every capture in that configuration.

The normal cap1 sequence must be executable:

```text
run baseline R -> class-setup DB C     R occupied: 1
capture C -> class baseline S         R occupied: 0 (C consumed/disposed)
S -> test child T -> close T          S occupied: 1 -> 0, repeated per test
class cleanup closes S               R remains available
R -> final DROP child -> close        R occupied: 1 -> 0
```

Do not assume that healthy ordering proves failure cleanup. Current
`Manager.finish_databases()` requests its fresh teardown child BEFORE closing
other owners; a preserved class source may still occupy R's only slot. Reorder
finalization to quiesce and retire remaining mutable children/class baselines
while retaining R, then request the teardown child. A class-setup failure before
capture, preserved capture rejection and a consumed capture error need distinct
tests. If R is blocked by cleanup debt or disposal cannot be confirmed, do not wait indefinitely
or grant an emergency slot: retain the original/cleanup causes, fail teardown,
and execute the remaining owner cleanup. Do not let Django DROP run on a closed
or wrong DB. Finalization may bypass the test-admission latch only when actual
disposal is confirmed and R itself is healthy; it never bypasses the SDK cap.

For pytest-xdist retain the supported explicit local -n N / load / loadscope
profile. Each DB-using worker owns its own root/class baselines and resolves auto
in its own host. No controller or DB-free worker acquires; a replacement worker
starts fresh. Caps do not divide memory/CPU budgets by worker count, and are not
a run-wide maximum. Recommend explicit per-Snapshot max_forks and independently
chosen -n for resource-sensitive suites. Existing serial-in-worker execution is
unchanged; no new parallel classes, Django --parallel or shared worker baseline.

## Implementation boundaries proposed

1. One internal admission/lease primitive shared by public Go Snapshot and
   control-manager baseline. It is policy/ownership code, not guest code.
2. Attach leases to both child owner types and all consumed-capture, fatal,
   startup-failure and Close paths. Where existing cleanup returns only an
   undifferentiated error, add a private disposal outcome; do not infer success
   from an error code. Audit ignored startup cleanup errors before reuse.
3. Shared control adds max_forks, bounded reservation/start operations and a capability
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
   per worker; add finite mariamem_fork_timeout as above. No extra CLI setting.
7. The owned E2E entries need a usable override: add `MaxForks` to Go HTTPConfig
   and `max_forks` to Python e2e.Config, with zero/None selecting the shared
   automatic policy. Validate explicit values before preparation and pass them
   to capture. An explicit1 rejects for this Live-based entry before starting
   the source; an auto result1 reports the Live requirement without silently
   expanding its budget. Include an explicit2 guide example. Existing app hooks,
   stable-endpoint semantics and failure admission remain unchanged.
8. D1 is explicitly in scope: declaration settings, run/class capture propagation,
   finite ordinary/finalization waits and teardown ordering above. Keep its
   deferred startup, native Django preparation, class/test isolation, failure
   latch and local xdist contract. This is a compatibility extension, not a new
   framework lifecycle or expansion of supported Django modes.

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
| Numeric limits | Capacity1/MaxInt32 accepted without cap-sized allocation; zero/negative/MaxInt32+1/2**100 and wrong types handled per API. Wait positive subnanosecond/max seconds accepted by validation; zero/negative/next float above max/2**100/NaN/infinity/bool rejected before sending. Well-framed raw control overflow returns invalid_options without host exit. Original source and healthy sibling SQL still work after each rejection. Accepted huge durations are validation tests, not real waits. |
| Default resolution | Inject finite/missing/unlimited/malformed memory sources, tighter cgroup ancestors, tiny and huge limits; test minimum/fallback/overflow and one-time resolution; expose exact resolved cap; Go and Python use the same policy. No current-free-memory or OOM guarantee inferred. |
| Admission | Caps 1 and 2 with four requesters; prove starting+live+cleaning never exceeds cap; release permits later progress; separate snapshots do not share the counter. |
| Wait/Close races | Go deadline/cancel and Python wait expiry/interrupt; Close wakes blocked requests despite live children; no RLock deadlock; admitted startup/backing race and repeated Close; SQL works on child after parent Close. |
| Python transfer/parent lock | cap1 held child, different-host Fork observes full, concurrent parent Close and waiter both finish before child Close; waiter fails closed, original child SQL works, no target/export starts, source Session references balanced. Cover close after Session retain/before reserve and late reservation races with barriers. |
| Disposal | Startup failure before/after allocation; cleanup failure blocks admission; original cause retained; double Close cannot release twice; consumed/preserved capture success/failure and late successful replies each have exactly one owner. |
| Live | Cap one rejects; cap two create/reset passes; ordinary Fork can exhaust spare slot; reset busy preserves generation/data and becomes possible after release; drain failure returns reservation; replacement/cleanup failure does not over-admit. |
| Live cleanup recovery | Real limiter cap2 with controlled child disposal: old-child failure, failed candidate disposal occupying both slots, failed retry, then confirmed retry plus explicit Reset recovers without exceeding2. No automatic restart, no double release, generation advances only on commit. Unrelated unresolved lease debt and concurrent parent Close prevent reopening. Exercise both Go and shared-host adapters; prior limiter-free tests alone do not satisfy this row. |
| Python entry | Both fork spellings enforce cap; Session refs/cancel/late cleanup balanced; pytest option passes through without changing None/callable/PrepareCommand behavior; worker-local default remains. |
| Python watchdog | Real control subprocess stays alive but never replies to reserve or startup, then independently stops reading stdin while its pipe fills. Finite caller failure covers send/reply/cancel; responsive-full polling honors finite and explicitly indefinite waits. Late reserve/start success has exactly one cleanup owner; repeat timeout cannot accumulate writer threads or release a running child. |
| Supplied pytest wait | cap1 and an intentionally held child cause fixture failure at its finite default/configured deadline; no next-test admission, original diagnostic retained. Invalid/None fixture timeout rejects. Do not simulate success by killing the entire lineage. |
| Handoff | Under cap1 a remote child blocks a same-host sibling until actual cleanup; parent Close preserves target SQL; resnapshot releases original slot only after consumed disposal; export failure, unsupported target, cancel before export response and after target creation, late success, unknown cleanup, target death and source death retain one owner; duplicate settlement cannot underflow. Retain existing different-binary/resnapshot real-host tests. |
| Existing Go fixture | Default two, configured cap, pool-before-DB cleanup, debt stops admission and Close wakes waiters remain; prove matching finite caps and inner/outer occupancy invariant without an extra healthy capacity wait. |
| Owned E2E entry | Explicit2 reaches the baseline, invalid1 rejects before preparation, automatic1 produces actionable Live failure, default/override still preserve first/second case reset and hook cleanup. |
| D1 serial | cap1 through run capture, class setup/capture, two isolated per-test children, class cleanup and final DROP child; both PreparedTestCase and PreparedTransactionTestCase, standard runner and pytest. Each capture resolves auto independently in a controlled policy test; explicit cap propagates without acquisition at declaration. |
| D1 failure/xdist | Class setup before capture fails; capture preserves/consumes on failure; child cleanup failure never hangs final DROP or reuses an uncertain slot. Existing local2-worker load/loadscope cases with cap1 per Snapshot preserve isolation and final cleanup; controller/idle workers acquire none, replacement workers receive the same settings. |
| CPU documentation | Usage guides/release notes distinguish memory budget from CPU/latency optimality, explicit tuning and worker totals. Mechanical policy tests cannot prove a performance benefit; P16 and CPU-optimal settings remain unmeasured. |

Use existing Go unit/race and Python unit owners, then a small public-API actual
guest sequence (cap1/cap2, SQL isolation, timeout, child capture, parent Close,
Live reset and existing cross-host roundtrip/resnapshot) on macOS arm64 and
Ubuntu x86_64; Python3.11/3.14 wrappers. Existing
platform CI/release owners should carry these cases; no new full resource matrix.
Add the D1 cap cases to its existing installed-entry runner/profile owners and
the existing tests/test_django_prepared_api.py, test_django_prepared_owners.py and
test_django_xdist_policy.py as appropriate. Use tests/test_owned_snapshot_unit.py's
real framed-control subprocess pattern for stuck-host controls, with an outer
test timeout so a missing watchdog fails CI instead of hanging its job. These
are future detector placements, not current coverage or a new framework matrix.
Extend the existing Python other-host tests with the parent-lock race, and
internal/live plus public-Go/internal/control adapter tests with a real limiter
for recovery. Range tests belong at both Python/API validation and control
field-decoding boundaries; retain one real-host SQL survival check for rejection.
Do not equate a controlled child cleanup failure with actual-engine fault injection.
Bind receipts to the tested candidate. Runtime cleanup failure injection remains
controlled-owner evidence; do not claim to reproduce real-engine OOM.

Completion: the fixed cases pass, Go/Python usage and errors are documented,
and user-visible behavior/limitations are in unreleased notes. Report unresolved
cases as unfinished; do not add performance requirements or #84 to this exit.
Integration and release follow their own decisions.

The original design-only task stopped at source inspection and this proposal,
with zero builds, runtime executions and CI submissions. The recommendation was the
256 MiB/quarter-memory default, unchanged proposed Live reservation behavior and
preserved cross-host handoff with leases. The finite automatic-default direction
is already decided. The Human subsequently authorized the concrete lifecycle/API
implementation; no further measurement is made a prerequisite by this proposal.
If lease implementation reveals an unowned late-outcome path, stop and report
that exact boundary instead of removing handoff or adding another campaign.
