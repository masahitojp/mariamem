# v0.5.0 J1 worker allocation completion repair

The Human authorized J1 repair after reviewing the paired original-Wasm/Go
counterexample at `8086d902d97ffe3d65326658ff45cab9540a737a`. The implementation
binds guest worker-map reclamation to the worker's final guest/host memory access.
The existing lifetime oracle now passes; it remains failing without the owner.
This is a candidate repair, not release approval or general Wasm conformance.

## Owners, input and changes

Guest MariaDB12.3.3 Wasm stays
`7c7b6ce5168a1a0d98019751b4c36c25f2e9948dbae0124ec3f434efb0b8642c`.
It was restored by the formal single-pass development build from the clean
baseline clone; linked Wasm and toolchain identities are unchanged. The build
receipt remains UNQUALIFIED. Goccy
`730057c146463f663e8774587bc96fb2bea91af8`, all 13 ordered converter patches,
raw translation/candidate source and initial data identities are unchanged.
No SDK, guest patch, dependency version, public API, platform or minimum Go
version changes. Existing Snapshot guest identity/rejection rules stay intact;
this runtime-only repair does not require recreating accepted guest Snapshots.

- [Installer adapter](../../scripts/runtime_thread_lifetime.py) pins the guest,
  required files and normalized full function bodies of Fn216 (entry ABI),
  Fn153 (dlfree) and Fn131 (its only callee). It adds one private Module field
  and a free handoff at the first instruction of Fn153, before allocator locks.
  Missing/changed inputs and repeated installation are rejected.
- [Completion owner](../../internal/generatedgo/code/base/thread_lifetime.go)
  records exact worker map-base allocations per DB. Entry reads accepted
  start_args+16 → pthread, then pthread+40/+44 → map base/size. Creation writes
  precede Go worker publication; map fields are immutable during that lifetime.
  A zero map base is caller-owned storage, not a malloc-owned allocation.
- [Production binding](../../internal/generatedgo/runtime_thread_lifetime.go)
  installs before root execution in the existing memory constructors. The
  original guest entry remains the delegate. Raw reclaim uses the pinned Fn153.
- [Generator](../../scripts/generate_runtime.py) owns both generated edits and
  explicit handwritten inclusion. Generated Go was never hand-edited. Only
  base.go, p3_pure.go and provenance change in translated output; new completion
  files and constructor changes remain handwritten owners.

The source [allocation/last-use evidence](v050-boundary-join-fixes.md#j1-allocation-is-reused-before-the-last-result-store)
and original failure classification remain historical. A map-size field is a
source ABI quantity, not a promise about guard-byte reservation or storage.
Registration checks logical bounds and uses the exact malloc base for identity;
it does not infer a neighboring object's ownership from that size.

## Lifetime argument and exceptional paths

1. The wrapper registers ownership before calling the original entry. A valid
   guest join cannot reach the completion/free path before that entry publishes
   its completion state. Failed spawn registers nothing and launches nothing.
2. Foreign free looks up that allocation generation and waits for its done
   channel. No registry or guest allocator lock is held across the wait. The
   guest fast join's earlier flags therefore cannot permit premature reuse.
3. Done is closed by the outer entry wrapper after the delegate and all its
   defers finish, including panic and Goexit unwinding. Remaining ThreadLaunch
   bookkeeping touches Go state, not linear memory. Whole backing retirement
   still joins the existing worker group before unmapping.
4. A detached self-free records a deferred request instead of waiting for itself
   or freeing its live stack/TLS. The outer wrapper performs the raw reclaim
   after the last guest access, then closes completion. Reclaim completes before
   the worker group reports completion. Allocator failure remains a worker trap.
5. Fn153 does not access guest stack/TLS itself. Its only callee, Fn131, can write
   TLS on a yield error. The late reclaimer therefore uses an owned infallible
   `runtime.Gosched` yield with no linear-memory access, matching production
   WASI's current yield behavior. Other imports retain their delegate; a changed
   reclaimer call closure is rejected by the source pins. This avoids relying on
   a still-live TLS error slot after self-reclaim.
6. A retiring generation is removed before actual free, so a reused address can
   register a new generation. Completion/waiters retain the old allocation
   object, not just its address. A stale/duplicate pending reclaim fails closed
   rather than deleting a newly registered generation. Concurrent joins of
   different allocations are supported; invalid duplicate ownership is not
   turned into a new pthread double-join guarantee.

Registry entries last until guest reclamation, not indefinitely until DB Close.
State scales with unreclaimed worker maps, not cumulative launches. Completed
but unjoined pthread allocations already remain guest-owned. Root/worker failures
keep existing cooperative drain; this does not add forced worker termination.

## Decisive before/after oracle and observation limits

The [fixture](../../benchmarks/spikes/v050-join-lifetime/README.md) packages the
actual malloc/join/unlock/free closure and verifies canonical provenance. It
seeds the same allocation/thread/waiter state as the prior counterexample and
pauses wake before the final result-byte store. The worker runs through real
ThreadSpawn and the completion wrapper; join/free use the actual guest functions.

Without the owner, actual join/free/malloc reuse occurs while wake is paused:
replacement byte 165 becomes 1 when wake resumes. With the owner, the actual
pre-allocator handoff waits; wake finishes, the worker exits, and only then does
free/malloc reuse occur. The same final oracle preserves 165. Both controls
(already completed and no post-unlock wake) also preserve 165. Detached self-free
reclaims exactly once after its final result store. Heap/mmap, normal/race results
are in the [receipts](v050-join-lifetime-evidence/verification.json).

The fixture observes the blocked Go handoff with runtime.Stack, and uses a
disposable host wake callback to choose the schedule. These are isolated
actual-function fixtures, not a natural SQL failure-frequency study. Production
has neither observer. Unchanged-host full-guest integration is separate evidence.
Value preservation and event/ownership arguments are the correctness evidence;
zero race reports, particularly on mmap/assembly or constrained schedules, are
not a general safety proof. No full-guest race census is performed.

The original standalone Wasm and unmanaged host remain unchanged; this repair
corrects the supported Generated-Go runtime's worker allocation contract. It
adds completion ordering and delays deallocation; it does not manufacture a
claim that the earlier failure was introduced by wasm2go.

## Canonical generation and verification

Use the [previous exact-input recipe](v050-boundary-join-fixes.md#scope-and-identity)
for guest build, translation and candidate setup. Then:

```sh
python3 scripts/generate_runtime.py --source-module "$CANDIDATE/module" --output "$GENERATED"
python3 scripts/regenerate_release_guest.py --guest-dir "$GUEST_DIR" --output "$INDEPENDENT"
python3 scripts/verify.py check
python3 scripts/verify.py integration
python3 benchmarks/spikes/v050-join-lifetime/package.py --output "$PROBE"
```

Fresh outputs are required. The independent route rebuilds converter/translation
from the checksum-bound archive and compares every generated/handwritten file.
Existing source/license/provenance assertions are retained. The ownership-copy
test was updated with the required checked ABI preimages instead of its former
generic dummy input; none of its inclusion assertions or input guards is disabled.

[Identities](v050-join-lifetime-evidence/identities.json),
[independent inventory](v050-join-lifetime-evidence/independent-regeneration.json),
[generated delta](v050-join-lifetime-evidence/generated-delta.json), and
[per-check evidence](v050-join-lifetime-evidence/verification.json) bind the result.

Native execution here is macOS27 arm64/Go1.26.8. New native Ubuntu and macOS15
minimum-OS qualification are SKIP, not inherited PASS. Ordinary integration
covers SQL/transaction, concurrent connections/independent DBs, normal Close,
Snapshot/Fork and Python lifecycle; final consumer/platform qualification and
Product Validation remain subsequent work. Neither is invoked here.

## Current disposition and next decision

J1 repair and scoped verification close the last identified corrective item in
the agreed R1–R5/current-guest investigation. The original question has a bounded
positive implementation judgment after T1/T2/J1: no outstanding identified
Wasm→Go access/ownership correction remains in that contract. This does not
claim every possible Wasm program, future compiler or schedule has been tested.
No new whole-guest investigation is recommended on the same inputs.

Recommendation: adopt this candidate and proceed to the already planned final
Qualification and Product Validation. Release approval remains a later decision.
The main objection is extra registry lookup/synchronization on allocator calls
and changed reclamation timing. Functional/lifetime checks pass; throughput and
resource costs have not been measured. Product Validation must assess that cost
on the final configuration. Non-cooperative workers still cannot be forcibly
reclaimed, and race-detector observation limits remain unchanged.

If a subsequent check finds a concrete failure, identify its owner and bounded
remedy rather than silently reopening general safety investigation. Main is not
merged/pushed, no tag or publication is performed, and RELEASE READY is not
asserted by this local handoff.
