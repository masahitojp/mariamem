# v0.5.0 J1 completion/reclamation decision detail

Decision basis: `ccd75706fae112f1cd811f426ba7ca7dbfc3fe8a`, with unchanged runtime
`f66727dda49d1b4ca2c7e814e218587c051f7f97` and the
[fixed guest/converter/provenance identities](v050-semantic-audit.md#scope-completion-and-identities).
This is a re-evaluation of existing evidence and the corresponding checked-in
source. No runtime fix, new guest trace, model experiment or qualification has
been executed for this update. The [short Human Review judgment](v050-human-review.md)
owns the current recommendation and supersedes the earlier acceptance handoff.

## Applicable requirement and current judgment

The comparison is this **actual optimized Wasm guest** against its translated
runtime, including the guest's imported thread/wait ABI and supported DB
lifecycle. It is not a comparison against an idealized unoptimized POSIX source,
and it is not a guarantee about other Wasm programs.

R1/R2 supply bounded positive arguments for the reviewed access mappings;
R3/R4 have reproduced T1/T2 helper/ABI violations; R5 supplies target/dependency
coverage, not execution of every schedule. For J1 the applicable preservation
question is whether translated accesses/host ordering introduce an outcome
forbidden by the fixed Wasm plus its import contract. The additional product
question is whether a thread allocation can be reclaimed while that thread still
accesses it, even if both executions inherit the same guest flaw. These outcomes
must not be conflated. The existing evidence answers neither question positively
or negatively enough to recommend a repair or acceptance.

## User consequence and ordinary reachability

If the disputed edge allows premature reclamation, an exiting worker could
access storage which the guest allocator has freed or reused. Plausible visible
consequences are a Close/shutdown failure or hang, or intermittent test failure
from corrupted cleanup state. These are conditional consequences, not reproduced
SQL failures, measured likelihoods, or evidence of cross-DB corruption. A wrong
pthread return value is also a generic join concern, but normal resident joins
pass NULL for that value; it is not the primary user consequence here.

The route is present in ordinary use, not dependent on the 292-year timeout or
thread-ID exhaustion:

1. [Resident session open](../../guest/resident.inc) creates one reusable pthread
   for a used connection slot. Session close keeps that worker for slot reuse.
2. DB Close ends the resident protocol. The root sets each slot's stop flag and
   signals its condition under the slot mutex; the worker closes its connection,
   calls mysql_thread_end and returns.
3. [Resident shutdown](../../guest/resident.inc#L224) joins every started slot
   before `l4m_close`. These joins are inlined in canonical `_start` Fn21692.
   A one-connection Start/use/Close therefore uses the join route. Bare Start/Close
   with no connection skips the resident-slot joins; MariaDB background cleanup
   has additional join routes, without a saved branch trace for that minimal case.
4. A join may observe detach_state==DT_EXITED and thread-list lock==0 immediately
   and free map_base without calling host wait. Other joins take the waiting
   branch. Which branch wins depends on scheduling, not a special user option.
5. Only after the guest root finishes does
   [executeGuest](../../internal/generatedgo/runtime_instance.go) join the Go
   workers. [releaseMemoryModule](../../internal/generatedgo/memory_lifetime.go)
   joins again before unmapping the whole backing.

**Evidence level:** the normal route and inlined fast branch are statically
confirmed. Prior normal Start/Close/scenario PASS receipts exist, but their
instrumentation did not record this branch or allocation overlap. They do not
prove fast-branch execution or failure. Host drain protects the whole backing;
it does not by itself order an earlier guest free.

## Confirmed evidence and the specific missing premises

| Confirmed | Evidence / implication |
| --- | --- |
| Join reads completion at pthread+28, then list lock 15243132 ordinarily; zero/zero can lead to free of pthread+40 map_base without wait | [Fn221](../../internal/generatedgo/code/p7/p7_pure.go#L7700), and [99-reference slice](v050-semantic-audit-evidence/thread-list-accesses.json) including the inlined `_start` joins |
| Exit and unlock publish completion/list state; the source uses barriers around a_store and in __tl_sync | [Pinned WASIX anchors and source hashes](v050-semantic-audit-evidence/source-anchors.json), [selected-source verification](v050-semantic-audit-evidence/source-verification.json) |
| Optimized guest join has no explicit acquire/fence on these words; waiting branch invokes the host | [J1 stage review](v050-semantic-audit.md#j1--fast-guest-join-publication-remains-unresolved). MemSize's unrelated atomic bounds read is not a completion event |
| Small sysroot reduction loses three fences in Binaryen; explicit fences survive patched wasm2go in both output modes | [Fence commands, identities and results](v050-semantic-audit-evidence/fence-results.json). LLD 21.1.2 reduction is not the adopted LLVM 23.1.0 whole-guest build |
| A release marker is not automatically the last linear-memory access | In Fn216, list-lock clear can be followed by conditional Fn89 wake. [Fn89](../../internal/generatedgo/code/p8/p8_pure.go#L126) writes a result byte on the calling guest stack, and [host wake](../../internal/generatedgo/main.go#L166) also writes that output byte. Address containment, applicable exit branch and overlap with free are not established by this lexical sequence |
| Blocking and fast joins have different synchronization opportunities | Host wait/notify uses parkMu; a completed fast join need not register a wait. Slot mutex/CV, allocator locks, thread-list CAS and host callbacks may supply other ordering; none can be omitted from the comparison |

The last-access row identifies a precise check needed within J1's existing
exit/join scope. It is **not a second reproduced defect**. Merely adding atomic
loads/fences would not establish that all accesses end before reclamation.

The missing premises are:

- **Allocation lifetime:** recover the exact map_base/map_size versus worker
  stack/TLS/result-slot layout from the adopted source/generated address flow;
  identify the last access to that allocation after completion/list publication,
  including wake's guest and host result stores and thread exit. Do not assume
  that “user thread function returned” means the runtime stopped accessing it.
- **Ordering and original allowed outcomes:** pair those specific instructions
  with their actual optimized-Wasm bodies and import calls. Include the normal
  Close's slot mutex/CV, thread-list operations, wake and allocator synchronization.
  Determine whether a premature-free/stale-state outcome is forbidden by the
  original guest contract, newly enabled by Go compilation, shared by both, or
  excluded by an existing completion edge.
- **Actual branch/address observation:** ordinary shutdown reaches join, but the
  saved traces do not show fast versus blocking join or free/last-access order.
  Instrumentation can establish execution/address attribution; it cannot prove
  weak-memory safety and can introduce synchronization which masks the issue.

No mmap/race-detector silence or repeated successful SQL run supplies these
premises. No probability of failure has been measured.

## Recommended additional work and finite acceptance

**Owner recommendation: additional confirmation first.** Current acceptance is
not recommended because the route is ordinary and its lifecycle argument is
missing. Immediate repair is also not recommended: the defect location and
original-Wasm allowed outcome have not been established.

A single J1 task, using saved R1–R5 evidence, has these deliverables:

| Work item | Output / time estimate |
| --- | --- |
| J1a allocation and last-use slice | Exact allocation bounds, exit/join branch mapping, post-marker guest/host accesses and free sites for Fn216/217/221 and the already identified inline copies; 30–45 minutes |
| J1b actual Wasm↔Go ordering comparison | Hash-bound actual Wasm bodies, instruction-to-Go/host map, decisive ordering argument or counterexample with original allowed/forbidden outcome; 45–75 minutes |
| J1c one targeted observation/reduction if needed | One-connection ordinary shutdown, plus forced already-exited and wait branches in an isolated build/fixture; record addresses, free and last-access events, observer/control differences and heap/mmap limits; 30–45 minutes |
| Decision record | Supported mapping, translation violation, shared guest lifetime violation, or specifically unfinished premise; 15 minutes |

Total estimate **2–3 engineer-hours; stopping budget three hours** including
input/tool restoration. These are planning estimates, not measured durations
or a guarantee of resolution. Use an existing checksum-bound accepted guest
artifact for J1b; if unavailable, report that concrete input dependency and the
cost of formal rebuild before changing the agreed scope. No whole-guest census,
new platform, repeated reassurance stress, mmap redesign or final qualification
belongs to this task. J1c is optional only when J1a/b already answer its question;
its omission must have an explicit reason, not be labelled native PASS.

The decision must follow the evidence:

- **Supported preservation and lifetime:** close J1 without a repair; T1/T2 fixes
  and their checks then permit final Qualification of the final candidate.
- **Wasm-forbidden translated outcome:** repair its owner, with a paired oracle
  which rejects the current forbidden outcome and accepts correct completion,
  then regenerate and verify before Qualification.
- **Unsafe lifetime shared by Wasm and Go:** do not label it a wasm2go mismatch;
  propose a guest completion/reclamation repair for ordinary shutdown. Qualification
  alone cannot establish that this lifetime contract is valid.
- **Specific premise still unresolved at the cap:** report the exact incomplete
  J1a/b/c deliverable, engineering obstacle and a concrete remedy/cost. This does
  not reopen R1–R5 or make three hours “completion.” It also does not automatically
  authorize accepting J1. Present an assessable bounded design next.

If a repair is required, the provisional envelope is **4–8 further
engineer-hours**: 2–4 for owner design/implementation and decisive protocol oracles,
plus 2–4 for canonical guest build where needed, translation, independent
regeneration and affected lifecycle checks. Refine after J1 locates the owner;
this is not approval to implement. A publication-only change might be small,
but post-marker stack use may instead require changing the reclamation event.
Do not hand-edit generated Go or add a fence that Binaryen can remove and call
that complete. A guest change alters guest/Snapshot identity and requires the
existing provenance and old-Snapshot rejection rules. T1/T2 runtime fixes can
share regeneration/check work where appropriate; the final Release CI and
Product Validation are separate costs, not included in this estimate.

## Recommendation change and strongest counterargument

The earlier report allowed T1/T2 fixes followed by qualification with J1 left to
Human acceptance. That was premature as a *technical recommendation*: it lacked
normal-use consequence/reachability and a last-access versus free argument. The
later reply introduced a stronger gate without explaining that change. This
record explicitly replaces both ambiguous formulations with **two required
fixes plus one bounded J1 technical decision**, not three required fixes.

The strongest objection to this additional gate is that no translation
counterexample exists, the optimized Wasm itself lacks the alleged source fence,
and ordinary functional tests passed while host drain protects backing lifetime.
A source-POSIX expectation cannot manufacture a Wasm violation. This is why the
recommendation is a small actual-Wasm comparison before repair, not unconditional
redesign. The counterargument does not prove that a guest allocation remains
owned until its last access; host drain happens later. Normal-use reachability
and the specific missing lifecycle premise justify one bounded decision task.

The Human is being asked to review this technical work recommendation and its
cost. The Human is not being asked to infer memory safety from internal names
or choose an unquantified defect probability without evaluation material.
