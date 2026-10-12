# v0.5.0 bounded shared-access semantic investigation

This is the result of the approved [R1–R5 investigation contract](v050-access-review.md),
not release qualification. The question is whether the fixed runtime preserves
the relevant Wasm operations and the guest's synchronization/lifetime contracts.
It is not whether enough stress tests have passed to make every concern disappear.

**Investigation coverage COMPLETE for the approved R1–R5 contract; correctness
not fully established, fixes not performed, RELEASE READY not asserted.**

**Assessment:** the specific mixed ordinary/atomic mutex reads are not evidence
of SQL corruption. Their consumers, CAS revalidation, compiled access width and
publication paths now have a bounded implementation argument. All 147 narrow
writer sites have target/lifecycle entries, including recovery and I/O callbacks
which were previously only classified by name. Two concrete boundary defects were
reproduced in unchanged helpers: positive wait-duration overflow and exhausted
thread IDs. One exact guest join/publication question remains investigated but
unresolved. These are separate findings, not a claim that general shared-memory
correctness is established.

No product implementation, generated output, guest input, converter patch,
provenance, existing failure oracle or public API was changed. The new code is
analysis tooling and isolated fixtures. No main merge, tag, publication, final
Qualification or Product Validation was performed.

## Scope, completion and identities

The requested completion rule remains: every in-scope target and dependency must
have an evidence-backed disposition; unexamined entries prevent completion.
An investigated unresolved premise is visible as unresolved, not converted to
PASS. The five-hour limit is a stopping budget, not an acceptance test. The
Human cancelled hourly reporting while resting. Actual timing and final coverage are recorded in the evidence receipt;
workspace cleanup is a subsequent storage operation recorded by its helper; the final assessment must be
read together with the outstanding items below.

| Item | Fixed input |
| --- | --- |
| Investigation source commit | `67549402ff4d4a5ddda2a3a56961e12828c8ffa5`, checked as a commit with `git_identity.py` before builds |
| Runtime implementation | `f66727dda49d1b4ca2c7e814e218587c051f7f97` |
| Guest | MariaDB 12.3.3, Wasm SHA256 `7c7b6ce5168a1a0d98019751b4c36c25f2e9948dbae0124ec3f434efb0b8642c` |
| Linked input | SHA256 `3b63079109c895f3e90895f86b57e48d9f8e14f13ce945021c88e20c4f4fd9ba` |
| MariaDB source | `83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e`, canonical ordered portability/12.3.3 patches |
| WASIX source | v2026-07-03.1 archive `55091ce6af5b549b3c97f61592bd2506e6a7e5da3588cb2f77a64388468ad231`; existing provenance commit `09503b230e8acc721c1e013ca28a41bf149e4ee2` |
| Converter | goccy `730057c146463f663e8774587bc96fb2bea91af8`, current 11 ordered patches; no converter update |
| Canonical base | SHA256 `b43554887688b079987c77ed954dd62ad75ec9616c7df0f5979d81e4cc5c8932` |
| Canonical provenance | SHA256 `98e389d019f4a2d09350bace9c8c691de8926bcffb9d1781c9d9ce1880b64a97` |
| New native execution | Go 1.26.8, macOS 27.0.1 arm64; heap and production memory-mapping owner |

The source collector rechecks a 4,739-file MariaDB and 2,577-file WASIX reference
corpus against archive bytes and ordered portability-patch postimages. This is
not the full prepared guest tree: for selected files it also reproduces the
canonical diagnostic insertions and checks modified-file hashes against the
formal prepared-source manifest. Selected source,
compiler and optimizer anchors retain hashes. Generated function files match
provenance. The 20-function protocol package copies function bodies, host wait/
wake methods and canonical base files unchanged, with hashes. Its synthetic TLS,
memory size and scheduling hooks make it an **isolated real-function fixture**,
not a complete MariaDB process or a new SQL result.

The ledger is normalized: [writer sites](v050-semantic-audit-evidence/writer-ledger.json)
refer to [28 target records](../../benchmarks/spikes/v050-semantic-audit/targets.json)
and protocols P01–P13 below. All 14 original *function families* remain covered;
startup/shutdown is distributed to the targets it actually writes. Thus 13 shared
protocol narratives do not remove the four startup/shutdown functions. Binding
confidence is source/layout/value-flow corroboration, not DWARF type proof.
Process deviation: the finite input inventory was fixed before the probes; the detailed ledger was
assembled alongside analysis, rather than completed before those probes as the contract requested. This
ordering deviation is disclosed; the final ledger still reconciles every site
and no target was dropped to close the investigation.

## Per-item disposition

| Work item | Investigation result | Effect on recommendation |
| --- | --- | --- |
| R1: ordinary/atomic reads | 65 ordinary-read statements in Fn88/93/130 classified; bounded mapping supported for pinned macOS code and valid guest ownership | Heap race reports alone do not justify a mutex rewrite or a user restriction |
| R2: native/Go ordering | Compiler memory-effect boundary and arm64 acquire/release/barrier composition documented; existing litmus/value receipts reused | Retain exact-width fix; no new whole-engine serialization justified by this evidence |
| R3: CV/rwlock/wait ABI | Actual protocol functions pass the named schedule/ownership checks; **T1 positive timeout boundary FAIL** | Recommend a small owner fix and regression oracle before qualification |
| R4: launch/host/drain | Normal launch transition and host backing drain supported; **T2 ID exhaustion FAIL**; **J1 fast guest join publication unresolved** | Bound ID allocation before qualification; J1 needs an explicit engineering decision, not an invented SQL-failure claim |
| R5: target and access routes | 65 functions / 147 sites / 28 targets reconciled; 47 indirect calls in the 17 writer functions classified; source lifecycle/raw/bulk/host routes recorded | Replaces the old generic `Source/lifetime review required` entries; dependencies T1/T2/J1 remain visible |

Target-level “supported” describes the local ownership/access argument. It does
not erase a dependency's boundary defect or imply all supported configurations
were executed. No platform or product configuration was silently removed to
obtain these dispositions.

## R1 — what the ordinary reads actually do

An ordinary read here is a generated `*(*int32)(...)` or byte read, without an
atomic operation or lock at that individual instruction. It is not automatically
a broken lock: a preliminary read may only decide whether to spin, while a later
CAS actually acquires ownership. Conversely, a read used to publish completion
without any acquire operation needs a different argument (J1).

The [statement table](v050-semantic-audit-evidence/ordinary-reads.json) names every
read, not just examples. The checker rejects a missing/extra read or changed
generated input. Its classes have the following consumers:

| Read class | Consumer, revalidation and required property |
| --- | --- |
| Immutable mutex type | Type/private/recursive flags select a branch; initialized before publication and not modified on a live mutex. Byte and word views overlap only this immutable field |
| Agent-local self/TID/cancel state | TLS selects this agent's pthread structure; cancel restore is this call's stack slot. Root TID is reserved `0x3fffffff`; child IDs have their own valid range (T2) |
| Owner test before CAS | TID comparison chooses recursive/error/try-lock handling. First ownership is still acquired by CAS; recursive state belongs to the existing owner. A preliminary read is not promoted to a synchronizing read |
| Owner-local recursion/robust list | Owner updates recursion and links after acquisition, before release; wrong-owner unlock returns EPERM. The fixture checks recursive/errorcheck basics; robust/PI owner-death modes are not newly execution-qualified |
| Lock/waiter spin hints | Only choose spin versus slow path; successful lock acquisition still requires a CAS. A stale hint can change work done, not grant ownership |
| Robust acquire waiter hints | Decide contention bits/list/error branches; acquisition uses lock-word CAS, and waiter/signed-lock information determines wake. These are **not** all CAS-loop preload statements |
| Waiter CAS loop | Fn93 lines 1743 and 1806 feed increment/decrement CAS; mismatch rereads and retries. No plain read followed by an unconditional write |
| Release CAS loop | Fn130's three copies read a candidate lock word and CAS it to the release value; mismatch retries. The successful CAS's observed old value is used for wake decisions |
| Unlock waiter hint | Snapshot of waiter count is supplemented by the sign bit of the **successfully released** lock word; a stale zero alone does not suppress all wakes |
| Futex precheck | Fn88 may return EAGAIN on ordinary mismatch. If equal, host performs an atomic comparison again while holding the registration lock |
| Host result local | One-byte result in this invocation's stack, written synchronously by the import before return; not a second agent's result slot |
| Futex timeout recheck | After host timeout, Fn88 checks whether the word changed and maps that case to success; caller rechecks its predicate. This does not itself acquire a mutex |

For the normal mutex lost-wake question, there are two decisive cases. If unlock
wins before the waiter marks the lock contended, the waiter's CAS/precheck/host
comparison prevents sleeping on the old locked value. If the waiter marks it
first, unlock's successful CAS observes the negative contended value and wakes.
Host compare/registration and notify share `parkMu`, closing the remaining
compare-to-enqueue gap. An ABA/new owner can legitimately require another wait;
it is not evidence that an unlocked mutex granted two owners. This argument
does not promise fairness or a maximum number of retries.

The pinned converter disables redundant-load elimination on shared memory and
retains potentially trapping pure-memory32 loads. Go 1.26.8 disassembly of the
copied actual functions shows aligned single-word `MOVW` reads, with rereads on
the relevant retry edges and calls to the contended atomic helpers. CAS uses
the Go atomic implementation (acquire load and LSE or acquire/release exclusive
sequence). There is no evidence here of a read invented from unrelated bytes,
a widened preliminary read or a plain unconditional lost-update replacement.

This is a compiled-code/algorithm argument for these sites, not reliance on
Go's race-free-program theorem. The [Go memory model](https://go.dev/ref/mem),
version June 6, 2022, places restrictions even on racy word reads and allows
detector-enabled implementations to report/terminate. It does not turn a heap
race report into a particular Wasm-forbidden outcome. Existing 2,000-update
mutex evidence and 22 heap reports remain unchanged; they are neither suppressed
nor repeatedly rerun as a confidence target.

## R2 — ordering across native and Go operations

The mapping argument has three parts, each needed:

1. **Compiler:** the native helpers are opaque calls. `//go:noescape` controls
   escape analysis, not purity. Go 1.26.8's `StaticLECall` takes/returns SSA memory;
   `ssagen` installs the call's returned memory state for following accesses.
   ARM64 atomic intrinsics similarly take/return memory. Thus ordinary payload
   accesses through the shared-memory pointer cannot be treated as unchanged
   across these calls. Source anchors and actual guest-helper disassembly are
   saved; no promise is made for an arbitrary future optimizer.
2. **ISA:** narrow helpers use exact-width LDARB/H or STLRB/H, or LDAXRB/H and
   STLXRB/H with retry. DMB ISH surrounds each primitive; failed comparisons clear
   the reservation. Full-width Go atomics use acquire/release atomic sequences.
   On normal coherent shareable memory these barriers/orderings compose with
   the full-width operations; they do not depend on Go heap allocation versus
   the ordinary mmap backing. A reservation granule may still encompass a
   neighbor and force a retry, without writing that neighbor.
3. **Actual targets:** live narrow metadata uses the declared byte/halfword;
   the wider ordinary copies identified in R5 are construction, fresh clone,
   prefix-only relocation or owned retirement. The mixed live WASIX lock word
   is a separate aligned 32-bit object. No current guest narrow cmpxchg writer
   site exists in the inventory: its four shapes are 132 Store8, 9 Xchg8,
   4 Store16 and 2 Add8. General helper cmpxchg remains covered by its prior
   implementation tests, not invented as a newly observed guest site.

The [prior writer study](v050-exact-writers-design.md#verification-and-actual-identities)
already contains store-buffering, IRIW, publication, mixed-width/value/boundary
tests and machine operand inspection. Those receipts are reused. This review
supplies the missing compiler-call boundary and target-layout argument; it does
not rerun finite litmus loops until they feel convincing. Arbitrary overlapping
mixed-size programs and all Go versions are not established by this argument.
No such unclassified live overlap was found among the 28 reviewed target records.

The same source's native Ubuntu checks were reported by
[Development CI](https://github.com/masahitojp/mariamem/actions/runs/38255402646/job/114832061016).
That prior run does not execute these new R1/R3 fixtures. New native Ubuntu and
minimum-supported-macOS execution are **SKIP**, not inherited PASS.

## R3 — actual protocol and ABI transitions

The fixture packages Fn69/71/80/88/89/90/93/94/130/202/203/209–213/218/220/226/4052.
The direct closure is exactly those 20 functions and has no indirect calls.
The host wait/wake methods and base implementation are byte-preserved.

| Transition | Argument and evidence |
| --- | --- |
| Expected value differs | Host atomic compare under `parkMu` returns not-equal before enqueue; WASIX result byte is true; Fn88's earlier mismatch is EAGAIN |
| Notify before host registration | Private CV node is inserted before releasing external mutex; signal changes node/barrier state; host comparison prevents stale sleeping. Forced fixture PASS |
| Notify after registration | Compare+enqueue and notify serialize on `parkMu`; closing selected channel wakes registered agent. Forced fixture PASS |
| Signal with multiple CV waiters | Source private-list lock, WAITING→SIGNALED CAS, detached list and barrier handoff preserve node ownership; broadcast of two actual waiters PASS |
| Timeout versus signal | WAITING→LEAVING CAS decides timeout ownership; competing signal is coordinated by node state/barrier/reference count. Mutex is reacquired before return |
| Expired/invalid absolute deadline | Actual Fn218 returns 73/28; different agent's try-lock verifies reacquisition/retained ownership. Fixture PASS |
| Timer and notify simultaneously ready | Go select may choose either completed event; expiry removes queue membership under lock. Predicate recheck remains required; no stronger fairness/latency claim |
| Indefinite wait | Negative timeout waits on channel in contended mode; single-agent trap is an existing bounded runtime policy. Product worker waits run after the launch transition |
| Empty wake | No waiter is required; helper reports zero count while WASIX out-byte is true per existing ABI mapping |
| Invalid address/result/timeout layout | Host checks bounds/alignment and returns errno 21; invalid option tag traps. Static code disposition; not advertised as a new runtime test |
| Cancellation/signal interruption | Guest cancel-state save/restore is local; asynchronous host thread_signal is fail-closed. The API does not gain cancellation support through this investigation |
| RW read/write contention | Read-count/writer CAS, waiters and contended bit; unlock uses CAS and wakes at the transition. One held-reader/waiting-writer and held-writer/read rejection fixture PASS |
| Positive upper duration | **T1 FAIL**, detailed below; ordinary short-duration PASS does not cover it |

Fn88's direct callers are rwlock Fn210/213, thread start Fn216, CV Fn218/219,
join Fn221, create Fn243, cond-destroy Fn266, once Fn808, timedwait Fn91/92,
mutex Fn93, generic wait Fn94 and libc locks Fn95/97. Thus the dependency is
not “mutex only.” Once/stdio/thread-list users reuse wait/lock primitives;
CV stack-node lifetime additionally depends on signal/timeout ownership and
the LEAVING reference handshake. `pthread_cond_destroy` uses that completion
protocol, not an assumption that a waiter has probably finished.

The new schedules pass on heap and mmap, normally and with `-race`. These
particular coordinated runs reported zero races on **both** backings. That is
not a contradiction of the older overlapping-mutex heap diagnostic: hooks and
channels constrain these schedules. The no-observer CV control also completes;
it establishes that this small scenario does not require the hook, not that
instrumentation is behavior-neutral for all workloads. Assembly accesses are
not automatically race-instrumented; mmap silence is never safety evidence.

### T1 — a positive duration becomes an immediate timeout

`AtomicWait` constructs `time.Duration(timeout) + time.Millisecond`. For
`MaxInt64 - 1_000_000 < timeout <= MaxInt64`, signed addition wraps negative.
The preserved failing oracle supplies MaxInt64, confirms return 2 before any
notification, and fails its “must still be waiting” requirement. This violates
the positive wait duration contract; the [threads execution draft](https://webassembly.github.io/threads/core/exec/instructions.html)
used here is dated 2023-10-10. It is an implementation counterexample, not a
detector diagnostic.

User consequence **if this boundary is supplied**: a requested approximately
292-year wait times out immediately. No ordinary SQL operation was shown to
generate this interval, and this does not establish that millisecond/second
timeouts expire incorrectly. The WASIX host accepts this interval; Fn88's
negative durations encode None, so the host's separate `>MaxInt64` rejection
does not introduce another reachable interval through that adapter.

The owner is converter `internal/codegen/helpers/helpers.go`, not generated
`base.go`. Proposed separate fix: overflow-safe positive timer construction
(preserve the existing timeout policy deliberately), tests immediately below/
at/above the addition boundary, zero/negative waits and host-result mapping,
then normal canonical and independent regeneration. No fix is hidden in this
study and the failing oracle is retained.

## R4 — launch, host access and retirement

Production guest spawn goes through `ThreadSpawn` → `ThreadLaunch`. For valid
IDs, allocation changes `nextTID` before the child goroutine can run. Other
guest agents therefore use contended full-width atomics; the counter is not
decremented when a worker exits. Go creation publishes preceding initialization.
The first/last-valid seeded boundary checks confirm the transition; T2 records
why “never returns to zero” cannot be stated without a range condition.

Host imports run synchronously on the calling agent. File imports receive
explicit data/result buffers; reviewed I/O metadata is not those payload bytes.
Signal callback registration copies a name, without asynchronous guest-memory
delivery. The unused subprocess helper's Go waiter updates process state and a
completion channel, not linear memory. Frontend pipe/connection goroutines do
not receive a Module pointer. Snapshot export occurs after `executeGuest` joins
workers, not while they are changing the backing.

For whole-backing retirement, `StartInstance` registers cleanup immediately;
`executeGuest` waits for workers even after root/worker failure; release repeats
the join before unmapping and keeps the module alive through release. File/
prepared mappings are closed after that drain. A non-cooperative worker can
hold this completion indefinitely: that existing limitation is not converted
to safe forced cancellation. Object retirement *inside* guest memory still
needs the R5 protocol; whole-backing join cannot retroactively protect an object
freed earlier by guest code.

### T2 — thread ID exhaustion is not handled before spawn

The [wasi-threads ID contract](https://github.com/WebAssembly/wasi-threads/blob/main/README.md#design-choice-thread-ids)
uses successful child IDs in `[1, 2^29)`, with negative values indicating failure.
The pinned WASIX wrapper imports `wasi.thread-spawn` (not the distinct
WASIX `thread_spawn_v2` interface). The fixed `pthread_create` maps a negative return to EAGAIN and frees its
new thread allocation. `ThreadLaunch` instead unconditionally increments an
int32 and launches a child. Seeded boundary fixtures on the unchanged helper:

| Previous allocator value | Returned ID / child behavior | Verdict |
| --- | --- | --- |
| 0 | 1; child uses contended mode | PASS |
| 536,870,910 | 536,870,911; child uses contended mode | PASS |
| 536,870,911 | 536,870,912; child runs outside valid ID range | FAIL |
| 2,147,483,647 | negative failure value; child nevertheless runs | FAIL |
| -1 (eventual wrap state) | zero; child runs with contended mode false | FAIL |

These tests seed internal state rather than claiming hundreds of millions of
real launches. The threshold is cumulative child launches within one Module/DB, not a sum
across independent databases. The counter has no decrement/reuse/bound, so the representation
edge is concrete. Ordinary small DB lifetimes were not shown to reach it.
User consequence at exhaustion: creation can report failure while work still
starts; the WASIX caller then frees the child's allocation. That caller-path
consequence is a source argument, **not a reproduced SQL crash or use-after-free**.
Zero-wrap's fast-path violation is downstream of an already-invalid ID range,
not a new normal-workload failure.

Proposed separate fix: allocate only within the valid positive range and reject
exhaustion **before** registering/starting a child; keep contended mode monotonic.
A bounded fail-closed allocator is sufficient to address this finding; ID reuse
and forced worker cancellation are not required. Verify boundary, concurrent
allocation, no-child-on-failure and unchanged normal start/drain semantics, then
regenerate through the owner. No runtime fix is included here.

### J1 — fast guest join publication remains unresolved

This is a specific remaining edge, not generic doubt about all teardown:
Fn221 reads `pthread.detach_state` ordinarily; on the already-exited path it
reads `__thread_list_lock` ordinarily and can proceed to free `map_base` without
calling host wait. The source `__tl_sync` has `a_barrier`, and `a_store` around
exit/unlock has fences. A C-source barrier cannot simply be asserted to survive
the complete pipeline.

The stage investigation found:

- The pinned sysroot's `pthread_create.o` contains the __tl_sync/__tl_unlock
  fences; the join object calls the synchronization helper.
- A small linked reduction exported those helpers. Binaryen 133 with the
  adopted optimization flags removes its three fences. Its interpreter/source
  treats a Wasm fence as unnecessary given current SC atomics. This is a
  reduction using local LLD 21.1.2, **not a full guest rebuild or proof of the
  exact original guest's optimization history**.
- Independent tiny inputs containing `atomic.fence` survive the pinned patched
  converter in both single-file and multi-package modes. It is therefore
  incorrect to call the observed absence a demonstrated wasm2go fence-drop bug.
- The actual canonical Fn221 fast branch has no explicit fence or acquire on
  the completion/list words. Bounds checks read the independent MemSize atomically;
  that alone does not establish completion synchronization. Its waiting branch
  does call host wait. `std::thread::detach` can reach Fn221 after its
  detach CAS; direct join callers also include Aria checkpoint/soft-sync cleanup
  and wolfSSL's no-join helper. Inlined copies also occur in `__pthread_detach`,
  `wolfSSL_JoinThread`, Aria service-thread cleanup, server `clean_up`,
  `std::thread::join`, feedback cleanup and `_start`. The saved thread-list
  access slice includes these copies, create/start and unlock; it is not limited
  to callers which survived as a direct Fn221 call. The detach CAS must not be
  silently attributed to every direct/inlined join caller.

**Missing guarantee:** ordering of completed thread-local/list effects before
another agent takes the *already-exited* ordinary-read branch and frees its
thread allocation, without the blocking wait's synchronization. The existing
whole-module host join establishes backing lifetime, but not this earlier
guest allocation reuse. No stale-read/free-overlap counterexample was reproduced,
and no Wasm-versus-Go semantic difference was established for this branch.
The original optimized Wasm may already permit the disputed weak observation;
source POSIX expectations and Wasm preservation must be judged separately.

The attempted methods were source/actual generated control-flow inspection,
pinned sysroot object decoding, a link/optimization reduction and explicit
converter fence probes. Repeating SQL or race stress cannot supply the missing
ordering premise. The finite next engineering choice is either (a) a precise
model argument for this two-location fast branch and its callers, including the
optimized Wasm contract, or (b) a narrowly owned join/thread-list publication
change with paired positive/negative protocol oracles and regenerated guest.
Neither a general mmap redesign nor converting every guest load is implied.
This report does not choose/implement that change or claim J1 is an actual SQL
defect. Its consequence, **if the missing ordering permits premature reuse**,
would be thread cleanup seeing incomplete state; the likelihood is unmeasured.

## R5 — target, callback and lifetime coverage

The ledger distinguishes source atomic assignments from ordinary stores and
separates a containing function's primary family from each inlined target.
Important corrections to a function-name-only reading include:

- Fn17371's narrow write is the global encryption request, not recovery-node
  ownership. Fn18241 also clears the deadlock-victim byte, besides ReadView.
- All eight narrow stores in fake I/O callback Fn18218 mark
  `page_recv_t.being_processed=-1`. Its `IORequest.slot` is a deliberate typed
  alias to a recovery node, not a temporary buffer reservation.
- All eleven narrow sites in read completion Fn18114 are temporary-buffer
  reservation flags. Fn18136 combines block halfword reset with separate LRU
  global flags. Startup/resize functions similarly write several protocols.

The local target arguments below depend on R1–R4 rather than replacing them.
Detailed neighbors, creation/publication/use/reuse/destruction, raw aliases,
callbacks, consequences and source references live in the target records.

| Protocol | Target path and decisive lifetime/access edge |
| --- | --- |
| P01 guard | GlobalMutex libc++abi guard: atomic byte 0; ordinary byte 1 under the global mutex/CV; static initialization before guarded-object publication. Exact operands make the bytes disjoint |
| P02 pool | Creation-pending flag is atomic. Worker callbacks are registered by `srv_thread_pool_init`; task execution releases a reference. `worker_end` removes the last worker under the pool mutex, and destructor waits its CV. Timer disarm cancels pending work and waits references before free |
| P03 transaction/view | TrxFactory zeroes before registration. Live view open/close uses its atomic byte and mutex; fresh clone/pool reuse does not memset a registered live view. Deregistration/freeze/refcount precedes destruction |
| P04 purge | Four neighboring bytes have distinct roles; ordinary initialized state is create/close-only. Coordinator disable and worker/truncation task waits precede close. Thread-count flag accompanies count protected by `purge_thread_count_mtx` |
| P05 file/extension | Space references and `fil_system.mutex` protect node/space lifetime. Extension sets its atomic flag before unlocking for I/O, clears after relocking, and close/rename/extension retries respect it. Host I/O targets frame buffers, not node metadata |
| P06 encryption | Global rotation flag is monotonic atomic request, not per-page key publication. Getter callback takes a numeric key ID; row-store callbacks write SQL Field objects. Crypt mutex/count/CV drains workers before cleanup |
| P07 recovery | Map node state 0→1 claims work; completion writes -1 as its final node access. GC under recv mutex erases completed nodes; wait_for_pool releases mutex, drains read/write I/O and reacquires before GC. Successful apply/new-empty-db debug_free differs from error returns, which route to shutdown/drain |
| P08 buffer load | Abort flag is a prefetch hint. One waitable load task owns operation state; shutdown waits `buf_load_dump_end`. Page contents have their own buffer ownership |
| P09 deadlock | Request flag accompanies a graph scan under lock-system locks. Per-trx victim flag shares transaction lifetime P03; commit reset is distinct from initial whole-object zero |
| P10 AHI | Index hint bytes are atomic; fresh-index clone is unpublished. Hash structures use partition/page/index latches. Block halfword +220 is outside the `buf_page_t` prefix copied by relocation. Resize initializes only new descriptors or owns withdrawn blocks before debug clearing/free |
| P11 cleaner/I/O | Cleaner completion uses flush mutex/CV; I/O slot cache destructors wait in-use operations before backing buffers are closed. `reserved` claims exclusive temporary buffers; release follows final buffer use. Normal read/write callbacks receive real frame buffers; fake completion receives recovery node as P07 |
| P12 checkpoint | Atomic request flag is a hint; LSN/data publication uses log latch/atomics/flush completion. Cleaner/task/I/O drain precedes `log_sys.close` |
| P13 table cache | Atomic first-warning flag only suppresses duplicate diagnostics; actual table-cache entries use the cache mutex. No SQL row data is published by this byte |

`innodb_shutdown` provides the shared teardown order: stop background sources,
wait cleaner/load/rollback work, `os_aio_free` (slot destructors wait even on the
fast-shutdown path), close file spaces, stop remaining background work, crypt
cleanup/AHI disable, then log/purge/trx/lock/dict/file/recovery/buffer destruction
and pool end. Startup error branches do not reuse successful-apply debug_free
as an unconditional cleanup shortcut. A root trap additionally follows host
worker drain; it may hang on a non-cooperative worker rather than forcibly free
the backing. These are named completion edges, not timestamp comparisons.

Supporting synchronization is not limited to mutex: the WASIX build selects
`SUX_LOCK_GENERIC`, including pthread mutex/CV, POSIX rwlock wrappers, atomic
reader/writer counters and their CAS loops, task reference counts, once/guard,
thread-list/join and futex registration. Normal `MY_MUTEX_INIT_FAST` falls back
to default attributes in this WASIX build. Source-level relaxed/acquire/release
atomics lower to Wasm's SC atomics; adjacent ordinary metadata remains ordinary.

The [47-site callback map](v050-semantic-audit-evidence/indirect-calls.json)
classifies the actual writer-function indirect calls, with source registrations
and selected initial-data/table corroboration. Three local std::function cleanup
manager words are zero in the fixed initializer and guarded before call; their
presence in the lexical graph is not a hidden metadata writer. Other classes
are pool/task/timer dispatch, exception text, key-version lookup, corruption
logging, charset comparison, SQL Field stores and THD option resolution. This
does not call all 24,025 program-wide table-call lines “safe”; only routes which
can reach these targets/owners need that classification. Native plugin replacement
or arbitrary corruption of a function table is not silently assumed as a normal
alias of a private metadata field.

Bulk/SIMD/host exclusions are object-specific: constructor zeroing before
publication; clone into a fresh receiver; buffer-prefix relocation excluding
the target halfword; owned withdrawn-descriptor clearing; file/frame bytes
separate from metadata; and I/O completion's explicitly resolved recovery alias.
They are not based merely on grep finding no field name near `memcpy`.

Reproduction commands and the distinction between source corpus, prepared
source and isolated execution are in the [fixture recipe](../../benchmarks/spikes/v050-semantic-audit/README.md).

## Execution evidence and limits

| Check | Result / scope |
| --- | --- |
| Pinned source/postimage verification | PASS; 4,739 MariaDB + 2,577 WASIX source files |
| Writer ledger and R1 read reconciliation | PASS coverage: 65/147/28 targets and 65 ordinary reads; counts are not correctness proof |
| Indirect call classification | PASS coverage: 47 sites in 17 writer functions, with arguments and selected table/data checks |
| Actual CV signal before/after registration, broadcast, expired/invalid timeout, rwlock conflict, recursive/errorcheck ownership, no-observer CV control | PASS on native macOS heap/mmap, normally and with `-race`; isolated functions/TLS |
| T1 positive timer boundary | **FAIL** required behavior, expected reproduction on unchanged source |
| T2 ID boundaries | First/last valid PASS; reserved-bit, negative-spawn and zero-wrap **FAIL** required behavior; seeded counter |
| Fixture compilation | PASS; separate from product acceptance |
| Full fixture `go vet` | **FAIL:** four unreachable-code diagnostics in copied generated bodies; source unchanged, analyzer not disabled |
| Evidence/public-source/tooling checks | PASS saved-file hashes, Python syntax, Go fixture formatting and public-source boundary; see checks receipt |
| Canonical source ownership | PASS source/provenance check; no generated changes or refreshed identities |
| Independent canonical guest/runtime regeneration | Not performed: no product source/input change. Prior integration receipt remains the evidence for its input/output identity |
| New full SQL/consumer/Snapshot/Qualification runs | Not performed: this investigation adds no product behavior. Prior fixed-input receipts are reused without relabelling them as new results |
| New native Ubuntu / macOS 15 execution | SKIP; no such native environment in this investigation |

Each writer row records whether its exact site was observed in the **earlier**
default/AHI-on guest traces. Their source was `82f3c2...` plus the saved observer,
with the old widened helper; unchanged function bodies permit path attribution,
not a new exact-width address trace. The earlier trace reached 24/65 functions
with AHI on. The other 41 remain unobserved in those scenarios, not unreachable.
The [saved SQL scenarios](v050-shared-impact-evidence/scenario-results.json) and
later exact-width regression comparison retain their own PASS scope. They do
not prove the new ordering arguments or supply rare/error-path execution.

Configuration coverage is explicit: the earlier ordinary scenarios started
with AHI OFF, and a second series turned AHI ON. Both remain in scope. Runtime
resize, purge-thread count, buffer-load abort, doublewrite/write-through,
encryption request, read-only/startup-error and fast-shutdown routes have the
source/lifecycle dispositions above; this task did not execute a configuration
matrix for them. Encryption/plugin callbacks are classified by their actual
arguments/registration, not declared unreachable because the default run did
not exercise them. No new support-policy exclusion was introduced.

The evidence separates: (1) reproduced helper-contract defects T1/T2, with no
new SQL harm reproduction; (2) actual mixed-access mutex execution and detector
reports, without demonstrated protected-value loss; (3) source/compiled-path
findings and J1's precise missing ordering premise; (4) unexecuted platforms,
unobserved writer scenarios and broader mixed-size programs. No numerical SQL
failure probability is inferred from any of these categories.

## Human decision and separate implementation scope

The recommendation is now concrete: retain the accepted exact-width work;
address **T1 and T2 with bounded owner fixes**, retaining the failing oracles and
canonical independent regeneration, before final qualification. These findings
do not justify classifying mariamem as unsuitable for development or publishing
a vague warning that ordinary SQL is unsafe. Their triggering conditions and
the distinction between reproduced helper behavior and hypothetical SQL harm
belong in this development judgment record.

J1 is the remaining decision about the strength of the guest completion
guarantee. Accepting this investigated limitation for v0.5.0 versus requiring a
specific join/publication argument or change is a Human choice. It is not a
request to accept an unexamined list of internal components. If stronger work
is chosen, scope it to that fast branch and its actual callers; do not restart
an open-ended full shared-memory investigation. No broader design is required
solely because a detector cannot see mmap/assembly.

This task stops at that review boundary. Fix completion, final native
Qualification, Product Validation and release approval remain separate.
