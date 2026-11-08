# Issue130 — bounded public lifetime fixture slice

Question: can the existing C2 public native owner boundary detect separate real
worker and host relay holds, retain typed late disposal, and keep capture debt
on its original parent after physical cleanup? This supports Issue65's objective
of reducing MariaDB update work without weakening owner/failure/join contracts.

Base source_commit: a5ee1ed9cc2c6932d317fba77c339b364acd48df.
Read inputs: current #65/#130 bodies (2026-11-08), project-status, C1/C2 tests,
P1-a native worker/relay barriers and public-backend.md detection table.

Budget: 2h active, including <=30min additive observer tooling; heavy CI0,
guest builds0, benchmarks0. Environment: macOS arm64, Python3.14, focused host
Go unit/race/vet only. Exit: additive staged public-path fixtures, deterministic
host owner checks, source identity, exact missing runtime inputs and bounded
result report. Inconclusive: preserve fixtures and report unexecuted native
assertions; do not claim #130, C3 or update-cost acceptance.

The staging observer is test-only and must never enter canonical generation.
No historical fixture, guest patch or Issue129 fixture is changed. It installs
onto a separate, already prepared C2 product copy. Real native execution is
explicitly deferred to the shared artifact / Issue132 cohort.

## Implementation and evidence boundaries

Only `internal/control/native_owner_test.go` changes in normal host sources.
Its two new tests use synthetic services: late worker join + portable log-remove
failure retain the lease and original Close result; permanent capture debt keeps
exactly its parent lease after physical cleanup, sibling retirement and retry,
while an independent parent remains usable. The original test/assertions remain.

`overlay.py` is an additive test artifact installer, not a product factory
change. It checks a fixed C2 public source receipt, complete before-inventory,
exact C2 factory and three host preimages, rejects existing fixture targets and
symlinks, and records a new inventory with `runtime_executed=false`. It modifies
only a separate product copy, never generated function bodies. Hooks attach per
instance before runner/relay startup; relay holds run outside the owner lock.
The one-shot factory registration is only for sequential acceptance tests.

| Added staged fixture | What execution would establish | This wave |
| --- | --- | --- |
| `TestIssue130PublicSeparateJoins/{worker,reader,writer}` | ordinary public Go Start/Pipe + real timeout; existing pthread completion seam or each relay held separately; immediate owner cause and connection loss, independent PING; Active1 and unfinished Done/disposal until join; shutdown deadline, typed owner/temp retention, late removal and stable Close/cause | type-checked, **not executed with guest** |
| `TestIssue130NativeControlWorkerAndLateLogFailure` | Python management boundary with real worker hold; immediate Status, late join and log-remove failure; typed owner and stable Close after retry | type-checked, **not executed with guest**; installed Python serialization is separate |
| `TestIssue130PublicPermanentDebtIsolation` | actual public Snapshot/Fork/capture, then injected host OwnRoot build-identity mismatch; physical join cannot forgive original parent's lease; sibling and independent parent remain usable, closed parent stays closed | type-checked, **not executed with guest**; host fault injection, not a guest trap/unmap failure |
| `TestIssue130PublicFinalFenceDespiteIdleCache` | force host STATE cache idle, actual transaction still rejects public Snapshot nonconsumingly via guest fence; ROLLBACK and owner remain usable | type-checked, **not executed with guest** |
| `TestIssue130HookOwnRootFailure`, `TestIssue130HookRelayHold` | hook placement, typed relay disposal and post-capture debt path with a private-frame fake peer | race PASS; **synthetic unit evidence only** |

The fixture type check used a temporary `generatedgo.StartWireInstance` adapter
stub that panics if called and `go test -run '^$'`; no fixture was run against that
stub. The real staged factory requires the existing P1-b `WireLifecycle` adapter
and completion instrumentation. The compile-only stub/temporary overlays are not
installed by `overlay.py` and are removed after checking.

## Negative controls

Existing C1 `mutations.py` ran unchanged, with new logs saved under
[evidence/core-controls](evidence/core-controls/mutations.json): early Done,
dropped startup typed owner, fixed five-second duration, forgiven capture
rejection and overwritten first cause were all detected by their original
synthetic-core tests. These are not actual-public negative-control results.

For the shared runtime cohort, pair the new fixtures with these exact faults:

- `Backend.Done` returning `executionDone`: the reader/writer subcases must fail
  while their host relay is still held; the real-worker case is a distinct hold.
- In `Backend.Close`, replace its pending `disposal.Retain(cause, err, r.disposer)`
  with `errors.Join(cause, err)`: public typed-owner/temp assertions and control
  typed-owner/log assertions must fail. Test the startup Retain separately using
  the existing startup oracle; this slice adds no actual-public startup injector.
- Bypass `SnapshotHeap`'s `rpcContext(...kindCaptureFence...)` with a fabricated
  FENCED reply: forced-idle-cache transaction rejection must fail. A changed
  rejection predicate alone is a weaker, separately labelled core control.
- Omit captureDebt propagation into Go/control owners or clear it after physical
  cleanup: permanent parent debt/isolation assertions must fail. The old parent
  debt assertions remain, and their source must not be changed to make this pass.

These real-public mutations are specified but **unexecuted** in this wave.

## Shared artifact and hook handoff

No new guest is needed for this fixture preparation. Later execution needs:

1. A separate copy of the clean/inventoried C2 public product and its
   `public-source.json` (`contract=issue65-public-unqualified`). Guest SHA256
   `d4f30818c3410db186db5ef1c9abc5f14af0cdc52bb2b76bbca369e02eb1b481`, guest and
   installer source_commit `be244a0bdb510a22417241c2aa2f76a9093aac1b`; checked
   translation/input manifest, worker-binding identity and complete Go/assembly/
   data inventory. No tag object is a source_commit. The #127 builder owns heavy
   work; no artifact was borrowed or claimed checked by this slice.
2. Existing `runtime_wire.go` with `WireLifecycle.BeforeWorkerComplete` and
   `base.SetNativeCompletionProbe` from the P1-b completion/lifetime overlay.
   The new factory wires that real per-pthread seam; host Reader/Writer hooks
   are added solely to the disposable core. All original C2 fixtures/tripwires
   stay installed. No new guest ABI or worker binding is proposed.
3. Run `overlay.py --product COPY --source-receipt PUBLIC_SOURCE_JSON
   --output-receipt NEW_JSON` from this committed observer source. Keep the new
   receipt outside COPY. The installer performs no build/run/gofmt; its exact
   output bytes are inventoried. Compare that inventory before/after later
   build/run. Original guest receipt remains unchanged. Run staged root tests
   `go test -run '^TestIssue130Public' -count=1 -timeout=5m .` and control test
   `go test -run '^TestIssue130NativeControl' -count=1 -timeout=2m ./internal/control`.
4. Rebind #129 source_commit `3c47dfbcd3b44691e99cbcf2fe3b1b1d042b049c`
   settings fixtures and these faults to the same #132 candidate, on macOS and
   Linux. If #127/#131 changes any hook preimage or runtime contract, review and
   adapt the overlay explicitly; a preimage mismatch is not permission to
   relabel old PASS. Preserve old fixture expected/actual/pass records.

Still missing: actual-public startup cancellation/failure + late worker/log
composition; actual control permanent-debt injection through its request
protocol; installed Python owner/error/log/cleanup behavior with these holds;
actual-public negative controls; both-OS execution, original oracle rebinding,
final shared candidate inventory. Python needs a test-only host driver/IPC
barrier bridge to install/release per-instance hooks across the process boundary;
Go globals alone cannot configure an installed Python host. That is additive
acceptance tooling, not a proposed production management API. No claim of #130,
C3, update-cost improvement, adoption or release completion follows here.

## Local verification and cleanup

[Checks and source hashes](evidence/checks.json) record focused deterministic
Go/control/host units (three repeats), core/disposal/forklimit race (three
repeats), staged synthetic-hook race (three repeats), focused vet, four Python
source-tool tests, touched Python compile checks and compile-only fixture typing.
The host race attempt was stopped (exit130) when it started recompiling unchanged
generated runtime packages; it is not a PASS. The initial normal host test
compilation likewise compiled existing dependencies but built no staged runtime
artifact and executed no guest workload.

The full public-source check still fails on the same six historical evidence
files listed in checks.json. They are preserved. The
[changed-source subset](evidence/changed-public-source.json) passes, and the
original control debt test's assertions are preserved byte-for-byte.

Work stayed within the 2h active / 30min tooling ceilings (elapsed wall time and
active/tooling estimates are reported in handoff, not treated as measurements).
Owned temporary Go source overlays/compile stub and new Python bytecode are
removed after verification. Go's existing shared compiler cache is not owned by
this slice and is preserved. Initial worktree status was clean; root4 user state
was never edited. The coordinator owns the Orca worktree lifecycle.
