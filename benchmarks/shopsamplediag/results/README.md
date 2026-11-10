# Shop sample loading: phase timing and settings-pressure observation

**No observed need to increase log/table/buffer capacity in this small shop
fixture.** Across21 primary diagnostic children, log-buffer waits, buffer free-page
waits, table-cache overflows and row-lock waits are all zero. Buffer free pages
remain660–965 before and790–956 after loading. Table handles go0→5 with exactly
5 misses and582 hits per child, consistent with initial opening rather than a
32-entry cache repeatedly overflowing. Redo bytes written rise35,000–35,868 per
child against the2MiB log buffer, with no observed log wait.

The dominant client-observed intervals are **100 detail INSERTs (52.19% of summed
body time)** and **100 stock UPDATEs (26.27%)**. Detail INSERT includes the total
recalculation trigger and resulting orders UPDATE/audit condition. This identifies
an operation group, not its internal cost or proof that all time is CPU.

Recommendation: do not start a broad capacity/COMMIT-setting sweep on this
fixture. Keep defaults. If another bounded investigation is chosen, distinguish
trigger/index/engine work and per-call transport/scheduling inside detail INSERT
and stock UPDATE. The concrete remaining unknown is where time within those
calls goes; this run does not isolate a trigger optimization or justify removing
constraints. It also does not remeasure pgmem, so it cannot attribute the exact
cross-product sample-time gap.

## Timing

Diagnostic primary:21 children. Durations are per-child totals, then medians.
Percentages use all-child sums; medians do not sum to the median body.

| Operation | Calls per child | Median total ms | Share of summed body |
|---|---:|---:|---:|
|Begin|1|0.044083|0.20%|
|Prepare orders|1|0.685791|2.15%|
|Prepare items|1|1.198916|2.10%|
|Prepare stock|1|1.097917|2.00%|
|Order INSERT + audit|40|9.995170|14.66%|
|Item INSERT + total trigger|100|36.820043|52.19%|
|Stock UPDATE|100|17.715166|26.27%|
|COMMIT|1|0.195666|0.34%|
|Deferred statement Close|3|0.000251|0.00%|

Body median68.426ms (max84.980ms), excluding status/settings probes. Combined
three-Prepare median3.489ms. Probe-before median7.935ms; probe-after1.233ms.
Outer sample median81.080ms includes probes. Per-call detail INSERT median0.245ms,
p95 0.773ms, max6.093ms; stock UPDATE median0.122ms, p95 0.398ms, max1.908ms.
This is not a redefinition of the uninstrumented P8 baseline's86.462ms median.

COMMIT median0.196ms, max0.464ms; its summed share is0.335%. Even completely
removing that interval cannot explain most of the observed sample cost in this
run. Changing flush policy may affect background work as well; that is untested,
so this is a low-priority judgment rather than a claim of zero possible effect.

## All four executions, including warmups

| Mode | Suite ms | Outer sample median ms | Outer sample max ms |
|---|---:|---:|---:|
|control-warmup|828.349|72.743|438.464|
|diagnostic-warmup|527.573|90.363|125.891|
|control|507.664|74.740|102.570|
|diagnostic|485.173|81.080|97.524|

All four runs pass70 cases and zero-mapping/scratch cleanup. Diagnostic warmup
and primary each contain21 valid child records with exact operation counts.
The control warmup has a438.464ms sample tail, retained with no retries. Neither
diagnostic run captured such a tail, so this does not explain or close it.
Warmup's shares (detail50.61%, stock27.14%, COMMIT0.46%) are directionally similar,
but a warmup is not a second independent primary repeat.

Diagnostic suite485ms versus control508ms does **not** establish a speedup from
observing. Probe queries open/warm the connection and change scheduling. Outer
sample median actually rises74.740→81.080ms. Use the phases to choose a follow-up,
not the one-pair difference as product performance evidence.

## Counter deltas and settings

For each primary diagnostic child, before/after values are retained. Selected
cumulative-counter deltas:

| Counter | Median delta | Min–max |
|---|---:|---:|
|innodb_buffer_pool_read_requests|2539|2539–2757|
|innodb_buffer_pool_reads|12|0–210|
|innodb_buffer_pool_wait_free|0|0–0|
|innodb_log_waits|0|0–0|
|innodb_os_log_written|35012|35000–35868|
|opened_tables|5|5–5|
|table_open_cache_hits|582|582–582|
|table_open_cache_misses|5|5–5|
|table_open_cache_overflows|0|0–0|
|innodb_row_lock_waits|0|0–0|
|innodb_row_lock_time|0|0–0|
|innodb_pages_written|0|0–151|

There are page reads (median12, max210), plus background flush/page-gauge changes.
They are not proof of capacity exhaustion, and in this memory-backed filesystem
they are not physical host-disk reads. Free-space observations are endpoint
samples, not a continuous occupancy trace. Wait-free stays zero in both observed
suites. Background work and initially cold pages remain possible contributors.

All requested settings were returned. `Innodb_rows_inserted` and
`Innodb_rows_updated` status names were absent and remain explicitly MISSING,
not silently zero. Actual settings are common across all diagnostic children:

| Setting | Observed value |
|---|---|
|autocommit|ON|
|check_constraint_checks|ON|
|foreign_key_checks|ON|
|innodb_adaptive_hash_index|OFF|
|innodb_buffer_pool_size|16777216|
|innodb_buffer_pool_size_max|16777216|
|innodb_doublewrite|ON|
|innodb_flush_log_at_trx_commit|1|
|innodb_log_buffer_size|2097152|
|innodb_purge_threads|1|
|innodb_read_io_threads|1|
|innodb_write_io_threads|2|
|query_cache_size|1048576|
|query_cache_type|OFF|
|table_definition_cache|400|
|table_open_cache|32|
|unique_checks|ON|

The runtime reports **write_io_threads=2**, even though the pinned recipe requests1;
we record the effective value rather than assuming argv equals runtime state.
The cause of this difference is not investigated here. Read threads remain1.
Query cache type is OFF (allocated size1MiB); disabling a cache that is already
not serving queries is not established as a sample-speed win.

Setting-specific disposition for this fixture:

- Log buffer2→8MiB: no waits, small observed log volume; low priority.
- Table cache32→128: five initial opens, no overflow; low priority.
- Buffer pool16→32MiB: no free-page wait and substantial free pages at both
  endpoints; no capacity-pressure evidence. Cold-page/background behavior is
  not ruled out, but increasing capacity is not currently supported by it.
- Flush-at-commit1→0/2: COMMIT less than0.5ms in every primary child; low priority
  for typical sample time, without claiming anything about rare waits.

## Scope and interpretation

The Human authorized an observation-only check of sample loading to decide
whether buffer/table/log settings deserve a bounded experiment. This does not
authorize changing settings, stripping triggers/constraints, adopting a product
change or expanding to a parameter sweep.

Product source_commit is `b1218737ffa0bc1d08e9b1285b9bcf6ccf8adc50`, matching
the preceding P8 shop comparison at harness8157db34/results c0b69604. This
experiment adds only benchmark code. No guest/runtime/default/API changes.
The exact measured harness commit, generated-input identities, module replacement,
Go version and binary SHA256 are in inputs.json. scripts/git_identity.py checks
commit identities and a clean tree before compiling. buildvcs is explicitly off;
the binary is bound by recorded hashes instead of misleading VCS stamping.

Apple M1/16GiB/macOS27.2, Go1.27.3/CGO0/Pipe, GOMAXPROCS8/GOGC100.
Shared desktop host, not isolated. One process at a time. Same70 cases (50 read,
20 write),21 Forks, cap9,20 categories/500 products/1,000 users in the Snapshot;
each child loads40 orders/100 lines with100 stock UPDATEs in one transaction.
The original control LoadSample remains byte-identical apart from its name.
Diagnostic SQL and business assertions are unchanged. Only current mariamem is
run; neither pgmem nor v0.6.2 is remeasured.

Fixed run order: control warmup, diagnostic warmup, control primary, diagnostic
primary. One primary suite per mode, not five independent repeats. Each diagnostic
suite yields21 child records. No retries or tail exclusions. The four modes use
the same binary. Both modes assert70 cases and zero final active mappings; exact
operation counts in each observed child are also checked. Runtime settings are
read back, with missing variables preserved rather than assumed zero.

The observer issues SHOW VARIABLES and filtered SHOW GLOBAL STATUS before
LoadSample and status again after commit/deferred statement disposal. Those calls
can open/warm the connection and affect caches/scheduling. Probe time is separate
from body time, while the existing outer sample span includes probes. Control vs
diagnostic wall is a perturbation check, not a performance treatment comparison.
Begin in the diagnostic body excludes the connection opened by the preceding
probe; this is unlike the original control's lazy-connect boundary. The status
queries also have work of their own, so deltas are observations across a window,
not exact exclusive costs of the240 business SQL calls.

Global counters are local to each independent child DB, not combined across the
21 children. Background work within that DB may contribute. Cumulative-counter
deltas and page/table gauges are retained separately by name; gauge decreases are
valid. InnoDB page reads are not proof of physical host disk I/O on this memory
filesystem. Ordinary first opens/read misses do not establish cache pressure.
Zero waits do not exclude uninstrumented locks, CPU cost, table work or waits
outside the observation window. No owner tracing or internal trigger timing was
added. Long INSERTs include all trigger/index/constraint/engine/driver activity;
this observation cannot allocate them to any one of those mechanisms.

Each SQL is timed around the synchronous client call; order INSERT includes
RETURNING Scan. Prepare operations are separate. Per-child sums of40/100/100 calls
are useful for composition. Stage medians across children do not add to median
body time, and overlapping children do not add to total suite wall. Fractions use
summed operation time divided by summed body time across children, with other Go
work as a residual. Background CPU and RSS are not individually measured.

## Reproduction and retention

Offline check: `python3 benchmarks/shopsamplediag/results/analyze.py --check`.
Compact observations include all four traces and both diagnostic sets. Analysis
requires no temp checkout, binary, network or cache. Mutations check missing runs,
operation-count errors and an unreaped mapping; actual checksums are verified too.

For a new authorized run, prepare a workspace at the measured harness commit
recorded in inputs.json with8GiB budget/12GiB free reserve. Run build.py then run.py
under experiment_workspace.py run --timeout1200. Dependencies and Go1.27.3 are
required. Measurement stops after four processes or on first unexpected failure.
Analysis/report commits are later than the measured harness and are not relabeled
as runtime measurements. Raw logs are hashed, compact results pushed, disposable
binaries/caches/copied source removed, and offline replay repeated after cleanup.

Measured harness source_commit: `1bbff128dbd02e2aa4ae6091aa86b0d91d365824`.
