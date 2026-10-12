# v0.5.0 access paths: Human Review

**Superseded assessment:** the [subsequent scope and exit-criteria review](v050-access-review.md)
withdraws the progression recommendation below. The requested overall path
investigation is incomplete; this report remains intermediate evidence under
its recorded scope. The historical observations and receipts are preserved.

**Decision now: proceed to final Qualification and Product Validation with an
explicit general shared-memory limitation, or require broader engine work first.**
I recommend proceeding with the existing exact-width candidate, without a
release-ready claim. The important narrow targets have atomic live accesses or
source-supported initialization/teardown separation; this investigation found
no additional concrete narrow-access violation requiring a product fix.
The strongest objection is substantial: the supporting WASIX mutex/futex paths
mix ordinary and 32-bit atomic accesses, and copied real-guest mutex functions
produce Go heap race reports. We have not established the entire Wasm-to-Go
memory-model mapping. That objection prevents a general safety guarantee;
it does not, by itself, demonstrate incorrect SQL or invalidate the specific
exact-width correction. The bounded mutex workload kept correct protected
values and completed, with observation both enabled and disabled. Choosing
broader work remains reasonable if the Human requires a stronger guarantee.

Adoption of the writer correction was already approved. This review concerns
the remaining limitation and the next validation stage, **not publication**.
Final Qualification/Product Validation remain unperformed; no main merge, tag
or release is part of this task. Any concrete wrong result, lost wake, invalid
memory access or demonstrated ordering violation would reverse the recommendation
and stop progression until resolved. Detector silence is not that evidence.

## What “all paths” covers here

The investigation starts from source commit
`20a9ca9156455939f4903d681345bd9868b1ac51`, the approved
[exact-width integration](v050-exact-writers-integration.md). Its runtime is
`f66727dda49d1b4ca2c7e814e218587c051f7f97`; guest/function bodies are unchanged
from the earlier [impact study](v050-shared-impact.md). This task changes only
analysis tools, isolated fixtures and documentation on `experiment/v050-access-paths`.
Canonical Go, guest source patches, converter pins, failure oracles, license
inventories, APIs and Snapshot identities are unchanged.

There are two different completeness boundaries:

1. **Inventory:** every one of the fixed guest's 65 Generated-Go narrow-writer
   functions and 147 writer sites is included, including the 41 functions not
   executed by the earlier AHI-on scenarios. No unobserved function is called
   unreachable. All 21,628 defined generated functions were scanned for direct
   calls and table-call sites. Constructor, live and teardown accesses are
   included in selected source references rather than considering SQL alone.
2. **Ownership/synchronization assessment:** the seven important target groups
   below were followed through named source readers/writers, object creation,
   publication/reuse, stop/drain and destruction, then through the relevant Go
   helper or synchronization path. Other writer families were classified with
   source declarations/accessors and caller evidence. This is **not** complete
   program-wide pointer/alias analysis, resolution of every indirect callback,
   every bulk/SIMD/host overlap, all error/configuration paths, or proof of every
   possible execution. Those boundaries remain explicit in the assessment.

In particular, complete lexical references to a field do not prove that an
untyped pointer never touches it. The direct graph omits dynamic table targets;
there are 24,025 lines with typed table-call sites across the full generated
program, including 33 in the constructor function. They are marked as indirect,
not silently treated as ordinary direct calls. We do not turn source-supported
ownership into a theorem about the entire compiled guest.

The [scanner](../../benchmarks/spikes/v050-access-paths/scan.py) verifies both
source archive hashes, every relevant extracted source file (MariaDB 4,739;
WASIX 2,577), the registered portability patch postimages, both pinned libc++abi
guard files, function-map hash and transpiled-file provenance. Added source,
changed archive/source bytes and writer inventory drift fail the check.
It records 716 lexical references in the declared scope, with file hashes,
line numbers and contexts. The [65-function inventory](v050-access-paths-evidence/writer-inventory.json),
[source references](v050-access-paths-evidence/source-references.json),
[generated excerpts](v050-access-paths-evidence/generated-excerpts.txt),
[access statements](v050-access-paths-evidence/generated-accesses.json) and
[conservative direct graph](v050-access-paths-evidence/direct-call-graph.json)
are the reproducible evidence; the script does not assign automatic safety verdicts.

## Important target paths

Source references below use MariaDB commit
`83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e`, archive
`36319b89c4373cf35e5c5c08686625eccae2816257b6982a4815ff552b945845`,
with the existing ordered portability patches applied and verified. C++ headers
and the key reviewed implementations are not patched to change these protocols.
Raw-reference source links are navigational; saved contexts/hashes bind the
actual analyzed prepared files. WASIX content is the existing archive
`55091ce6af5b549b3c97f61592bd2506e6a7e5da3588cb2f77a64388468ad231`,
whose existing provenance names commit `09503b230e8acc721c1e013ca28a41bf149e4ee2`.
Libc++abi guard files match the prior audit at LLVM source commit
`6bb93a243f6d15855f485f5aec3810d9e2de150d`.

### 1. Purge flags: the previous ordinary/atomic neighbor example

The source closes the **named** access paths for four neighboring bytes:
`m_initialized` is ordinary; `m_enabled` and `m_active` are `std::atomic<bool>`;
`skipped_rseg` is `Atomic_relaxed<uint8_t>`, which wraps `std::atomic` rather
than an ordinary byte. Its load/assignment operators issue atomic operations.
See [types and protocol](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/storage/innobase/include/trx0purge.h#L133)
and [the wrapper](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/include/my_atomic_wrapper.h#L35).

- Initialization: `_start` → Fn65 `__wasm_call_ctors` performs the ordinary
  byte/halfword zeroing. `srv_start` → `trx_lists_init_at_db_start` →
  `purge_sys.create()` initializes the selector/latches and sets
  `m_initialized=true`. After startup/DDL recovery, `srv_init_purge_tasks` →
  `coordinator_startup` atomically enables purge and submits the coordinator.
- Live: worker/coordinator paths read `enabled()` atomically and update
  `m_active` atomically. `stop_FTS()` waits on an acquire load of `m_active`;
  stop/resume additionally use the purge latch and task enable/disable protocol.
  Iterator history selection and `rseg_enable()` load/store `skipped_rseg`
  atomically; the latter also requires the rollback-segment exclusive latch.
  These are not ordinary accesses just because source uses assignment syntax.
- Teardown: `innodb_preshutdown` stops undo sources and calls
  `srv_purge_shutdown`; that atomically disables the coordinator, disables/drains
  its task, waits for worker/truncation tasks, then destroys their background
  contexts. Later `innodb_shutdown` invokes `purge_sys.close()`, which alone
  reads/writes ordinary `m_initialized`. `waitable_task::disable/wait` uses its
  mutex/CV and reference count; this is stronger evidence than the old timeline
  merely showing a later timestamp.

Generated addresses corroborate bytes `24020808..11`. Ordinary halfword
zeroing at `24020808` occurs in Fn65, **not a live purge worker**. The ordinary
live-lifecycle byte at +0 has named accesses only in create/close; workers use
the three atomic bytes at +1/+2/+3. The new narrow helpers no longer overlap
them with a 4-byte operand. Supported finding: the previous concrete neighboring
exposure is removed, and named initialization/shutdown paths support phase
separation. Conditions: source task/latch semantics must survive lowering;
arbitrary raw aliases and all constructor indirect targets are not proved.
No purge error, wrong SQL or premature destruction was reproduced.

### 2. ReadView, including high-frequency commit paths

`m_open` is an atomic boolean. All named runtime operations are `open`, `close`
and `is_open`; non-owner threads may inspect it alone, while reading view
contents uses `m_mutex`. The owner-only creator ID is a different member.
Purge uses `trx_sys.clone_oldest_view` → `read_view.append_to`, which locks
`m_mutex`, checks `is_open` and copies view contents. Monitor printing also
locks before inspecting the view.

Creation goes through `TrxFactory::init` → placement `ReadView()` and its
whole-object memset, before a transaction is taken from the pool and registered
with `trx_sys`. Normal transaction reuse closes/reopens the atomic flag; it
does **not** repeatedly run that constructor on a registered live view.
`trx_t::free` deregisters the transaction before returning it to the pool;
transaction-list freezing/removal and reference counts provide the source
lifetime protocol. Its correctness as a complete generated pointer/lifetime
algorithm is not newly proved by this field review.

The earlier unexplained commit offset +1384 is the inlined `read_view.close()`
target, corroborated by the source call and the +40 flag offset in Fn16684.
Fn18241's other byte store, +192, corresponds to clearing the atomic deadlock
victim flag. The same view-close store occurs in external/store-lock and
connection-close paths. This consolidates several high-count writers into an
already atomic live target instead of inventing another ordinary shared field.
These bindings are source/inlining corroboration, not a full DWARF layout proof.

The upstream [ReadView fast path](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/storage/innobase/read/read0read.cc#L201)
explicitly tolerates timing around reopening an unchanged view: purge can
temporarily retain history it could already remove. That is an upstream
protocol tradeoff, not a reproduced SQL corruption or a defect introduced by
the narrow writer. See the [view access contract](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/storage/innobase/include/read0types.h#L160).
Finding: named live flag accesses are atomic; ordinary whole-view initialization
has a source-supported pre-publication path. Complete list/alias and compiler
proof remains outside this scoped conclusion.

### 3. AHI search hints and the halfword counter

`hash_analysis`, `n_hash_potential`, `last_hash_succ`, and `n_hash_helps` all use
`Atomic_relaxed`. Reads, assignments and increments go through its atomic API.
`search_info_update`, hash lookup/build and buffer block reuse/reset paths are
included in the source references; AHI-disabled runs still reset the block
halfword. Hints are deliberately approximate; actual hash lookup has page/latch
and record-checking paths rather than treating a hint as the record itself.

The potentially suspicious placement reset `ahi::operator=` is used by
`dict_index_t::clone()`: it allocates a **new receiver** before `*index=*this`,
then initializes its latch, heap and fields before returning it. It does not
reset the source's live AHI bytes. Buffer-block initialization/reuse relies on
the source page ownership/state/latch protocol; all **named** counter resets
remain atomic assignments. A full proof of every raw page/metadata alias during
buffer resize is not claimed.

Finding: the observed adjacent live hint accesses are atomic at their requested
width after integration; no ordinary named same-target accessor was found.
See [hint types](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/storage/innobase/include/dict0mem.h#L1059),
[counter type](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/storage/innobase/include/buf0buf.h#L872)
and [clone lifetime](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/storage/innobase/dict/dict0dict.cc#L1246).

### 4. Page-cleaner and LRU flags: correcting the earlier unknown binding

Fn18008 `buf_pool_t::LRU_warn` has exactly the two source flag writes:
`try_LRU_scan=false`, then `LRU_warned=true` if its atomic check was false.
Generated writes/checks and other LRU paths corroborate globals `15209756`
and `15209757` as those two fields. They are both `Atomic_relaxed<bool>`.
They should **not** be described as an established overlap with an ordinary
neighbor, or identified as the standalone `buf_page_cleaner_is_active` flag.
The latter has its own initialize/exit stores (corroborated at `24088372`).

Cleaner init sets the active flag before launching its detached thread. Cleaner
exit clears it under `flush_list_mutex` and signals completion; shutdown drains
I/O and threads before closing the buffer pool. `page_cleaner_idle_flag` is
also atomic: writes occur under `flush_list_mutex`, with documented lock-free
reads in flush-ahead. LRU wake/retry and warning-reset paths remain atomic even
when they use C++ assignment. Source evidence supports these bindings;
it is not complete symbol/layout or detached-thread alias proof.
See [field types/access protocol](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/storage/innobase/include/buf0buf.h#L1541)
and [cleaner lifecycle](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/storage/innobase/buf/buf0flu.cc#L2836).
Finding: the earlier observed adjacent footprint is explained by separate
atomic flags; the extra 32-bit operands are removed.

### 5. One-time C++ initialization guard

The actual generated Fn4053/4054/4055 select the libc++abi **GlobalMutex**
protocol, corroborated by calls to the same mutex address `15466096` and
normal byte1 accesses. Guard byte0 is only acquired atomically or released
atomically; acquire/release/abort manage ordinary init byte1 under the global
mutex and CV. Release publishes byte0 first, then completes byte1 and broadcasts
if waiters exist. Abort leaves byte0 alone and resets byte1 under the mutex.
They are now disjoint memory operands, so byte0's release cannot add a read/write
of the lock-protected byte1 as the old widened helper did.

This removes the concrete width mismatch without needing to argue that the old
four-byte CAS always preserved concurrent byte1 changes. It still depends on
publication ordering through native narrow acquire/release and correct mutex/CV
lowering. Published payload and destruction ordering are not generically proved
by the guard-byte inspection. [Pinned implementation](https://github.com/llvm/llvm-project/blob/6bb93a243f6d15855f485f5aec3810d9e2de150d/libcxxabi/src/cxa_guard_impl.h#L182).

### 6. Thread-pool creation pending flag

Every source reference is accounted for: initialization with ATOMIC_FLAG_INIT,
`add_thread().test_and_set()`, new-worker `clear()`, and exception-path `clear()`
if thread creation fails. No named ordinary runtime access to this flag exists.
The member is initialized before constructor body thread creation; the pool
destructor stops AIO/maintenance, wakes workers and waits under its mutex/CV
for `worker_end` to remove the last worker. Worker-end is the final pool access
in `worker_main`; it does not clear the flag again after the destructor's drain.
Ordinary neighboring statistics are no longer included by the native byte
operation. Scheduling/resource exhaustion can still delay or fail creation;
this correction does not guarantee startup latency or forced worker termination.
[Source lifecycle](https://github.com/MariaDB/server/blob/83e909fc2a0dbc394b4b683fb3fa2d7dcf26cc5e/tpool/tpool_generic.cc#L697).

### 7. The shared synchronization dependency: a concrete remaining boundary

Following protection through libc++/WASIX reveals a real mixed-access path,
not merely an unspecified possible neighbor:

| Actual guest path | Ordinary access | Atomic access to same word |
| --- | --- | --- |
| Fn93 `__pthread_mutex_lock` slow path | lock word at mutex+4; waiter count at +8 | CAS lock transitions; CAS-based waiter increment/decrement |
| Fn130 `__pthread_mutex_unlock` | waiter-count read; lock-word read for CAS retry | CAS clears/releases the lock word |
| Fn88 WASIX futex wait adapter | preliminary/post-wait ordinary word checks | canonical host repeats the value check with an atomic load before parking |

The named C source uses volatile words and native atomic primitives; generated
ordinary reads are plain Go reads. CAS retries preserve adjacent/value updates;
the ordinary read followed by CAS is **not** by itself a demonstrated lost
update. The host's AtomicWait holds `parkMu` while rechecking the value and
registering its channel; wake uses the same mutex, addressing the check/register
lost-wake window at that host layer. This does not prove all guest-side predicate,
CV, timeout or cancellation schedules. This dependency existed before the
writer integration and uses 32-bit words; another byte-width change cannot
resolve it. WASIX pthread join likewise uses ordinary detach-state reads;
its create implementation specifically keeps the pthread struct out of the
TLS initialization area to avoid later non-atomic overwrite. Join/lifetime
translation as a whole is not newly qualified here.

The [isolated executable probe](../../benchmarks/spikes/v050-access-paths/mutex_probe.py)
copies Fn88/89/90/93/130 bodies **byte-for-byte**, their complete direct function
dependency closure, canonical base and the four canonical host wait/wake
methods. It supplies separate per-agent stacks, TLS pointers and partial pthread
blocks, NORMAL mutex initialization, and explicit panic stubs for unused imports.
It does not execute the complete SQL guest or all mutex types/configurations.
The copied source and individual body hashes bind that distinction.

On native macOS27.0.1 arm64 / Go1.26.8, four agents perform 2,000 protected
updates while deliberately yielding inside the critical section:

| Backing / observation | Protected result / wait path | Detector / exit |
| --- | --- | --- |
| Heap, observed | PASS, 2,000; wait path observed | Normal exit; counts are scheduling-dependent |
| Heap, observed `-race` | PASS value, 2,000; wait path observed | **FAIL**, 22 race reports in the saved final run |
| Heap, observer disabled | PASS, 2,000 | Normal exit; no dispatch count collected |
| Production-style mmap, observed | PASS, 2,000; wait path observed | Normal exit |
| mmap, observed `-race` | PASS, 2,000; wait path observed | Zero reports, **no safety inference** |
| mmap, observer disabled | PASS, 2,000 | Normal exit; no dispatch count collected |

Use [exact results](v050-access-paths-evidence/mutex-results.json) for the actual
wait counts; they are not performance measurements or simultaneous-event counts.
The 22 reports are detector warnings from this run, not 22 independent defects
or SQL failures; report counts vary with scheduling.
Observation wraps only the host wait dispatch without reading guest memory;
control runs preserve the protected result. A preliminary fixture omitted the
TLS pthread pointers, falsely aliasing cancellation bytes. That scaffold was
fixed, and final assertions reject such Fn90 race evidence. Superseded numbers
are not attributed to the product. Initial fixture compile/setup errors are
also retained separately. No production function or failure oracle was weakened.

Supported finding: real converted mutex functions have instrumented ordinary/
atomic conflicts on heap in this bounded fixture. Protected values and progress
held in these runs; **SQL harm and a semantic violation of the original Wasm
were not reproduced**. The mmap execution does not make the conflicting
accesses disappear. Assembly also hides narrow accesses from Go's detector.
Both observations make “no report” inadequate as a general safety claim.

## Remaining writer families and completeness ledger

The inventory assigns every writer function exactly once to a primary family;
inlining can bring other families' accesses into the same function. Thus these
are coverage groups, not a claim of one variable per function or dynamic reach.

| Primary family | Functions | Source target/access classification |
| --- | ---: | --- |
| Guard | 1 | Byte0 atomic, byte1 ordinary under global mutex; detailed above |
| Thread pool | 2 | Atomic flag; initializer/worker/error/destructor paths above |
| ReadView/commit/connection | 5 | Atomic open/close plus atomic victim reset; detailed above |
| Purge/control | 6 | Atomic enabled/active/selector/thread-count-changed; ordinary initialization above |
| Encryption | 4 | `srv_encrypt_rotate` is an atomic global; payload/rotation ownership is not established by the flag alone |
| File settings/extension/corruption | 6 | `need_unflushed_spaces`, `being_extended`, `is_corrupted` are atomic targets; file metadata has additional locking/lifetime requirements |
| Recovery | 8 | Atomic `page_recv_t::being_processed`, `recovery_on`, and inlined rotation paths; object/map lifetime not fully alias-proved |
| Buffer load/abort | 3 | Atomic global abort flag; no named ordinary live accessor found |
| Startup/shutdown/DDL recovery | 4 | Inlined initialization/control stores across the same target families; all configurations/error unwinds not exercised |
| Deadlock | 4 | Atomic victim and `to_be_checked` flags; transaction reference/lock protocol remains required |
| AHI/buffer halfword | 7 | Atomic hints, counter and enable flag; fresh clone receiver; raw resize/page aliases remain outside proof |
| Buffer/I/O/resize | 12 | Atomic idle/active/LRU and reserved-slot targets; I/O callbacks and resize ownership have unproved aliases |
| Checkpoint | 2 | `log_t::need_checkpoint` is atomic; flag coverage does not prove every log ordering property |
| Table-cache warning | 1 | Static `std::atomic<bool>` flag with exchange; named references are declaration and warning exchange |
| **Total** | **65** | **147 generated writer sites included** |

### Facts, exclusions and unclosed properties

1. **Reproduced user harm:** no new SQL wrong result/hang/crash demonstrated.
   Prior exact-source SQL/consumer/lifecycle evidence remains historical evidence;
   no new full guest workload/race census was run in this task.
2. **Reproduced implementation-level conflict:** real mutex dependency functions
   in the final isolated heap fixture produce race reports. This is not labeled
   hypothetical, and is not relabeled as SQL data corruption.
3. **Source-supported exclusions:** important named live narrow targets use
   atomic APIs; the guard's ordinary byte is disjoint and mutex-protected; ordinary
   creation/reset occurs on startup or fresh receivers in reviewed paths;
   source stop/drain precedes reviewed destruction. These conclusions have
   stated ownership/synchronization assumptions, not unrestricted safety proofs.
4. **Unclosed:** implicit/raw aliases, indirect callback targets, allocator
   generations/page resize, generic bulk/SIMD overlap and compiler/native/Go
   ordering across all mixed accesses. The other 41 previously unobserved
   functions now have a static inventory/classification, **not new execution
   observations or a claim that all their lifetime paths were exhaustively proved**.

If stronger assurance is required, the next investigation should be bounded
around the demonstrated mutex/futex ordinary/atomic mapping and its wait/cancel/
join invariants, with native platform tests and explicit width/ordering oracles.
Changing only atomics or adding a mutex that ordinary accesses do not share
cannot establish the missing property. A general design would need consistent
ordinary, atomic and bulk access lowering, ownership/lifetime and compiler
constraints; the need for that broader implementation is a Human decision.
This is an identified boundary, not a promise that unbounded testing eventually
proves the whole guest safe.

## Verification, provenance and reproduction

The [baseline receipt](v050-access-paths-evidence/baseline.json) checks a commit
object. The [source preflight](v050-access-paths-evidence/source-preflight.json)
and [analysis identities](v050-access-paths-evidence/identity.json) bind archives,
ordered patches, selected source bytes and canonical provenance
`98e389d019f4a2d09350bace9c8c691de8926bcffb9d1781c9d9ce1880b64a97`.
No runtime/source-identity migration or new generation occurred in this
analysis task; the prior independent regeneration remains valid for unchanged
runtime bytes. Snapshot guest-ID rejection remains unchanged.

The previously pending [Ubuntu native CI](https://github.com/masahitojp/mariamem/actions/runs/38255402646)
completed **PASS** at exact source `20a9ca9156455939f4903d681345bd9868b1ac51`.
Its saved source/platform/results/base/guest receipts confirm native Ubuntu
24.04 x86_64, Go1.26.8 and the four real-Wasm heap/mmap configurations. This
closes the earlier narrow integration's native-platform pending check. It does
not execute this new mutex probe or prove this access-path analysis; native
Ubuntu execution of the **new mutex probe is SKIP** (no local native runner).
Native macOS15 execution remains SKIP (local macOS27.0.1). Emulation is not used
as native evidence.

| Current-task check | Outcome |
| --- | --- |
| Pinned archive/source/patch/function/provenance verification | PASS; 7,316 extracted C/C++ files checked, exact 65/147 inventory |
| Source scanner negative controls | PASS, 4 tests; changed archive/source/unregistered file rejected |
| Python tooling syntax | PASS |
| Canonical generated-source verification | PASS, unchanged source |
| Actual mutex-body fixture normal/control values | PASS heap/mmap; normal and observer-disabled runs |
| Actual mutex-body heap `-race` | Expected diagnostic **FAIL**, 22 reports preserved; values passed |
| Actual mutex-body mmap `-race` | Execution PASS; detector zero remains inconclusive |
| Public-source and saved-evidence/diff/reference checks | PASS before commit |
| Broad runtime/consumer reruns, Qualification/Product Validation | NOT RUN; unchanged runtime, scoped analysis/probe only |

Recreate an isolated workspace at the baseline, download the two archives using
the canonical hash-checking helper, extract them, and apply MariaDB portability
patches with `guest_input.apply_series`. Obtain the two fixed libc++abi guard
files and compare their recorded hashes. Then run:

```sh
python3 benchmarks/spikes/v050-access-paths/scan.py \
  --mariadb-archive /absolute/path/mariadb-12.3.3-source.tar.gz \
  --wasix-archive /absolute/path/wasix-libc-source.tar.gz \
  --mariadb-source /absolute/path/prepared-mariadb \
  --wasix-source /absolute/path/wasix-libc \
  --cxa-source /absolute/path/pinned-cxa-files \
  --output /absolute/path/fresh-scan
python3 benchmarks/spikes/v050-access-paths/mutex_probe.py \
  --scan /absolute/path/fresh-scan --output /absolute/path/fresh-mutex-probe
python3 -m unittest discover -s benchmarks/spikes/v050-access-paths -p 'test_*.py' -v
```

Use Go1.26.8 and an absolute task-local GOCACHE. Mutex probe packaging and
partial TLS are explicitly different from a full guest build; unused imports
panic and real function/host/base bytes are bound by the result receipt.
Saved raw/sanitized file hashes are in
[saved-files.json](v050-access-paths-evidence/saved-files.json). Workspaces,
downloads, source copies, generated probe modules and caches are disposable
after source/results are committed. Stop here for Human Review.
