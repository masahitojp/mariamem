# v0.5.0 boundary fixes and J1 decision

The two demonstrated converter boundary defects are repaired at their owners.
The bounded J1 comparison establishes a guest allocation-lifetime failure in
both the actual Wasm and its translated Go, not a newly demonstrated Go-only
Wasm violation. I recommend a limited completion/reclamation repair before
final Qualification. The investigation is complete within its agreed scope;
that repair is not implemented by this task.

## Scope and identity

Starting source: `446d24a463da976aeb1112af8e796f0b613c31ce`, following
[R1–R5](v050-semantic-audit.md) at
`ccd75706fae112f1cd811f426ba7ca7dbfc3fe8a`. Accepted runtime component:
`f66727dda49d1b4ca2c7e814e218587c051f7f97`. A–D and the earlier three fixes
remain the [integration](v050-ad-integration.md) and
[correctness](v050-correctness-fixes.md) evidence; this does not repeat them.
Work belongs to `experiment/v050-boundary-join`, not main.

The missing guest artifact was restored through the formal single-pass
development build from a clean source clone at the starting commit. Its Wasm
hash equals the accepted input; no new guest change was adopted. The build is
UNQUALIFIED and is not independent guest-build qualification. Fixed inputs,
patch order, converter binary, candidate inventory and generated identities are
in [identities](v050-boundary-join-evidence/identities.json),
[translation manifest](../../release/generated-go-translation.json),
[candidate inputs](../../release/generated-go-inputs.json), and
[canonical provenance](../../internal/generatedgo/provenance.json).

Canonical regeneration, with fresh external output paths and the checksum-bound
converter archive, uses these existing owners:

```sh
python3 scripts/build_generated_guest.py --development-output "$GUEST_DIR"
python3 benchmarks/spikes/generated-go-integration/translate_guest.py --guest "$GUEST_DIR/mariamem.wasm" --guest-sha256 "$GUEST_SHA" --converter-archive "$CONVERTER_ARCHIVE" --output "$TRANSLATION"
python3 benchmarks/spikes/generated-go-integration/setup_candidate.py --source-only --source-module "$TRANSLATION/module" --guest "$GUEST_DIR/mariamem.wasm" --input-manifest release/generated-go-translation.json --output "$CANDIDATE"
python3 scripts/generate_runtime.py --source-module "$CANDIDATE/module" --output "$GENERATED"
python3 scripts/regenerate_release_guest.py --guest-dir "$GUEST_DIR" --output "$INDEPENDENT"
python3 scripts/runtime_correctness/wait_thread_fixture.py --scope all --converter "$TRANSLATION/wasm2go" --output "$BOUNDARY_FIXTURE"
```

The guest build runs inside the pinned build environment documented in
[development](../development.md#single-pass-unqualified-guest-development),
not on an arbitrary host toolchain. Candidate adoption updates the checked-in
candidate inventory before installation; the final inventory is linked above.
The independent command rebuilds converter/translation from the archive and
checks every canonical file, including handwritten ownership files. Only base.go,
provenance and the two new owned tests differ from the starting canonical tree;
the [delta](v050-boundary-join-evidence/generated-delta.json) records their hashes.

## T1: positive timeout overflow

Owner commit `bec75c55aa0c42ee88e1df38123ae2f04e268e08` adds
`wait-timeout-range.patch`. The existing one-millisecond clock allowance now
saturates at the positive Go duration limit instead of wrapping a large positive
timeout into an already-expired timer. Negative waits, mismatch behavior and
notification semantics remain unchanged. A requested 292-year wait need not run
for centuries: the oracle checks that it remains parked and is then notified.

Both sides of `MaxInt64 - 1ms`, MaxInt64, negative/zero/short waits, notification,
mismatch and queue removal are covered. The real guest emits only wait32; its
owned tests also exercise the common timer with a 64-bit comparison. The actual
opcode fixture emits wait32 and wait64 and verifies their generated wrappers.
The original R3 failure oracle is retained unchanged. The initial canonical
test wrongly referenced an absent wait64 wrapper; the test ownership/layout was
corrected without removing width coverage or changing runtime behavior.

## T2: bounded thread IDs

Owner commit `be61d940e4c5b8b81b5ed1a73561d00fef76831c` adds
`thread-id-range.patch`. CAS allocation returns IDs in `[1, 2^29)` and rejects
exhaustion before adding or launching a worker. It does not recycle IDs or reset
the contention marker. Negative/reserved/overflow states, the final valid ID,
concurrent allocation, unique IDs, child execution counts and missing entry are
tested. The original R4 failure oracle is retained unchanged. This prevents a
failed spawn from racing the guest's allocation cleanup at exhausted IDs.

## J1: allocation is reused before the last result store

The pinned WASIX `pthread_create.c` places stack, TLS and pthread metadata in
the same malloc-owned map. `pthread_join.c` frees `pthread+40` map_base after
detach_state (`pthread+28`) and the thread-list lock permit completion.
The optimized guest clears list lock `15243132`, then may call Fn89 to wake
list waiters. Fn89 uses a byte on the exiting agent's guest stack; the host wake
writes that byte after notification. Completion/list publication therefore
precedes a possible last access to the allocation being joined and freed.

[Actual Wasm decoding](v050-boundary-join-evidence/j1-decoded.json) binds those
instructions to function body hashes. Fn217's original body hash is
`2c2e86f9fe87447850299dbb1a91deded11881f1b273b44d722b173231dacf5b`.
The [Go slice identities](v050-boundary-join-evidence/j1-go-identities.json)
cover its unmodified allocator/join/unlock closure. The saved probe uses the
pre-T1/T2 canonical base; the guest functions and wake adapter are unchanged by
those fixes. This is explicitly a component identity, not the new whole-source
qualification. The [reproduction recipe](../../benchmarks/spikes/v050-join-check/README.md)
explains the intervention and controls.

Concrete schedule, valid even with sequentially consistent accesses:

1. The exiting agent clears the list lock and enters the wake import.
2. Before wake writes its result byte, another actor runs the actual fast join,
   actual free and actual malloc. Malloc returns that same allocation.
3. A byte in the replacement allocation is set to 165.
4. The exiting actor's wake stores 1 there, changing the replacement byte.

Observed map/reused pointer: `268435472`; result address: `268693519`, inside
the 262144-byte map. Original Wasm and translated Go both produce 165 → 1.
Deferring reclamation until unlock returns, or omitting the post-unlock wake,
preserves 165. [Results](v050-boundary-join-evidence/j1-results.json) and
[original Wasm receipt](v050-boundary-join-evidence/j1-original.json) separate
the failing lifetime oracle from successful reproduction of that failure.

### What this does and does not establish

- **Confirmed:** the actual allocator/join/unlock bodies permit premature reuse
  under the forced import schedule, and a later write changes a replacement byte.
  Heap and production mmap backing show the same value; normal and race runs
  each fail the lifetime oracle and pass both controls.
- **Normal use:** resident Start/use/Close statically reaches exit/join; bare
  Start/Close does not necessarily join resident workers. Existing normal
  functional checks are separate evidence. This probe seeds metadata and waiter
  state rather than running an entire natural SQL shutdown. It does not confirm
  how often that particular branch/schedule occurs in normal use.
- **User consequence:** premature reuse could cause cleanup-state corruption,
  intermittent Close failure/hang or test failure. A complete SQL failure,
  natural-schedule crash, frequency and cross-DB corruption are **not reproduced**.
- **Observation:** the forced callback itself selects the interleaving. No
  unchanged-host natural trace is claimed. There is no newly demonstrated
  Go-only outcome forbidden by the original optimized Wasm plus this host ABI.
- **Detector limit:** these forced schedules are serialized; all four Go runs
  report zero races. That supplies no concurrent-safety argument. Existing heap,
  mmap and assembly observation limits remain in force.

J1a allocation/last-access and J1b actual-body comparison are COMPLETE. J1c
natural-scenario tracing is NOT PERFORMED: it was conditional, and the paired
actual-body lifetime counterexample already decides whether a reclamation
repair is required. It must not be labelled a native PASS. No scope was reduced.
The scoped confirmation finished inside its three-hour cap; elapsed budget is
not used as evidence of completion. [Timing](v050-boundary-join-evidence/timing.json).

## Recommended bounded repair and stopping condition

I recommend **limited lifetime repair**, not present acceptance or another whole
access census. Allocation reclamation must wait for the agent's last guest/host
memory access, rather than just detach_state/list-lock publication. A publication
fence or atomic join load cannot fix an access which intentionally occurs later.
Moving the host result store before notify alone also misses the earlier guest
stack store in Fn89. Retaining every worker allocation until DB Close would add
unbounded per-DB retention and is not an adopted remedy.

The next design should choose a completion event owned by the worker lifetime,
and bind reclamation of the exact stack/TLS map to it. A bounded candidate is
a host completion lease keyed to the worker allocation, with a guest reclaim
handoff; foreign join waits before allocator locking, detached self-reclaim is
deferred until agent completion, and reused addresses receive new lease identities.
Alternatively implement that handshake in the pinned guest/sysroot owner.
These are design candidates, **not implemented or proven safe here**. Validate
the exact ABI/allocation binding before selecting either owner; do not intercept
all frees indiscriminately or edit generated Go. Public APIs and Snapshot checks
stay intact. A changed guest requires new guest/Snapshot identities.

Acceptance is finite: the existing paired early-free oracle must reject
premature reuse and accept both completed/reclaim controls; add normal and
already-exited join, delayed wake, detached self-exit, panic/failed-start cleanup,
concurrent joins, allocator-lock deadlock and address-reuse checks. Then canonical
generation/independent identity and normal lifecycle acceptance must pass.
No whole-Wasm proof or unrelated mmap redesign is a prerequisite.

Estimate remains **4–8 additional engineer-hours**, not a completed-work claim:
2–4 for the limited owner design/implementation and decisive protocol oracles,
2–4 for affected build/regeneration/lifecycle checks, excluding final Release CI
and Product Validation. The design/repair needs its own review because this task
authorized conditional confirmation, not a new completion protocol. The earlier
decision already specified repair if a shared lifetime violation was found;
that condition is now met, rather than a newly invented fourth investigation.

The strongest objection is that the original Wasm behaves identically and no
natural SQL harm is reproduced. That limits any converter-incompatibility claim
and any assertion about failure probability. It does not make premature reuse
safe. Therefore T1/T2 success alone is not my recommendation to proceed to final
Qualification. This is an engineering judgment for the current candidate, not
a claim that the product is unsuitable for development.

## Verification and handoff

The [verification receipt](v050-boundary-join-evidence/verification.json) owns
PASS/FAIL/SKIP and normalized evidence hashes. Mac execution is on macOS27 arm64,
Go1.26.8/Python3.14; it is not macOS15 minimum-OS qualification. Ubuntu native
execution is SKIP (not available here). General shared-memory conformance,
natural SQL harm/frequency, final Qualification and Product Validation are not
claimed. Original failure oracles, source verification and license guards remain
unchanged. Guest identity is unchanged, so no new Snapshot migration is introduced.

This handoff stops before a J1 production repair, final Qualification or release.
There is no main merge/push, tag, publication or RELEASE READY judgment.
