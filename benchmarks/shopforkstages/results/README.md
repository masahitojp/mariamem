# Current shop Fork startup: P4/P8 stage refresh

**MariaDB server initialization still dominates observed Fork time, but the
largest named individual initialization region is now common initialization,
not InnoDB alone.** In P4 diagnostics: common7.652ms, InnoDB6.060ms,
Aria2.673ms. In P8: common10.233ms, InnoDB5.965ms, Aria2.943ms (pooled child
medians). Server initialization accounts for80.07%/74.71% of summed observed
Fork elapsed at P4/P8. Filesystem setup and module creation are much smaller.

Recommendation: if choosing another Fork optimization investigation, narrow the
remaining common-initialization region before changing buffer-pool capacity or
assuming engine startup is all recoverable I/O. InnoDB remains material, but its
pool creation is only1.54/1.63ms and broad open/recovery2.29/2.33ms here.
This is an attribution result, not approval to cache live engine state or bypass
recovery/constraints. No prototype or parameter change is made.

The strongest limitation is observer disturbance, especially at P8: paired
process-Fork-p50 increases1.3–13.0ms (median9.141ms), while P4 increases1.4–3.4ms
(median1.643ms). The detailed values locate work in the observed execution; they
are not precise partitions of an unobserved32ms Fork. There are only3process
pairs per parallelism, on one shared Mac. No fixed overhead subtraction is valid.

[Standalone chart](report.html) (download/open locally).

## Ordinary control versus observed Fork

All primary children retained:63 per cell. Quantiles are pooled within a cell.
Control uses the same overlay binary with observation disabled; ordinary product
comparisons retain their own earlier sources and numbers.

| Parallel | Observer | Fork p50 ms | p95 ms | Maximum ms | >100ms children | Suite median ms |
|---|---|---:|---:|---:|---:|---:|
|4|off|26.398|35.174|37.442|0|667.862|
|4|on|29.375|39.514|46.742|0|681.672|
|8|off|32.102|53.599|56.589|0|828.514|
|8|on|42.392|67.106|110.517|2|527.430|

P4/P8 off Fork medians26.398/32.102ms are near the earlier pristine shop
comparison26.243/34.715ms, but are separate cohorts. No performance treatment was
applied. Sample loading still has400ms-class tails, so the larger P8 off suite
median is not evidence of a product regression or a new P4 scaling ceiling.

## Host partition

Each child partitions exactly into the five disjoint rows below. Medians do not
add; means do because they use the same63 children. Execute-to-ready contains
all guest initialization and scheduling/ready transport. The observer's diagnostic
read is nested in ready-to-startup-end.

| Disjoint elapsed region | P4 p50 ms | P4 mean ms | P8 p50 ms | P8 mean ms |
|---|---:|---:|---:|---:|
|filesystem_prepared|0.114|0.186|0.124|0.193|
|memory_construct|0.577|0.782|1.117|1.815|
|execute_to_ready|26.923|27.324|37.723|39.633|
|ready_to_startup_end|0.280|0.379|0.271|0.939|
|api_host_other|1.178|1.444|1.176|2.311|

Module construction includes the existing image.Acquire path and thread-lifetime
setup. It does not clone an initialized MariaDB engine. Filesystem setup includes
prepared-handle attachment, not eagerly copying every database page. Host-other
includes outside-startup API work and inner timing serialization/file output;
it is not exclusively product overhead.

## Inside server initialization

These rows are nested; do not sum all of them. Common and each engine are named
regions, not exclusive CPU categories. Values are elapsed time in diagnostics.

| Region | P4 p50 ms | P8 p50 ms | P8 p95 ms |
|---|---:|---:|---:|
|server_init|23.400|30.907|54.304|
|common|7.652|10.233|25.253|
|components_before_plugins|1.501|1.603|7.599|
|myisam_key_cache|1.431|1.535|7.502|
|plugins|11.803|15.066|25.085|
|plugin.InnoDB|6.060|5.965|13.299|
|buffer_pool|1.535|1.632|3.046|
|innodb_open_recovery|2.290|2.329|6.236|
|innodb_background|1.330|0.930|3.528|
|plugin.Aria|2.673|2.943|9.782|
|plugin.caching_sha2_password|0.752|0.719|7.528|
|components_after_plugins|1.069|1.056|6.431|
|routine_schema|1.100|1.120|4.589|

Server init >100ms:0/63 at both P4 and P8. Maxima39.351/92.031ms. Public observed
Fork >100ms occurs twice at P8, retained; no single server-init record exceeds
100ms. No tail filtering is used to obtain the table.

Common per-process medians are6.948/7.906/7.777ms at P4 and
14.011/9.038/10.610ms at P8. InnoDB per-process medians are
6.108/5.964/6.116ms and6.094/7.318/5.808ms respectively. The common-init finding
is present in all three primary runs, not just an isolated100ms outlier.

On additive means P4→P8, common grows8.133→12.360ms, InnoDB6.444→7.680ms,
Aria3.638→4.396ms, and other regions also grow. InnoDB's similar p50 does not mean
its whole distribution is unchanged: p95 grows9.038→13.299ms. These are observed
elongations under different concurrency, not evidence of CPU or a particular
lock cause. The stronger P8 observer effect limits causal interpretation.

The earlier9.52ms InnoDB/7.33ms common/6.49ms open-recovery figures were a prior
P1 source/fixture cohort. They are historical context, not a matched before/after
experiment for CRC, lexer or static-image adoption. Current common7–10ms is not
all the old lexer map work: prepared lexer/UCA changes are already present.

## Complete run list and remaining tails

| Run | Suite ms | Fork p50 ms | Sample maximum ms |
|---|---:|---:|---:|
|p4-off-r-1|692.920|24.343|80.231|
|p4-on-r-1|780.179|33.696|110.155|
|p8-off-r-1|695.471|28.745|444.178|
|p8-on-r-1|732.718|43.469|438.781|
|p8-on-r0|527.430|44.144|104.901|
|p8-off-r0|828.514|31.101|436.357|
|p4-on-r0|630.654|28.900|77.886|
|p4-off-r0|667.862|25.458|86.067|
|p4-off-r1|651.246|26.323|69.232|
|p4-on-r1|686.453|27.741|88.653|
|p8-off-r1|833.151|32.102|460.191|
|p8-on-r1|494.467|41.243|111.148|
|p8-on-r2|780.762|40.060|442.911|
|p8-off-r2|583.875|38.755|136.071|
|p4-on-r2|681.672|31.572|75.329|
|p4-off-r2|723.419|29.929|67.363|

P8 off r0 has sample spans428.955/436.357ms; off r1 has437.266/460.191ms;
on r2 has442.911ms. These explain why a diagnostic run can have longer Forks
but a shorter whole suite. They are retained, not assigned to an UNDO owner or
claimed fixed. This task stops at the fixed16processes without pursuing those
separate sample tails.

## Source, workload and boundaries

Product source_commit `b1218737ffa0bc1d08e9b1285b9bcf6ccf8adc50` matches the
preceding shop P4/P8 comparisons. Measured harness source_commit and binary hash
are in inputs.json. scripts/git_identity.py validates commit objects and clean
source before compilation. Git changes are benchmark-only; a fail-closed Go
build overlay observes three handwritten files (runtime_instance.go, linked.go,
timing.go) and adds one timing-package test. Before/after hashes are recorded.
No generated instruction body, guest source, SQL, engine setting, release input,
public API or image-sharing algorithm is changed. The normal constructor still
uses the adopted process-static image cache. There is no new guest compilation.

Apple M1/16GiB/macOS27.2, Go1.27.3/CGO0, runtime GOMAXPROCS8/GOGC100,
Go Pipe. Shared desktop, not an isolated machine or Ubuntu qualification.
Same shop70 cases:50 readers sharing one child and20 private writers;21 Forks.
P4/P8 use cap5/cap9 and shared-reader connection pool4/8. Master fixture has
20 categories,500 products,1,000 users. Each child loads40 orders/100 lines;
no sample phase observer or status queries from the previous diagnostic are used.
The inherited default16MiB/max buffer pool is asserted by the original fixture.

Four warmups (P4/P8 × observer off/on), then three alternating pairs per
parallelism, with P order also rotated.16 total processes,12 primary. There are
63 primary children per cell, not63 independent process repetitions. All16
processes pass70 cases (1,120 total;840 primary) and zero final active mappings/
empty owned scratch. All tails are retained; no retries or extra samples.
Compilation/download is outside measurement. Product runtime is unchanged.

Off and on use the same overlay binary. Off disables timing environment/recording
but retains wrapper dispatch and disabled Mark checks, so it is a diagnostic
control rather than an independently built pristine-product performance baseline.
On enables existing startup and detailed initialization hooks. Those hooks also
collect allocation/I/O counters; this report uses their wall-clock boundaries,
not exclusive CPU attribution. No new UNDO owner tracing or claim about lock
ownership is made. The older large observer is not silently relabeled as current.

Each child carries its own context callback. Nested fork/api_startup/startup traces
are bound to the test lane; guest diagnostics are read from that exact child's
MemFS after ready. The temporary reader closure is cleared before publishing the
trace, so stored records do not retain guest filesystem ownership. Concurrent
8-context isolation and invalid-reader tests pass. No new SQL/protocol messages
are needed for observation. Invalid/missing/truncated stage records stop the run.
All required guest events exist; dropped initialization records are zero.

The outer fixture Fork span includes the public call and timing overhead. Host
stage timestamps share one clock within the nested startup trace. Filesystem,
module construction, execute-to-ready and ready-to-startup-end are disjoint;
API/host other is their residual against the outer Fork. They sum per child.
Diagnostic MemFS read is nested inside ready-to-startup-end, not an extra additive
phase. Public Fork also includes inner trace serialization/file output, recorded
in the residual. Root Start is retained separately and includes first static-image
construction; the child stage table does not amortize or hide that cost in a
claim about complete suites. Whole suite clocks include root setup and cleanup.

Guest timestamps use an independent origin. Only durations are compared with the
containing host envelope. Server init is nested in execute-to-ready; common,
components-before-plugins, all plugins, components-after-plugins and server-other
partition server init. MyISAM is nested before plugins; InnoDB/Aria/auth are inside
all plugins; buffer-pool/open-recovery are inside InnoDB. Never add parent and
child rows or add independent medians to reconstruct total time. Means of the
same63-child population are additive where rows are explicitly disjoint.

Common spans embedded_begin→embedded_options_complete: shared server/option/
charset initialization before component initialization. It is not all immutable,
not all lexer-map generation and not guaranteed removable work. InnoDB's broad
open/recovery marker interval covers checkpoint/system/UNDO/dictionary/transaction
initialization and integrity work on the existing-data branch, not solely redo
replay or physical disk I/O. Buffer-pool allocation is only one nested interval.
Current timings cannot be subtracted from earlier source/toolchain/fixture cohorts
to claim a specific CRC/lexer/image optimization gain. Per-stage guest CPU remains
unavailable; observed elongation can include scheduling and waiting.

## Reproduction, checks and cleanup

Read-only replay: `python3 benchmarks/shopforkstages/results/analyze.py --check`.
One deterministic gzip preserves all original observation records losslessly,
including warmups, root records, full guest events and counters. Summary omits
duplicate per-child derived tables; they are recomputed from observations.
Original process log/stage/trace SHA256 values and uncompressed observation hash
are retained. No live paths, binaries or removed cache are required for replay.
Analysis controls reject a missing process, missing stage and mapping leak.

For a new authorized measurement, prepare a clean workspace at the measured
harness source in inputs.json with8GiB owned budget/12GiB free reserve; execute
build.py then run.py under the1500-second experiment-workspace guard. Per-process
limit150seconds. The build first runs timing/observer tests, then produces one
on/off binary. run.py executes the fixed16 processes and stops at first failure.
Reports/analysis are later commits, not relabeled as the measured source.

Evidence is on an experiment branch, not main adoption or release approval.
After source/results are pushed, delete owned copies, binaries, caches and the
clean worktree. Recheck retained checksums/replay and absence of cleanup debt.

Measured harness source_commit: `0eb5f3e8d82be3526d78c24a2a919115056c8f2c`.
