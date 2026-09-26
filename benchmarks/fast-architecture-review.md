# 0.2 FAST: architecture review

Review date: 2026-09-27. Repository reviewed at
`8c93ddb`, using the exact benchmark inputs documented in
[the baseline analysis](fast-baseline-analysis.md). This is an investigation
plan, not an implementation decision. No new performance measurements or
optimizations were made for this review.

The objective is cheap independent MariaDB instances in **latency, CPU and
memory**, not merely a faster `Fork()` return. Exploratory targets are
Fork → first usable SQL p50 <250 ms and p95 <500 ms. They are not promises;
the same readiness definition must include deferred work needed by that SQL.

## 1. What the measurements actually say

### Facts

The canonical Go measurement is on macOS 15.7.9 arm64 with 3 reported CPUs,
Wasmer 7.4.2, an already compiled AOT artifact and a 1,000-row InnoDB fixture.
There are 20 measured lifecycle trials after warmup. Ubuntu product correctness
is supported, but an equivalent Ubuntu performance baseline is still missing.

| Go measurement | ×1 p50 / p95 ms | ×8 p50 / p95 ms |
| --- | ---: | ---: |
| Fork → first SQL, individual DB | 1,224 / 1,936 | 3,384 / 4,710 |
| Whole parallel group ready | 1,224 / 1,936 | 4,222 / 5,240 |
| `mysql_server_init()` | 762 / 1,446 | 2,072 / 3,387 |
| Guest snapshot restore copy | 156 / 225 | 360 / 682 |
| Host metadata/snapshot validation | 138 / 229 | 509 / 934 |
| Outside host startup trace | 112 / 134 | 296 / 440 |
| Spawn-to-ready envelope residual | 56 / 76 | 111 / 340 |

Rows are nested/overlapping scopes, not additive percentile totals. The
authoritative measured **process spawn** is 3.2/4.2 ms at ×1, not the roughly
one-second spawn-to-ready envelope. Bootstrap connection/initial SQL inside
the guest takes <1 ms p95. External connection is 5.9 ms median; first fixture
query is 1.1 ms. Steady SELECT is 0.131 ms median.

Sampled runtime CPU is approximately 0.98/0.93/1.01 CPU seconds per DB at
×1/4/8, derived from group medians. Sampled runtime peak RSS is
338/1,377/2,245 MiB per group. These are sampled observations, not complete CPU
accounting or unique physical memory. They establish substantial cost, not
which allocation owns it or how much is actually shareable.

### Inferences and numerical limits

Initialization is about 60% of individual Fork latency across all three
concurrency levels. Its ×1→×8 median increase is 1,311 ms, larger than
validation (+371 ms) or restore (+204 ms). Startup reuse or much cheaper engine
initialization must therefore be investigated directly. Layer count and process
count do not explain these measurements by themselves.

The following **derived thought experiment** subtracts named durations from
each of the 20 ×1 raw samples, then recomputes percentiles. It holds everything
else fixed and assigns zero cost to the removed work; it is not a prediction
for a new implementation or an additive-median calculation.

| Hypothetically free work | Remaining p50 / p95 ms |
| --- | ---: |
| Restore copy only | 1,096 / 1,742 |
| `mysql_server_init()` only | 481 / 602 |
| Both initialization and restore | 321 / 426 |

Thus a storage-only solution does not address the present latency target.
Even free initialization leaves meaningful validation/materialization/setup
work. Reaching the target requires a combination, or a large change in what
these stages actually do. Sharing must also reduce paid CPU or memory;
moving work before the timer is insufficient for the product goal.

### Unknowns

`mysql_server_init()` combines engine allocation, file access, recovery/open
work, thread creation and synchronization. We have not separated CPU execution
from waits inside it. The envelope residual includes pre-main runtime/CRT
initialization **and** post-marker output/transport/scheduling; it is not a
Wasmer timer. No per-stage CPU, bytes read/written, page-fault, dirty-page or
unique-memory breakdown exists. Hosted-run variance is substantial.

## 2. Cost model and actual implementation

The current public `Fork` is a **cold restart from files**:

```text
Snapshot.Fork
  → validate native bundle / create owned runtime directory
  → validate module + snapshot inventory
  → start Wasmer using the existing AOT artifact
  → copy host snapshot files into guest /mariadb
  → mysql_server_init + bootstrap
  → host MySQL listener → driver connection → first SQL
```

The Go host is already in the consumer process. Each DB gets a Wasmer process,
its own MariaDB engine and its own runtime filesystem. `/mariadb` is an
**unmounted Wasmer memory filesystem**; `/snapshot-in` and `/snapshot-out` are
host mounts. A host runtime directory is not the MariaDB datadir.
See [public startup](../mariamem.go), [host startup](../internal/host/server.go),
[process launch](../internal/guest/guest.go),
[guest lifecycle](../guest/resident.inc) and [copy code](../guest/snapshot_fs.inc).

There is concrete repeated work:

- A Go Start/Fork hashes the AOT three times: manifest verification in
  `artifacts.Resolve`, its `ModuleBuild` call, and host `ModuleBuild`. Runtime
  and sidecar hashes are also checked. On macOS platform detection calls
  `sw_vers`. Much of this precedes host instrumentation. Snapshot data inventory
  is validated once per **Go** Fork; Python adds its own validation.
- Snapshot stops/joins sessions and calls `mysql_server_end`, copies the guest
  datadir to the host transfer directory, then publishes a second copy.
  Publication hashes transfer and destination inventories; the public Go API
  validates destination again. Its measured 301 ms export and 348 ms publish
  medians are combined shutdown/copy and copy/hash/commit buckets respectively.
- Fork then reads the saved files again into its private memory filesystem and
  initializes a new engine. Prepared SQL data is reused; initialized engine
  state is not.

These checks protect artifact compatibility, corruption detection and complete
snapshot publication. Removing repeated work requires carrying validated
identity and enforcing backing-store ownership, not caching an arbitrary path
forever. Current paths are mutable; neither a path nor a hash taken earlier
makes future contents immutable. See [artifact resolution](../internal/artifacts/artifacts.go)
and [snapshot inventory/commit marker](../internal/snapshot/snapshot.go).

Memory has several independent owners: AOT mappings, runtime metadata/stacks,
WASM linear memory and engine heap, runtime filesystem contents, and host/driver
state. The pinned guest requests **256 MiB initial linear memory**, 2 GiB maximum,
but configures only a **16 MiB InnoDB buffer pool** and a 2 MiB log buffer.
These settings do not prove residency or attribution; “hundreds of MiB equals
the buffer pool” is unsupported. The source already disables networking/binlog
and reduces caches/IO-thread settings. See pinned lite4mariadb
[startup options](https://github.com/shyim/lite4mariadb/blob/24be9371a2f6c71250a2356631ad6feab2280b02/wasm/lite4mariadb.c)
and [WASM link settings](https://github.com/shyim/lite4mariadb/blob/24be9371a2f6c71250a2356631ad6feab2280b02/wasm/CMakeLists.txt),
with [local overlays](../guest/source.patch).

## 3. Candidate architectures

### A. Keep the current boundaries; remove repeated work and reduce initialization

**Mechanism/cost affected:** pass a validated bundle identity through a startup,
reuse truly immutable prepared inputs, combine copy/hash passes where safe,
and profile before changing engine configuration, allocation or initialization.
This targets validation, materialization and possibly the dominant init bucket.
Existing AOT already avoids compilation during Fork.

**Potential:** duplicate-read elimination can reduce CPU/I/O and ×4/8 contention
without a runtime migration. Only a demonstrated reduction inside engine init
could make this option alone competitive for the latency target. Reducing
unnecessary committed/initialized memory could improve RSS and startup CPU;
current data does not establish that such memory exists or is avoidable.

**Risks/scope:** plumbing validated identities is small; changing integrity
lifetime is a correctness decision. Engine tuning is bounded only if profiling
finds a specific cause. Do not disable transactional/recovery machinery to win
a benchmark. Real MariaDB, multi-client behavior and instance-fatal cancellation
must remain intact. No public API change is necessary; both platforms can retain
their process model.

**Cheapest experiment:** separately measure native hashing, snapshot hashing,
engine init CPU/waits and memory growth. In a disposable branch, compare one
validated immutable bundle against current repeated validation, then one
profile-supported initialization change. Falsifier: the dominant init cost
persists after secondary work is removed, or savings trade away SQL semantics.

### B. Filesystem sharing / CoW while retaining cold engine startup

**Mechanism/cost affected:** an immutable prepared filesystem plus independent
writable storage per instance; avoid eagerly copying every saved byte.
Host reflinking alone leaves today's `/snapshot-in`→memory-FS copy intact.
To remove it, the guest must use an isolated host-backed datadir or a lazy/CoW
runtime filesystem in place of the current private memory FS.

**Potential:** lower restore/export CPU, storage and duplicated file backing,
especially for larger mostly-read fixtures. ×4/8 copy traffic may fall. Fresh
`mysql_server_init()` still runs and keeps a private buffer pool/heap. File
sharing does not automatically share those structures or all observed RSS.
Engine startup writes may quickly dirty much of the supposedly shared state.

**Risks/scope:** preserve independent write/truncate/rename/unlink behavior,
file locking and descriptor semantics. Never use writable hardlinks. An atomic
file clone is not a consistent live multi-file database snapshot; retain a cold
or otherwise proven consistent capture. Host-backed storage changes syscall
and page-cache costs and may move memory outside process RSS.

macOS APFS offers cloning, while Linux reflink requires a supporting filesystem
and same-filesystem source/destination. Ubuntu 24.04 as an OS contract does not
guarantee either. Capability detection and a correct fallback are necessary;
no special filesystem may be silently added to the support contract.
See [Apple's APIs](https://developer.apple.com/library/archive/documentation/FileManagement/Conceptual/APFS_Guide/ToolsandAPIs/ToolsandAPIs.html)
and [Linux FICLONE](https://man7.org/linux/man-pages/man2/FICLONE.2const.html).

**Cheapest experiment:** a storage-only prototype keeps normal engine startup
and serves one prepared datadir through private-write backing. Measure bytes
read/copied/dirtied through first SQL and first representative write, unique
memory, ×1/4/8 latency and source/child deletion isolation. If most files copy
up during initialization, or initialization dominates unchanged, this is a
storage improvement/complement rather than the primary FAST architecture.

### C. Host-owned VFS with immutable lower state and private upper state

This is a concrete way to implement B with controlled ownership rather than
relying on host filesystem capabilities. It may remain inside a customized
external Wasmer runtime; embedding in Go is not a prerequisite.

**Mechanism/cost affected:** share immutable data backing, create inexpensive
per-DB namespace/metadata, and copy changed pages or files into a private upper
layer. It can remove eager restore and enable cheap filesystem capture. It
does not by itself preserve initialized MariaDB heap, threads or buffer pools.
CPU/RSS benefit depends on copy-up granularity and the first-write working set.
Whole-file copy-up can be expensive for InnoDB shared tablespaces/log files.

**Reference applicability:** at pglite-go commit
`e0e93e1ab795753e95e7af0f43bf010dd3ecf85f`,
[the VFS](https://github.com/moriyoshi/pglite-go/blob/e0e93e1ab795753e95e7af0f43bf010dd3ecf85f/vfs/vfs.go)
has a read-only lower, writable upper, whiteouts and whole-file copy-up.
Its [Open path](https://github.com/moriyoshi/pglite-go/blob/e0e93e1ab795753e95e7af0f43bf010dd3ecf85f/pglite.go)
loads a bundled lower, restores or initializes a cluster, then starts a backend.
It is evidence for a useful VFS boundary, not evidence that initialized
PostgreSQL instances are cheaply cloned. PGlite's single-connection execution
model also differs from mariamem's threaded sessions
([PGlite documentation](https://pglite.dev/docs/multi-tab-worker)).

**Required boundary changes:** today's Go host controls a Wasmer CLI child; it
cannot simply pass a Go `fs.FS` across that process boundary. A Wasmer filesystem
implementation/custom runner, a host service with measured IPC cost, or an
embedded integration is needed. The latter must supply this guest's WASIX
threads, synchronization, filesystem and exception requirements. pglite-go's
Emscripten/WASI adapters are not a drop-in WASIX implementation.

**Risks/scope/platform/API:** medium-to-large filesystem/runtime work on both
platforms. Synchronization, sparse writes, descriptor offsets, rename/deletion,
flush ordering and complete export need tests. Existing `Snapshot` can remain,
but base lifetime must extend past startup while a child lazily reads it.

**Cheapest experiment:** test a read-only lower/private upper at the existing
WASIX filesystem boundary, first with file operations and then two real DBs.
Track copy-up bytes by file and page, init duration and write latency. A fixture
that fits in one giant eagerly copied file should be an explicit falsifier for
an overly coarse overlay, not excluded from the benchmark.

### D. Embedded/shared runtime with fresh MariaDB instances

**Mechanism/cost affected:** reuse engine/module/AOT mappings and runtime setup
across independent instances, through an embedded runtime or a runtime service.
This may remove some of the unobserved pre-main cost and shared code/metadata
allocations. Eliminating the measured 3.2 ms spawn is not sufficient motivation.
Fresh instantiation still executes restore and `mysql_server_init()`.

**Potential:** runtime resource sharing could improve CPU/RSS at ×4/8 if those
resources are actually duplicated. Existing file-backed code may already share
physical pages across processes; summed RSS cannot decide this. No measured
number justifies a large latency benefit from embedding alone.

**Risks/scope:** large compared with validation cleanup. The current fatal-query
path kills one process group. A shared process must cancel/terminate one DB's
guest and background threads without poisoning siblings or the Go caller.
Runtime panic/abort and resource leaks become a wider failure domain. Embedding
an alternative engine also requires proving the WASIX ABI; changing engines
does not come for free. Both platforms need equivalent isolation and teardown.
The public API can stay stable if these guarantees hold.

**Cheapest experiment:** after memory attribution, compare fresh instances using
one shared compiled module with separate-runtime instances, retaining cold
MariaDB init. Include timeout, sibling survival and repeated cleanup. Reject
this as the primary latency strategy if only the small residual/spawn changes;
retain it only if unique memory/CPU or enabling another option justifies scope.

### E. Derive instances from initialized MariaDB state

**Mechanism/cost affected:** preserve a prepared, initialized engine and derive
independent continuations, potentially with memory CoW and filesystem CoW.
This is the option that directly attempts to avoid repeated 762 ms initialization
and its CPU work. It has the largest potential and the largest unresolved
correctness burden. Bulk checkpoint restore may avoid init CPU but still copy
hundreds of MiB; low latency does not establish low incremental memory.

The capture must account for engine heap/buffer pools, WASM memory/globals,
all relevant stacks/TLS/threads, locks/futexes, files and offsets, runtime
resources, clocks/timers and host communication. File state must match memory
state. An idle SQL endpoint is not a stopped engine: the source initializes
InnoDB thread-pool/monitor/master work and a MariaDB timer thread, in addition
to lazy session workers. Closing sessions does not make those threads disappear.

**Existing capability is insufficient as a shortcut.** The pinned Wasmer 7.4.2
[proc_fork](https://github.com/wasmerio/wasmer/blob/v7.4.2/lib/wasix/src/syscalls/wasix/proc_fork.rs)
shares the filesystem interface and calls `memory.copy`.
[WasiEnv::fork](https://github.com/wasmerio/wasmer/blob/v7.4.2/lib/wasix/src/state/env.rs)
creates a child main thread; it does not reproduce all sibling MariaDB threads.
The inspected [mapping copy](https://github.com/wasmerio/wasmer/blob/v7.4.2/lib/vm/src/mmap.rs)
allocates and copies bytes, despite a CoW comment elsewhere. Neither independent
databases nor cheap shared memory follows from using that syscall.

Three variants need different proofs:

- **OS process clone:** native CoW is attractive, but copying a multithreaded
  runtime leaves thread/lock/descriptor continuation problems; fork-and-exec
  would discard the initialized state. Inherited pipes/files must not share
  mutable external endpoints. A Go/Rust host process clone is not a supported
  ready-engine template merely because the OS has `fork`. On Linux, only the
  calling thread survives and the child of a multithreaded process is restricted
  to async-signal-safe operations until exec
  ([fork contract](https://man7.org/linux/man-pages/man2/fork.2.html)). This is
  not a recipe for continuing a live MariaDB/runtime safely.
- **Runtime checkpoint/restore:** Wasmer has journal and
  [thread restoration code](https://github.com/wasmerio/wasmer/blob/v7.4.2/lib/wasix/src/syscalls/journal/restore_snapshot.rs).
  Current mariamem launch does not use it. Binary feature availability, support
  for this guest's complete state, replay side effects, independent files and
  restoration cost have not been proven. This deserves a bounded feasibility
  probe, not a claim of an existing solution.
- **Explicit engine-safe template point:** stop or park engine activity and
  rebind child resources under a documented protocol. This could offer stronger
  control, but may require invasive MariaDB/runtime changes. A pre-engine
  template is easier but leaves the dominant cost; a post-engine template must
  reconstruct every necessary continuation. Removing background machinery to
  simplify cloning may change MariaDB behavior.

**CPU/RSS/concurrency/platform/API:** true sharing could amortize template CPU
and private memory across ×4/8; early engine writes may destroy sharing quickly.
Native checkpoint mechanisms are platform-specific, and Linux-only feasibility
does not satisfy macOS support. Runtime-level serialization is potentially more
portable but AOT/native stack and CPU identities can constrain images. Cold
snapshots should remain the portable preparation/export representation unless
a deliberate API decision changes that; an ephemeral warm template can be an
internal derivative. A live template cannot silently replace persistent files.

**Cheapest experiment:** before MariaDB, use a two-thread WASIX probe with
mutex/condition state, open files, timer activity and memory growth. Require
independent file mutations and functioning workers in two continuations.
Then capture one initialized real fixture and test divergent transactions,
DDL, session state, timeout isolation and teardown in both children. Measure
capture, restore, first SQL/write, dirty/unique memory and repeated burst cost.
A hung worker, shared file or broad fatal cancellation falsifies the mechanism
even if `SELECT 1` succeeds once.

### F. Prewarm pools or share one MariaDB server

**Disposable prewarm pool:** prepare real independent DBs before demand and
consume each once. It can hide Fork latency and preserve behavior, but retains
roughly per-instance CPU/RSS and shifts cost into replenishment. On exhaustion,
latency returns; a pool of eight is not cheap isolation merely because the first
eight acquisitions are fast. Portable, moderate internal scope; Snapshot/base
ownership and bounded resource budgeting still matter. Cheapest experiment:
measure template+pool construction, idle footprint, two consecutive bursts and
replenishment CPU, including exhaustion. Keep only as an explicit latency/memory
tradeoff if the product accepts it, not as proof of the FAST goal.

**Database/schema per test within one server:** shares engine initialization
and buffers, but also global variables, failure domain, server resources and
cross-schema access. The existing 16 slots are independent SQL sessions in
**one** DB engine, not 16 independently disposable database instances. Whole-DB
invalidation after one interrupted query would affect unrelated tests. This
does not preserve today's isolation contract and is not a transparent candidate.
Likewise, rollback-only reuse does not restore arbitrary DDL/session/global state.
No implementation experiment is needed before a separate product decision.

## 4. Comparison matrix

Benefits below are mechanisms/potential, not benchmark predictions. Combinations
are possible, especially validated immutable inputs + storage sharing + a
proven initialization strategy.

| Candidate | Single Fork / ×4/8 latency potential | CPU / incremental memory | Scope and semantic risk | Portability | Public API |
| --- | --- | --- | --- | --- | --- |
| A: current boundaries | Validation savings known; target depends on init findings | Less duplicate work; memory gain unproven | Small plumbing through potentially engine-sensitive changes | Existing two platforms | No change needed |
| B: filesystem CoW | Removes eager copies only when guest backing changes; init remains | Less copy CPU/file backing; private engine remains | Medium; storage/ownership correctness | Filesystem capability varies; fallback required | Keep Snapshot; adjust internal ownership |
| C: runtime/host VFS | Like B; read/copy-up granularity controls scaling | Share untouched files; engine heap remains | Medium/large; WASIX integration and full FS semantics | Can cover both with validated adapters | Keep Snapshot; pin bases for children |
| D: runtime sharing | Affects an unmeasured fraction, not init by itself | Shared code/runtime possible; private engine remains | Large; fatal-error blast radius and thread cleanup | Both require runtime support | No change if failure isolation preserved |
| E: initialized continuation | Directly avoids dominant init; must also address copying/validation | Amortized init; true CoW could reduce unique pages, full-copy restore cannot | Highest; consistent multi-thread/memory/FS state | Unproven on both; avoid Linux-only commitment | Retain cold Snapshot; hot state lifetime must be explicit internally |
| F: prewarm pool | Fast while stocked; burst/refill tails remain | Pays startup early; idle RSS grows | Moderate; deterministic discard/replenishment | Existing two platforms | Can remain internal, resource policy needed |
| F: shared server/schema | Amortizes most startup | Shared buffers/engine | Changes isolation/failure semantics | Portable server model | Product/API decision required; excluded as transparent replacement |

## 5. Recommended investigation sequence

Do not run every option as a full prototype. Use successive gates to eliminate
unsupported explanations and reserve invasive work for evidence-backed paths.

1. **Attribute initialization and memory, then remove one known confounder.**
   Split the dominant bucket into a few natural engine stages; distinguish CPU,
   waits, file activity and memory commitment. Inventory threads at ready.
   Attribute private memory to linear memory, runtime FS and other mappings
   using each OS's available measures; record limitations. Compare current
   validation with within-call identity reuse on immutable inputs in a small
   branch. Repeat ×1/4/8 with the same fixture, plus small/medium fixture sizes
   and Ubuntu. This separates intrinsic engine work from redundant validation,
   filesystem traffic and runtime allocation. Do not turn this into broad tuning.
2. **Run the tiny continuation feasibility probe alongside a bounded storage
   probe.** The thread/file test in E answers whether existing runtime mechanisms
   can preserve independent initialized state at all. The B/C test answers how
   much data initialization immediately reads or copies up. These distinguish
   “keep cold startup but make backing cheap” from “must preserve hot state.”
   Do not build a Go runtime embedding merely to conduct the filesystem test.
3. **Choose one MariaDB experiment from those results.** If initialization is
   reducible without semantic change, test A plus validated/shared backing.
   If it remains dominant and the continuation probe passes, test one complete
   initialized fixture under E. If continuation fails, record the exact missing
   thread/resource mechanism and request a scope decision before redesigning it.
   Test D only if measured runtime/mapping cost warrants it or it is necessary
   to enable the chosen prototype. Test pooling only with explicit total-cost
   accounting; do not use it to conceal an unresolved cost problem.

Every experiment retains real SQL, existing multiple sessions, snapshot source
consumption, temporary/explicit ownership, and whole-instance invalidation
without harming sibling DBs. Include parent Snapshot.Close while children run,
divergent writes/DDL, repeated create/dispose and failure cleanup. Correctness
precedes timing claims. No Testcontainers comparison is part of this review.

## 6. Decision point

**No final production architecture is supported yet.** The evidence does support
prioritizing initialization and memory attribution over runtime replacement,
and checking initialized-state feasibility before investing in it.

Choose A (possibly with B/C) if a semantics-preserving prototype reaches the
exploratory latency targets with lower CPU/unique-memory cost across repeated
×1/4/8 runs and representative fixtures. Choose B/C as a primary storage layer
only if its measured private-write working set stays small and it preserves
filesystem/lifetime semantics; it still needs an answer for engine startup.
Choose E only after complete thread/resource restoration and child independence
work on both platforms, and copying/first writes do not erase its advantage.
Choose D only for measured savings or a demonstrated enabling role. Do not
choose F as “cheap” based solely on acquisition latency.

Report per-instance and group readiness separately. Account for template setup,
amortized CPU, idle template/pool cost, memory at ready and after writes, and
refill/cleanup tails. Decide a numerical CPU/private-memory budget before a
production commitment; this review has evidence of cost but no agreed budget
or reliable unique-memory baseline. A p50 win with large ×8 p95, background
CPU, memory or correctness regressions does not meet the goal.

`Snapshot` should remain the public prepared-state concept during investigation.
Its source-consuming semantics need not reveal the implementation strategy.
Today explicit paths survive Close, temporary paths are owned, and Go pins the
snapshot only through startup because children have complete copies. Any lazy
base must instead remain available for child lifetime, even after Snapshot.Close.
Current path persistence is not an `fsync` crash-durability guarantee; Go also
has no public reopen-by-path method, whereas Python has `Snapshot.open`.
An internal warm derivative can coexist with cold export; whether a future
public template/cache control is necessary is a later evidence-based API review,
not a prerequisite for these experiments.

### Source trail

Repository behavior references above are relative links at review commit
`8c93ddb`. Additional evidence is in [session management](../guest/resident.inc),
[public Snapshot/Fork](../snapshot.go), [timing markers](../guest/startup_timing.inc),
[guest instrumentation patch](../guest/source.patch) and
[pinned input provenance](../release/inputs.lock.json).
Pinned MariaDB background-work paths inspected were
`storage/innobase/srv/srv0srv.cc`, `srv0start.cc`, `sql/mysqld.cc` and
`mysys/thr_timer.c` in lite4mariadb revision
`24be9371a2f6c71250a2356631ad6feab2280b02`.
Wasmer filesystem sharing was checked in 7.4.2
`lib/wasix/src/fs/mod.rs`, `lib/wasix/src/state/mod.rs` and
`lib/virtual-fs/src/mem_fs/filesystem.rs`, in addition to the linked fork/memory
implementations. Source inspection establishes constraints, not successful
checkpoint support for this guest.
