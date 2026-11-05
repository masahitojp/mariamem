# Startup buffer-pool load OFF: one-option bounded contrast

**Conclusion:** OFF removed the observed long COUNT spans in this finite cohort and reduced batch wall in all five pairs at both P4/P8, but one366ms UPDATE remained and P8 Fork p50 worsened beyond the predeclared5% guard. Treat this as a throughput/latency tradeoff, not a complete Issue68 fix or automatic adoption candidate. Stop the fixed experiment without extra repeats.

[Graph](report.html) · [Process CSV](processes.csv) · [All distributions and fixed gates](summary.json) · [Plan](plan.json)

## Exactly what changed

One extra server-init argument in each arm: `--innodb-buffer-pool-load-at-startup=1` versus `=0`. All25 original lite4mariadb/mariamem arguments retained. Six settings from the previous bounded-default experiment are at **current** values in both arms: read1/write2(effective)/purge1, max_connections10, table_open_cache32, thread_cache_size0. Buffer pool size/max16MiB, log buffer2MiB, native AIO OFF, dump-at-shutdown ON; auth/path/wire contracts unchanged.

Separate SQL preflights verify root+8children per arm: fresh roots both report load OFF and every other observed variable is equal; Fork children report load ON versus OFF, with exactly that one observed variable difference. Root preparation, application schema/seed and Snapshot protocol are unchanged. OFF does not delete tables, seed, snapshot files or the buffer-pool dump; it disables automatic cache loading on child startup. This does not imply no page I/O or no other queues.

## Fixed ordinary timing

One Apple M1/16GiB/macOS27.2; Go1.27.3, CGO0, GOMAXPROCS8, GOGC100. 1,000 rows;48 independent children per process; Pipe; cap=P;5 fresh-process pairs/P4/P8 with alternating profile and rotated P order. Separate warmup/cell. No config queries, trace, detailed queue observer or CPU profiler in primary runs. Per-query host timers are identical in both arms; do not merge this new cohort with older combined-SQL-only results.

| P | Profile | COUNT>100ms /240 | COUNT>500ms /240 | COUNT p50 /p95 /max ms |
|---|---|---:|---:|---|
| 4 | current | 2 | 2 | 3.23 / 10.18 / 798.43 |
| 4 | load-off | 0 | 0 | 1.97 / 5.86 / 8.08 |
| 8 | current | 6 | 3 | 4.13 / 17.56 / 835.29 |
| 8 | load-off | 0 | 0 | 2.70 / 11.15 / 14.26 |

These are client query spans, not internal task-queue delays. Zero COUNT tails among240 OFF children/P is not proof of permanent elimination, a population frequency, native parity or satisfaction of the older Issue68 internal child-max queue-p99 gate. That earlier accounting-patch result remains under its original source/distribution.

| P | Profile | Batch median ms | Fork p50 median ms | Batch CPU median ms | Sampled peak RSS median MiB |
|---|---|---:|---:|---:|---:|
| 4 | current | 601.1 | 31.21 | 2799.3 | 364.1 |
| 4 | load-off | 546.6 | 31.22 | 2649.1 | 363.1 |
| 8 | current | 872.5 | 47.86 | 3167.8 | 661.0 |
| 8 | load-off | 483.0 | 52.10 | 3047.8 | 664.5 |

Independent cell medians above are descriptive. **Median paired changes** below are the fixed comparison; positive savings means OFF lower/faster.

| P | Batch saved | CPU saved | Fork saved | RSS added |
|---|---:|---:|---:|---:|
| 4 | 9.07% | 3.92% | -0.005ms (-0.02%) | -0.98MiB |
| 8 | 33.26% | 5.27% | -8.169ms (-18.33%) | 0.61MiB |

Both P have batch-wall wins in5/5 pairs. P8 paired batch improvement33.26% and CPU reduction5.27% coexist with Fork median+8.17ms/+18.33%. This exceeds the predeclared5% Fork guard, so the full gate is **not passed** despite improved COUNT distributions and whole-batch wall. The choice to prioritize whole-suite throughput over per-Fork latency would be a new explicit Human decision; this report does not silently relax that guard.

## Remaining slow case

OFF/P8 round3 child41: COUNT1.235ms, UPDATE366.443ms, verification SELECT0.896ms; combined SQL368.575ms, Fork60.613ms. It is retained. Current/P8 has six long COUNTs, three>500ms; current/P4 has two long COUNTs, both>500ms. No mechanism trace was collected here, so do not assume the remaining UPDATE has the same queue cause or that a wait moved from COUNT to UPDATE.

## Post-hoc public-interval overlap (explanatory, not a gate)

Existing samples permit interval-only reduction with no extra DB runs. For each child, sum intersections of its public Fork interval with all public Fork intervals and divide by its duration; then take child median/process and process median across5. P8: current6.34 overlapping Forks→OFF7.18. First-eight Fork p50 medians55.36→52.51ms; later40 children46.16→52.07ms. P4 overlaps3.64→3.61.

This is consistent with removing long waits allowing more workers to keep starting children concurrently, making per-Fork elapsed latency larger while batch finishes sooner. It does **not prove** the source of CPU/memory/scheduler contention, and the first-eight stratification was not preregistered. No server-init/phase CPU/fault attribution is inferred. Full per-process overlap rows and readonly overlap.py are retained.

## Correctness and provenance

All positive SQL/pristine COUNT/SUM/independent UPDATE/verification and cleanup oracles pass. Separate wrong-seed controls in both arms fail as intended and clean up.20 primary processes,4 warmups,2 positive8-child preflights and2 negative1-child controls:28 fresh processes, no retries/exclusions. Active-child interval census matches cap. Selector unit tests verify all original arguments/order, added1/0 option/null termination,64-byte guest-stack scratch containment and restoration of stack/argv slots, unchanged unrelated data, and malformed mode/stack/preimage/terminator rejection before mutation.

Product source_commit1862f4a89397bddfa1820d835106d3437a438cf7; measured harness source_commit5472e3df7fbee38973f030e61c0e9dd293b735bd. Clean commit identity checked using git_identity before build; only benchmark tooling differs from product. One exact binary for both arms; experimental selector read once at process initialization. Origin guest SHA2566d7442204d39bc28eb4b34401874b84b4d3f517c2bb698ba7f3a465027c36cbe identifies the unmodified input guest. This translated-Go argv prototype is **UNQUALIFIED**; no new WASM has that origin hash and no canonical guest rebuild is claimed.

The pinned Fn244 frame has128bytes, argv occupies104bytes including its original terminator, and timing locals begin112. The prototype uses argv offsets100/104 for the added pointer/new terminator, reserves64bytes below the current stack pointer for the bool option during Fn5739, then restores the two slots and stack. Exact before/after file hashes and unit fixtures bind this experimental layout; it is not a production API or general argv mechanism.

Batch includes all child SQL, connection retirement/WaitDisconnected and DB Close, excludes root preparation/capture/final Snapshot close. Process CPU spans all threads/operations; no exclusive Fork CPU claim. RSS is20ms sampled batch process peak, not retained-child RSS. Ordinary Start/Fork still creates a listener although SQL uses Pipe. Disk6GiB/free reserve12GiB and RSS3GiB safety guard did not trip.1host/small fixture only; Ubuntu/large working set/full qualification are NOT RUN.

## Recommendation and completion

The COUNT/background-load relationship is now supported by this source-bound contrast, and whole-suite time improved. Complete-resolution and unconditional default-adoption claims are unsupported because of the UPDATE residual and failed P8 Fork guard. Preserve the result for a narrowly scoped Human tradeoff review, or maintain current settings; do not extend this run to chase zero failures or silently reopen unrelated parameters. Candidate canonical guest changes/platform acceptance, main integration and release remain separate.

receipts.zip retains every process/memory observation, effective variables, selector/build logs, plan/input/overlay hashes, collector/build/reducer and posthoc interval script. Extract to an empty directory, run `python3 analyze.py --check` and `python3 overlap.py --check` for readonly matrix/distribution/CSV/gate/overlap replay without a temp tree. Reproduce new observations from clean measured harness5472e3df and archived build.py/run.py in their recorded disposable layout. SHA256SUMS.json covers published files. No canonical product/API/guest default change, CI dispatch, main merge, Qualification or release in this task.
