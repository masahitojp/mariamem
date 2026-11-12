# Installed candidate: fixed30 performance comparison

All30 suites passed correctness and cleanup. No rerolls or excluded tails. The4 warmups are retained but excluded from the primary summary.

Baseline source_commit `8df45792a927e440972266ee799d6f7223713e14`; candidate source_commit `4e2ac423118dac3233f7bd90862d56b936a893a4`. Both use committed installed runtime sources with the same pinned harness. Pipe16MiB/read1, GOMAXPROCS8/GOGC100, cap=P+1; one Mac.

| P | Wall median baseline → candidate (ms) | Paired median change | Faster pairs | CPU median (ms) | RSS median (MiB) |
|---|---|---|---|---|---|
| 4 | 607.80 → 611.60 | +2.79% | 1/5 | 2430.19 → 2516.27 | 447.31 → 433.23 |
| 8 | 551.68 → 535.45 | -7.68% | 4/5 | 2671.16 → 2697.63 | 710.38 → 713.91 |

Separate P8 SQL timing (3pairs,189 PREPARE calls per arm):

| Arm | PREPARE p50 / p95 / max (ms) | >100ms |
|---|---|---|
| baseline | 1.132 / 7.442 / 395.240 | 1/189 |
| candidate | 1.070 / 6.997 / 22.713 | 0/189 |

Child stages (observer-off, pooled over each arm's5 primary suites):

| P | Arm | Stage | p50 / p95 / max (ms) |
|---|---|---|---|
| 4 | baseline | fork | 22.334 / 29.659 / 33.270 |
| 4 | baseline | sample | 54.311 / 68.744 / 465.997 |
| 4 | baseline | cleanup | 3.099 / 4.979 / 7.290 |
| 4 | candidate | fork | 22.746 / 30.270 / 33.593 |
| 4 | candidate | sample | 58.693 / 70.810 / 81.885 |
| 4 | candidate | cleanup | 3.212 / 4.279 / 7.016 |
| 8 | baseline | fork | 32.560 / 49.717 / 57.539 |
| 8 | baseline | sample | 79.764 / 106.920 / 467.569 |
| 8 | baseline | cleanup | 3.796 / 9.622 / 11.715 |
| 8 | candidate | fork | 32.097 / 55.233 / 60.421 |
| 8 | candidate | sample | 88.716 / 116.541 / 127.988 |
| 8 | candidate | cleanup | 3.534 / 8.994 / 27.922 |

[Full summary](performance/summary.json) retains wall/CPU/RSS p50,p95,max and every paired delta. [Compact observations](performance/compact.json) retain all30 suites, Fork/sample/cleanup stages and all secondary PREPARE observations. The unchanged analyzer reproduces the summary from compact data and rejects four corrupted-evidence controls.

These finite observations do not establish uniform acceleration or complete natural-tail causality. Pending hosted acceptance remains necessary before a separate integration review. Purge and the unobserved owner/pending/read-generation/recovery sequence remain outside this correction.

[Reproduction](../../../benchmarks/dictionary-installed/README.md); [source and harness identities](performance/sources.json); [fixed plan](performance/measurement-plan.json); [completion](performance/measurement-completion.json).
