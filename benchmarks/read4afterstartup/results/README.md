# Read1/read4 after normal startup concurrency adoption

**Keep read1 for now. Read4 did not meet the predeclared benefit threshold in this
bounded comparison.** After PR141, the temporary global startup restriction is
already removed. Raising the read I/O task group from1 to4 gave a5.6% longer
whole-suite median and won only2/5 pairs. This does not establish that read4 is
always harmful: five one-host pairs are descriptive, and long PREPARE waits
occurred in three read4 processes. The waiting mechanism was not captured.

## Identity and scope

- Adopted main/base_commit: `32e3329c8f12ade2062f7acb5c8c8794457b5709` (PR141),
  tree-identical to approved head e88f4e35977cd711f3ef13deba69b0d6d9d4f947.
- Measured source_commit: `1adf07fd5a9f48275c52541af7ffa3031ec3563d`.
  Runtime/guest/release source equals that main; a guarded Go overlay adds only
  an argv selector at the existing guest entry handoff. Read1 validates all25
  strings without mutation; read4 changes only the final read-thread digit.
  Both arms use the **same binary**; its SHA256 and overlay hashes are in inputs.
- Apple M1,16GiB, observed macOS27.2 arm64, Go1.27.3; GOMAXPROCS8/GOGC100.
  This is a local Mac experiment, not the supported-platform CI matrix or Ubuntu
  evidence. Native product correctness is covered separately by the PR141 receipt.
- Existing shop workload:50 reads share one child;20 writes each have an isolated
  child.21 Fork children, cap9, Go Pipe, test parallelism8.16MiB buffer pool and
  the adopted normal global concurrency remain fixed. No prefetch or other
  setting is changed. All root/child connections assert the actual read setting.
- One warmup per arm, then five alternating pairs (1→4,4→1,1→4,4→1,1→4).
  All12 suites/840 cases pass; mapping count returns to0, Snapshot/DB retirement
  succeeds. Warmups are preserved but excluded from results. No tail is excluded.
- Caller timestamps retain sample PREPARE/order INSERT/item INSERT/stock UPDATE/
  COMMIT costs. No intrusive runtime sampler/stack collector is enabled. Queue
  attribution and ownership of the observed long waits remain **unknown**.

## Measured result

| Metric | Read1 | Read4 |
| --- | ---: | ---: |
| Whole-suite wall median |538.775ms|569.054ms|
| Wall min–max |510.996–561.724ms|533.159–978.325ms|
| Wall MAD |11.695ms|35.895ms|
| Fork per-child p50 / p95 (105 children/arm) |38.539 /54.014ms|37.208 /55.161ms|
| Fork >=100ms |0/105|0/105|
| PREPARE p50 / p95 (315 calls/arm) |0.924 /5.185ms|1.061 /7.646ms|
| PREPARE >=100ms |0/315|3/315|
| Per-process cleanup sum median |158.495ms|135.680ms|
| Process CPU median |2783.364ms|2792.982ms|
| Process peak RSS median |773.328MiB|770.141MiB|

Whole wall includes root boot, migration/seed, Snapshot, all70 cases and final
cleanup. Compilation and evidence serialization are excluded. CPU includes all
process threads for that workload; peak RSS is Darwin process high-water RSS,
not incremental per-child memory. Cleanup includes pool close, WaitDisconnected,
child retirement and final baseline close. Concurrent per-child sums overlap;
do not add them to reconstruct whole wall. Percentile is nearest-rank p95;
median is the ordinary median. No confidence interval is claimed.

| Pair / execution order | Read1 wall | Read4 wall | Read4 minus Read1 |
| --- | ---: | ---: | ---: |
|0 /1→4|561.724ms|569.054ms|+7.330ms|
|1 /4→1|535.303ms|652.248ms|+116.945ms|
|2 /1→4|550.470ms|546.633ms|−3.837ms|
|3 /4→1|510.996ms|978.325ms|+467.329ms|
|4 /1→4|538.775ms|533.159ms|−5.616ms|

Read4's long PREPAREs were386.140ms (`TestShipOrder/twice`, pair0),397.319ms
(`TestApplyDiscount/books_10`, pair1) and404.775ms (`TestDeleteUser/user_15`, pair3).
The first two processes were shorter than800ms: a400ms call does not invariably
add400ms to whole wall because other cases run concurrently and its placement
within the schedule matters. The records locate calls, not their waiting owner;
do not call these proven recurrences of the old global-cap or #68 UNDO mechanism.

## Judgment and next action

The fixed screen required >=5% lower median and >=4/5 paired wins, with all
correctness/cleanup checks passing. Only the correctness/cleanup condition is
met. CPU median differs+0.35% and peak-RSS median−0.41%; these small descriptive
changes do not establish resource equivalence. A paired RSS increase68.656MiB
also remains visible in summary.json. The original read4 improvement under the
old global cap is not transferable to this new base.

Do not adopt read4 or start another automatic sweep. Keep the adopted startup
mitigation and current read1/16MiB defaults. If a concrete workload later needs
read parallelism, reopen that separate bounded question. This cohort does not
justify claiming that read4 causes the tails, nor that startup-cap adoption
eliminated them. #140 remains a residual-wait issue; #88/8MiB is independent.

## Reproduce and retained evidence

At the measured source, use an experiment-workspace with at least8GiB free and
a6GiB budget, then run `python3 benchmarks/read4afterstartup/run.py <workspace>`.
The runner checks source identity and runtime equality before building. It runs
selector controls, one binary build, two warmups and ten natural suites. Build
wall was113.82s on this host; a suite is limited to120s, with no auto retry.
This is an experimental argv overlay, not a new public setting or canonical
C/WASM artifact. Product adoption and release require separate decisions.

`observations.json` retains all run identities and settings, per-child Fork/
cleanup/sample durations, every PREPARE duration, SQL-phase totals and all>=50ms
operations with case/time identity. `reduction.json` records original/published
hashes and omitted fields. `inputs.json` retains source, environment, binary and
intervention identities; `summary.json` is derived, not a second data source.
`python3 benchmarks/read4afterstartup/results/analyze.py --check` reproduces it
read-only without a build tree. Routine short SQL call arrays, console logs,
compiled binaries and caches are not retained in Git. SHA256SUMS covers the
published files. No historical measurement is relabelled.
