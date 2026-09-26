# MariaDB initialization and memory attribution: Step 1

This investigation follows Step 1 of [the architecture review](fast-architecture-review.md).
It adds observations, not an optimization or an architecture decision.
The detailed cross-platform measurements are **pending the dispatched CI run**;
this document records the actual source boundaries, measurement interpretation
and questions to resolve from its artifacts. It must not be read as a completed
numerical attribution. Raw benchmark JSON remains ignored.

## Evidence already established

**Measured fact, previous run:** the [baseline analysis](fast-baseline-analysis.md)
reports Go Fork → first SQL 1,224 ms p50 at ×1; `mysql_server_init()` 762 ms,
restore copy 156 ms, host validation 138 ms. Initialization reaches 2,072 ms
p50 at ×8. These nested percentile values are not additive. No new sub-stage
numbers are inferred from them.

**Source fact:** the guest links MariaDB's embedded server. Its
`mysql_server_init()` enters `init_embedded_server()` in `libmysqld/lib_sql.cc`,
which includes `sql/mysqld.cc` and calls `init_server_components()`. Plugin
initialization calls InnoDB's `innodb_init()` in `handler/ha_innodb.cc`, which
calls `srv_start()` in `srv/srv0start.cc`. It is a fresh engine startup after
the filesystem restore, not reuse of an initialized InnoDB instance.

## Initialization subdivisions

The pinned source is instrumented by fail-closed insertions in
[`guest_init_hooks.py`](../scripts/guest_init_hooks.py); source preparation and
WASM provenance hash the modified files. The reporter retains these scopes:

| Scope | Real work between the markers |
| --- | --- |
| Embedded options | Embedded thread/options/common-variable setup before server components |
| Global components before plugins | Server globals, caches, timer/logger/statistics setup |
| All plugins (enclosing scope) | All storage-engine/plugin initialization, including InnoDB |
| InnoDB options | Handlerton/global allocator setup and parameter validation before `srv_start` |
| InnoDB runtime before buffer pool | `srv_boot`, AIO setup, error file and file-system structures |
| Buffer pool creation | `buf_pool.create()` |
| Log/lock/page-cleaner setup | Log/receive/lock structures and initial page-cleaner startup |
| Tablespaces/log/recovery/dictionary | Open/create system tablespace and logs, recovery/dictionary initialization |
| Doublewrite/undo/transaction setup | Doublewrite/undo and transaction-system initialization before rollback-phase completion |
| Metadata/temp tablespace/background setup | Monitor/dictionary-stats/FTS setup, system-table checks, binlog startup hook, temporary tablespace and master timer |
| Remaining InnoDB startup | Buffer-load/remaining startup work before `srv_start` returns |
| Post-plugin components/DDL | Remaining component setup through `ha_signal_ddl_recovery_done` |
| Remaining embedded setup | Embedded ACL/time-zone/user/DDL setup through initialized flag |

Markers also retain a complete embedded-init enclosing interval and the
existing restore/server-init/bootstrap/ready stages. Some source statements
between nested marker pairs remain outside the listed subdivisions; do not
force the table to sum to the enclosing timer. Cold Start and seeded Fork
follow different create/open/recovery branches inside the same scopes.

## CPU, file activity and waiting

Each marker records monotonic wall time and available OS process/current-thread
CPU clocks via WASIX. **Definition:** process CPU includes all Wasmer process
threads, including work concurrent with the engine's initialization. It can
exceed wall time. Current-thread CPU is not a persistent MariaDB-thread identity;
unavailable, zero or regressing clocks are not evidence of zero CPU. The usual
sampled runtime CPU remains available as a separate correlated observation.

POSIX link wrappers record successful direct guest calls to open/read/write,
pread/pwrite and truncate, attributed by `/mariadb` filename and stage. The
guest datadir lives in Wasmer's memory filesystem. **Unknown:** physical disk
traffic, libc-internal buffered I/O, mmap file traffic, failed-call time and
exclusive filesystem wait. Summed I/O call time can overlap threads and
includes syscall/runtime execution. Wall minus CPU is not a reliable waiting
timer. A stage with substantial CPU and little observed I/O supports further
CPU/memory investigation; it does not by itself establish a CPU-bound cause.

The final file list is captured at ready preparation, before the public first
SQL. It is not a before/after disk-content diff. Per-file opens/truncates,
read/write bytes and call time distinguish read-heavy recovery/open work from
observed initialization writes. Missing activity must be treated as a coverage
blind spot, not proof that no I/O happened.

## Memory and thread attribution

**Source facts:** initial WASM linear memory is 256 MiB, with 2 GiB maximum;
configured InnoDB buffer pool is 16 MiB and log buffer 2 MiB. Those are capacity
and configuration values, not measured RSS contributions.

`buf_chunk_t` calls `my_large_virtual_alloc()`; the pinned WASM branch in
`mysys/my_largepage.c` uses page-aligned allocation and explicitly zeroes its
requested range instead of reserving inaccessible `PROT_NONE` pages. The buffer
pool timer and aligned-allocation counter observe this branch. Its existence
does not establish how much of initialization latency or RSS it explains.

| Observation | What it establishes | What it cannot establish |
| --- | --- | --- |
| WASM `memory.size` at markers | Linear-memory capacity/growth | Committed/resident or useful bytes |
| Wrapped malloc/calloc/realloc/aligned allocation balance and request totals | Observed C allocator changes/churn by stage | Total live heap, fragmentation, unwrapped libc/Rust allocations |
| Wrapped mmap/munmap balance | Observed guest mapping length changes | Additional physical RAM; mappings can overlap/remap and WASIX may emulate them inside linear memory |
| Ubuntu smaps/rollup/status | Mapping RSS/PSS/private pages and high-water observations | Ownership of anonymous regions by MariaDB vs Rust VFS/runtime |
| macOS vmmap summary | Available OS mapping/category/residency accounting | Complete per-object ownership or unique physical RAM |
| OS thread inventory + successful guest pthread creates | Ready OS threads and stage-level create counts | Live MariaDB thread count or engine role from runtime thread names alone |

Allocator balance may be negative when a pre-enable/unwrapped allocation is
freed through a wrapped call. It excludes internal allocator metadata and Rust
filesystem/runtime objects. Do not sum wrapped heap, mmap and linear-memory
capacity as disjoint allocations. RSS sums across DBs may count shared AOT/system
pages repeatedly; use PSS/private observations where available.

**Source thread-role inventory, not a measured live count:** server timer setup;
InnoDB generic thread pool/AIO workers; page cleaner; periodic monitor/master,
dictionary statistics/buffer-load tasks; FTS optimization when started. The
resident guest creates SQL slot workers lazily; advertised 16 session slots do
not mean 16 workers were created before ready. Rust/runtime OS workers are a
separate owner. The ready capture happens after one public SQL connection has
already opened/closed, so it can include that retained slot worker.

Mapping/thread capture runs once per Start and Fork ×1/4/8 case, after all DBs
reach first SQL, the hold and process sampler. It does not enter first-SQL
latency, but prolongs those DB lifetimes and contributes to whole-lifecycle
runner CPU/wall and retained runner memory. Diagnostic duration/self CPU are
separate raw fields. Unsupported/permission-denied tooling is recorded, not
silently replaced by estimates.

## Measurement matrix and validation confounder

The manual `guest-build-boundary.yml` initialization measurement uses one exact
Linux-built WASM and separately hashed macOS 15 arm64 / Ubuntu 24.04 x86_64 AOT
artifacts. It retains source commit, prepared source/toolchain/AOT provenance,
20 measured trials, two warmups, raw samples, p50/p95 and existing process costs.
Hosted machines differ: compare within-platform scaling, not absolute platform
latencies as if the hardware were equivalent.

1. Diagnostics-off control, 1,000 rows, ×1/4/8.
2. Initialization + mapping diagnostics, 1,000 rows, ×1/4/8.
3. Same diagnostics, 100,000 rows, ×1/4/8.
4. Diagnostics-off within-call validation-reuse probe, 1,000 rows, ×1/4/8.

Both fixtures retain the same schema and 32-character payload per row. This
tests row/data-size sensitivity, not many-table metadata sensitivity. Their
final first SQL is `COUNT(*)`, so larger-fixture first-query cost must be kept
separate from initialization. Diagnostic snapshot samples retain total/per-file
data bytes from the already-validated inventory, read outside the Snapshot
timer. This adds no data rehash. File bytes/mappings remain distinct metrics.

The validation probe edits only a disposable source copy, with a private
read-only bundle verified unchanged afterward. It carries the manifest-verified
AOT digest into sidecar verification, then that verified build identity into
host startup **within the same call**. Initial artifact/runtime/sidecar hashes
and snapshot inventory checks remain. Two redundant AOT digests are skipped;
there is no process-wide/path cache and no production change. The raw report
records original commit, patched-source hashes and private native-file hashes.
The comparison estimates the redundant-read contribution, not the benefit of
caching snapshots or avoiding validation altogether.

## Results still required

CI emits `initialization-<platform>-<commit>` with raw JSON, measured stage/file
tables and AOT/native identity. Retrieve those artifacts after CI completes to
fill in: dominant ×1 sub-stages, ×4/8 growth, CPU/I/O correlation, ready mapping
and live thread observations, fixture sensitivity, control perturbation and
validation-reuse effect. None is established by source inspection alone.

## Implications for the next probes

**Hypotheses only:** dominant allocation/zeroing would motivate a narrow cold
initialization or initialized-state probe; dominant recovery/open/file work
would motivate storage-sharing tests; Rust anonymous/VFS residency beyond
linear memory would motivate runtime/filesystem memory attribution. Large
initialization wall growth without comparable process CPU growth would justify
sampling waits/contention more directly. A material validation-reuse delta
would justify investigating immutable-identity plumbing separately.

The next probe must be chosen from the measured CI result, including its
instrumentation perturbation. This document does not choose CoW, continuation,
runtime sharing or a production optimization.
