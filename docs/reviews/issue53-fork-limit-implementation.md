# Issue #53 — implementation checkpoints

The Human authorized implementing the reviewed design on 2026-11-03 after
`a4929d1234068eead0faf6034b5d2e4b27e58b31`. The first checkpoint implements shared
primitives; the next adds reachable cleanup ownership through the existing host
lifecycle. The current checkpoint connects public Go entries. **Shared-control
and Python limit enforcement remain unfinished.**
[Issue #53](https://github.com/masahitojp/mariamem/issues/53) owns completion;
[the fixed acceptance table](issue53-fork-limit-design.md#fixed-acceptance-and-stopping-point)
is unchanged. No acceptance row covering a real entry is marked complete here.

## Current checkpoint — public Go limits

The Human requested continuing with a user-visible cap1 Fork wait/release path.
Implementation starts from inspected commit
`68d768550e7c8fb743e8eb3790082c4a23efc3d1`.

- Go exposes `SnapshotOptions.MaxForks` and immutable `Snapshot.MaxForks()`.
  Zero resolves auto at capture; explicit1..MaxInt32 overrides it. Invalid values
  reject before consuming the source. Capacity waiting precedes the backing lock,
  and parent Close revokes unused reservations and wakes waiters before joining
  admitted startup. Successful child lifetime stays independent of parent Close.
- A child owns its lease before the runtime watcher starts. Close, unexpected
  exit and consumed capture settle only after disposal. Preserved capture retains
  occupancy. Unknown or partial cleanup stops parent admission; no `consumed`
  flag or error string serves as a disposal proof.
- Live requires cap>=2, reserves nonblockingly before healthy drain, and preserves
  data/generation on capacity busy. Explicit Reset retries pending/current-child
  cleanup before recovery when failed, then atomically checks all debt and takes
  a slot. Another owner's unresolved cleanup and parent Close prevent recovery.
  A failed startup with delayed disposal supplies a retained cleanup-only child.
- Go fixture default2 stays intact; its configured cap now reaches the private
  Snapshot, maintaining the outer SQL-owner/inner DB lease relationship. Go HTTP
  config adds a cap override and rejects explicit1 before preparation.

Focused Go race tests passed for public Go, `internal/live`, `internal/forklimit`
and `mariamemtest`. Added tests cover public wait cancellation, parent Close,
consumed/preserved behavior, outer/inner cap propagation, cap2 Live busy/drain
reservation return, two failed disposals followed by retry, and another owner's
debt. Controlled cleanup failure evidence is distinguished from actual guest faults.
The existing Go source/installed consumer now includes actual cap1 wait/release,
timeout survival, parent Close with a live child and recapture, plus Live's spare
slot busy path. Its runtime result is recorded after the code commit.

Remaining work is the shared-control protocol and Python together, then supplied
Python fixtures/E2E/D1 and both-host fixed acceptance. The old Python handoff has
no source-lease acknowledgement; enabling that host-side limit alone would strand
capacity when a remote child closes. Keep these changes in the same subsequent
integration slice instead of adding an unlimited bypass or shipping a half-bound
handoff. No entry/acceptance case is removed and no new approval gate is added.

## Previous checkpoint — late cleanup ownership

After the first checkpoint, the Human requested continuing with the identified
startup/consumed-capture cleanup boundary. Implementation starts from inspected
commit `c810e194aa855a7e521a73a163e10d83e8bda945`. That earlier checkpoint passed
[Development CI41648322854](https://github.com/masahitojp/mariamem/actions/runs/41648322854)
(`check`, `integration`, `Live required gate`); this run is not evidence for the
new lifecycle changes below.

- `internal/disposal` separates an operation's error from its cleanup owner.
  Wrappers/joins preserve the owner and original cause. Successful cleanup does
  not rewrite the failed operation or an already stored public Close result.
- A failed framed greeting can still return nil Process, but its error now owns
  the unresolved join. One continuation per cleanup owner follows late completion;
  it does not poll, repeatedly retry filesystem failures or kill a shared host.
  Failed removal retains an owner for explicit retry.
- Host startup holds borrowed restore backing until cleanup completes. Transfer
  removal waits for execution/session completion, and Close/consumed capture use
  the same retry owner. Worker join has one waiter per Server rather than one
  per disposal retry. Imported temporary backing closes after pending startup
  cleanup, avoiding a blocking deferred Close while the borrow is still held.
- Public Go and shared-host lifecycle wrappers retain temporary/log cleanup in
  the correct order. A private Live log is removed on startup failure only after
  that call successfully created it. Post-start failure no longer discards the
  child's cleanup error. A failed control operation with an unpublished created
  handle disposes that handle before returning its error reply.
- `Lease.TrackCleanup` holds capacity until all typed owners confirm completion.
  One watcher belongs to a lease, even across duplicate reports. Unknown untyped
  cleanup remains blocked; strings never prove disposal. Confirmed late cleanup
  settles the lease but still requires explicit admission recovery.
- Internal nonblocking cleanup probes use a distinct pending condition so they
  do not add a spurious caller cancellation/timeout to the original diagnostic.

Focused Go1.26.10 macOS arm64 race tests passed for `internal/disposal`,
`internal/forklimit`, `internal/guest`, `internal/host`, `internal/control` and
the public Go package. New controlled cases cover a real framed greeting with
late completion, guest/session joins held separately, failed/retried removal,
parallel retry serialization, retained cap1 capacity, unchanged capture/Close
failure results and unpublished-handle cleanup. These are controlled lifecycle
faults, **not reproduction of an actual-engine hang or filesystem fault**.
On 2026-11-04, clean inspected commit
`c62fc38f2e8b784e104172d59d42aab2013004db` passed the canonical daily check:
67 source tests, Go daily tests/vet, 1808 Python tests plus 100 subtests; 85
opt-in/optional tests skipped. The same commit passed Go/Python real DB/Live
source smoke (capture, reset, busy/closed-parent rejection, host reap and
directory removal). Go1.26.10, macOS arm64 and Python3.14 with the repository's
unit requirements were used. These are local source checks, not Ubuntu/macOS15
qualification or full #53 acceptance. The subsequent commit only records these
results; it does not relabel the earlier `c810e194` CI receipt.

The previous inaccessible-cleanup-owner boundary is addressed. The next work is
to wire public Go Snapshot/Live and the shared-control reservation protocol,
then Python's finite send/reply watchdog, handoff and supplied entries. No
`fork-limit-v1` capability or public `max_forks` entry is advertised yet. The
full fixed acceptance table, including both hosts, is still required; no new
performance requirement or Human approval gate is added here.

## First checkpoint — implemented boundary

- `internal/forklimit`: finite immutable capacity, cancellable acquisition,
  nonblocking reservation, activation before allocation/export, Close wakeup
  and revocation of unused reservations. Active children retain their lease.
- Cleanup uncertainty retains occupancy, preserves its cause and stops admission.
  Confirmed settlement clears only its own debt. Explicit recovery checks all
  remaining debt and reserves atomically; normal disposal never resumes admission.
  Duplicate settlement does not release another lease. Storage grows with actual
  outstanding leases, not the configured maximum or lifetime Fork count.
- One-time sizing uses the minimum observed physical/cgroup/runtime memory limit,
  quarter-memory / 256 MiB, finite GOMAXPROCS fallback and MaxInt32 clamp. Linux
  membership and mount-root resolution includes visible cgroup ancestors. Hidden
  namespace ancestors cannot be observed. No free-memory or CPU-optimal claim.
- Go request-field parsers and Python's private `_forklimit` validators share
  MaxInt32 capacity and the new wait-time bound. Python rejects huge integers
  before conversion; positive subnanosecond waits serialize as `1ns`. Raw JSON
  parsers are intended for request-local use, not the fatal framing decoder.

The code is deliberately not connected to Snapshot, shared control, Python public
methods, Live, fixtures or D1 yet. In particular, the control host does not yet
advertise `fork-limit-v1`. Validator tests are not proof that bad new fields
preserve sibling SQL in a real host. Those integration cases remain required.

## First checkpoint ownership audit (historical; addressed above)

The design requires reporting an unowned late outcome before wiring the limiter.
Source inspection at the design base found this concrete path:

1. `internal/guest/linked.go`, `ConnectWithFailure`: failed ready/timeout calls
   `AbortAndWait`, then returns **nil Process + error**.
2. `internal/guest/guest.go`, `AbortAndWait`: after ten seconds without `p.done`,
   it returns an error string saying cleanup timed out. It does not provide the
   caller with a typed unresolved owner/completion outcome.
3. `internal/host/server.go`, `start`: on that error, it removes transfer scratch
   (ignoring removal failure) and returns nil Server. The public/shared-control
   callers therefore cannot distinguish joined disposal from a still-running
   linked execution when deciding whether to release a newly reserved slot.

The guest completion goroutine still retains its Process internally. This is
not evidence that its execution was abandoned by every goroutine or that an
actual engine hung. The missing owner is the **admission layer's accessible
completion/cleanup owner**. No error-message parsing or assumed slot return is
acceptable. `SnapshotHeap` also returns consumed=true on failed finish; consumed
alone cannot serve as a disposal oracle.

Recommendation for the next bounded implementation slice: preserve a private
typed cleanup owner/outcome through startup and consumed capture, including
transfer-directory disposal. Keep a failed startup's lease until that owner
confirms joined disposal. Keep the original operation failure even when later
cleanup succeeds. Test late completion and failed/retried removal with controlled
owners, then connect public Go and shared-control adapters to the same primitive.
This is already within the approved ownership work, not a new performance study
or permission to change the guest/WASM engine. No handoff removal, speculative
release, host kill or acceptance reduction is proposed.

## First checkpoint verification (historical)

Source starting point was inspected with `scripts/git_identity.py inspect HEAD`:
object_type=commit, source_commit=`a4929d1234068eead0faf6034b5d2e4b27e58b31`.
Tests below apply to the subsequent implementation diff, not to that unchanged
source commit. No benchmark or release receipt is issued.

- macOS arm64, Go1.26.10: `go test -race ./internal/forklimit` passed, including
  the final correction at `3c1dee3e232dbd986eac04ed9cde7999d46d9c87`. Tests cover
  cap1/2 contention, actual blocked-wait wakeup, cancel, Close/recovery races,
  retained cleanup debt, duplicate settlement, input bounds and sizing fixtures.
- The initial foundation's Linux amd64 test binary cross-compiled with Go1.26.10,
  before the final cleanup-cause discrimination correction. This is **not** Ubuntu
  runtime acceptance; Linux cgroup fixtures also run on the macOS test host.
- Python3.14: the 40 focused validator cases passed. No public API, host-control
  survival, stuck-pipe or installed-entry claim follows from these pure tests.
- Publication allowlist check passed. Existing Go/Python DB/Live source smoke
  passed; since the new primitives are unconnected, this is regression smoke,
  not #53 runtime acceptance.
- Daily check completed after installing the repository's unit requirements:
  67 source checks, Go daily package tests/vet, 1808 Python tests plus 100 subtests
  passed; 85 opt-in/optional tests skipped. Python3.14 / pytest9.2.0,
  xdist3.8.0 / PyMySQL1.2.3 / SQLAlchemy2.0.54. The earlier incomplete-venv/dirty-tree
  attempts failed and are not acceptance evidence.
- That daily invocation started at `5330cf4c4fb14334e51ec544b408788034357f5d`.
  During its Python phase, `3c1dee3e` changed only the new Go pool and its tests;
  the final pool race test was rerun separately. This is layered local checking,
  **not an exact-head CI receipt**. Both-platform #53 acceptance is outstanding.

The final correction uses the pool's direct full sentinel to decide whether to
wait. A cleanup cause that wraps the same sentinel must still return cleanup
failure immediately. A regression test checks that it does not wait to deadline.

No guest/WASM patch, generated source, version or release ledger changed. The
original checkout's unrelated user modifications are preserved in place.
