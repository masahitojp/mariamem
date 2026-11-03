# Issue #53 — implementation checkpoint

The Human authorized implementing the reviewed design on 2026-11-03 after
`a4929d1234068eead0faf6034b5d2e4b27e58b31`. This checkpoint implements the shared
primitives. **It does not yet enforce a public Snapshot Fork limit.**
[Issue #53](https://github.com/masahitojp/mariamem/issues/53) owns completion;
[the fixed acceptance table](issue53-fork-limit-design.md#fixed-acceptance-and-stopping-point)
is unchanged. No acceptance row covering a real entry is marked complete here.

## Implemented boundary

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

## Ownership audit: exact next boundary

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

## Verification

Source starting point was inspected with `scripts/git_identity.py inspect HEAD`:
object_type=commit, source_commit=`a4929d1234068eead0faf6034b5d2e4b27e58b31`.
Tests below apply to the subsequent implementation diff, not to that unchanged
source commit. No benchmark or release receipt is issued.

- macOS arm64, Go1.26.10: `go test -race ./internal/forklimit` passed. Tests cover
  cap1/2 contention, actual blocked-wait wakeup, cancel, Close/recovery races,
  retained cleanup debt, duplicate settlement, input bounds and sizing fixtures.
- Linux amd64 test binary cross-compiles with Go1.26.10. This is **not** Ubuntu
  runtime acceptance; Linux cgroup fixtures also run on the macOS test host.
- Python3.14: the 40 focused validator cases passed. No public API, host-control
  survival, stuck-pipe or installed-entry claim follows from these pure tests.
- Publication allowlist check passed. Existing Go/Python DB/Live source smoke
  passed; since the new primitives are unconnected, this is regression smoke,
  not #53 runtime acceptance.
- Daily Go tests and vet passed. The first Python-wide invocation used an
  incomplete task venv and a dirty checkout; dependency/clean-source prerequisites
  must be satisfied before rerunning the canonical check. No broad PASS claim
  is made from that attempt. Both-platform #53 acceptance remains outstanding.

No guest/WASM patch, generated source, version or release ledger changed. The
original checkout's unrelated user modifications are preserved in place.
