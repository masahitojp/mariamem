# Matched Fresh/Fork startup attribution

**Conclusion:** in this warm static-page prototype, Fork spends more time in the
InnoDB existing-file/open/recovery interval, not in common initialization.
Fresh API startup is faster, but Fork reaches the same verified1,000-row schema
and seed state sooner in every P1/P4 pair. The fixed investigation is complete.

**Recommendation:** preserve the distinction between API-ready and equal app
state. If investigating the Fresh/Fork startup difference further, select a
bounded subdivision/source study of existing-data InnoDB startup, not another
undifferentiated common-init campaign. Common init is still a cost in both paths;
this result does not rule out an independent immutable-data optimization.
Do not skip recovery/integrity checks. No follow-on prototype is implemented.

The strongest objection is the scope: one small integer dataset, three process
pairs per cell, a warm prototype image, synchronized waves and diagnostics with
measurable observer cost. This does not establish a general production ranking,
exclusive CPU/I/O attribution or a safe shortcut through recovery. No new pgmem,
Ubuntu, memory, guest build, CI, product adoption or release evidence.

## Protocol and identity

Tested source 398133d0a05f00e53c795f318aec7113261b6cac; same binary for every route/observer state, unchanged guest
6d7442204d39bc28eb4b34401874b84b4d3f517c2bb698ba7f3a465027c36cbe.
The binary contains the stage/UNDO observer overlay; off disables it via the
existing environment gates, not a separately compiled production build.
Mac M1/16GiB, Go1.27.3/CGO0, GOMAXPROCS8/GOGC100, Pipe, static-page image enabled.

Both routes first create/seed/capture the same baseline, warming initial image
construction in root setup. Fresh ignores that baseline for child starts and
creates the app table/seed per child; Fork uses its files. Keeping a baseline in
Fresh is an experimental control, not the normal public Fresh lifecycle. Setup
and first image-build costs are recorded separately, not inside child startup.
Fresh concurrency is driver-bounded; it is not subject to the unused Snapshot's
Fork pool. Fork has MaxForks=P. Every wave starts together, all ready before SQL,
and all disposed before the next wave. No application SQL overlaps later child startups.

32 processes /1,354 children /844 waves. Twenty-four primary processes are
Fresh/Fork × observer off/on × P1/P4 ×3 repetitions, plus4 off warmups,2 on pilots
and2 on wrong-seed controls. All30 positive processes and both expected failures
have SQL/cleanup PASS; final active mapping/reserved/RW counters are zero, with zero grow/release failures,
and image FDs close. Observer-on586 children retain matching complete
UNDO owner logs and initialization traces, no truncation or dropped init events.
No retries, replacement, extra repetitions or tail exclusions.

## Results

| 通常計測・中央値 | Fresh | Fork |
|---|---:|---:|
| P1 API起動 | 22.07ms | 25.18ms |
| P1 同じデータの検証完了 | 30.38ms | 27.50ms |
| P4 API起動 | 25.58ms | 32.54ms |
| P4 同じデータの検証完了 | 41.17ms | 38.36ms |

The ordinary columns are median-of-process child p50 values. API startup excludes
Fresh schema/seed, while equal-state ends at COUNT/SUM validation after seed.
P1 equal-state Fork-minus-Fresh p50 deltas by pair: −2.87/−2.72/−3.35ms;
P4: −2.81/−1.73/−2.41ms. Setup costs are outside these child endpoints.
A primary Fork/P4 COUNT tail816.28ms stays in the observations, affecting means
and full-suite wall. Warmup COUNT787.64ms also stays. No primary startup itself
exceeds100ms. The result does not resolve or reopen #68.

| 詳細診断・平均 | P1 Fresh → Fork | P4 Fresh → Fork |
|---|---:|---:|
| 共通初期化 | 8.34 → 8.43ms | 9.26 → 9.01ms |
| InnoDB全体 | 5.58 → 9.43ms | 6.84 → 11.19ms |
| ↳ 表領域作成／既存ファイルopen・復旧 | 0.71 → 6.52ms | 0.83 → 7.22ms |
| ↳ 後続のtransaction関連区間 | 2.01 → 0.14ms | 2.27 → 0.14ms |
| ↳ バッファプール | 1.30 → 1.31ms | 1.74 → 1.69ms |
| サーバー初期化全体 | 20.00 → 23.81ms | 24.34 → 29.33ms |
| routine構造の作成／検証 | 1.67 → 0.97ms | 2.04 → 1.28ms |

Diagnostic values are equal-size process means (144 children per cell). Nested
rows do not add to their parents. The broad new/existing-data interval has the
same marker boundaries but different branches; do not call its Fresh timing an
existing-file recovery measurement. Its extra Fork time is consistent across all
three process pairs: +5.86/+5.77/+5.78ms P1, +6.57/+6.32/+6.26ms P4. Fresh spends
more in the later transaction-related interval, partially offsetting it. Common
init mean differences are +0.09ms(P1)/−0.25ms(P4), not the main route difference.

Observer API-startup p50 effect (paired median): Fresh +1.40/+3.79ms, Fork
+1.59/+2.16ms at P1/P4. Do not subtract a constant observer correction or equate
elapsed stage time with CPU or physical I/O. The previous source-bound I/O
counters remain historical; this run does not measure every read cost.

## Artifacts and replay

The Japanese [startup guide](startup-lifecycle.md) explains state reuse, file
attachment versus engine reads, nested phases, prior cohorts and limitations.
`summary.json` retains all process metrics, every pair,
tails and observer effects; compressed observations retain every child trace from which its stage breakdown can be regenerated. The timing index binds those traces to original files without duplicating their content.
Source/guest/binary/overlay identities are in inputs.json; raw reports and586
owner logs remain in local digest-bound archives. Git carries the compact
replayable bundle, not hundreds of raw files.

Reproduce in a fresh owned workspace on 398133d0a05f00e53c795f318aec7113261b6cac with
`python3 -B benchmarks/freshforkstartup/build.py` then run.py. The campaign uses
8GiB budget/12GiB free reserve,900s global runtime limit and190s per process.
Copy this bundle's collection scripts into evidence and run collect.py before
cleanup. After cleanup, `python3 -B analyze.py . --check` and
`python3 -B check_analysis.py` require no build/temp files. Eight negative controls
cover wrong warmup contract, missing Fresh seed, failed oracle, premature SQL,
missing/dropped init markers, missing owner and cleanup debt.
