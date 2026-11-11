# Timer product candidate: startup improves; whole-suite benefit remains uncertain

Decision now: whether to integrate PR152's bounded timer candidate into main.
**Recommend integration for SQL timing correctness and startup reduction.** On
this Mac, both Fresh and Fork wall time improve in all six paired batches. The
strongest objection is that P4 complete-suite wall/CPU medians are higher, so this
is not an established end-to-end optimization. That limitation was already
accepted for candidate preparation and remains material to the main decision.
Do not justify adoption using P8's large median reduction alone. No merge,
Qualification or release is authorized by this report.

## Measured object and method

2026-11-11, Apple M1 / 16 GiB / macOS27.2 arm64, Go1.26.10,
GOMAXPROCS8/GOGC100, Go Pipe, 16 MiB buffer pool/read1. Exact inputs and binary
hashes are in [inputs.json](inputs.json); the question, fixed counts and budget
were recorded in [plan.json](plan.json) before compilation/measurement.

- Main baseline: `584004b21132e28886330484bfec00fdda99642c`.
- Product candidate: `1f0e6fc4313278c10027864285df7b70a85f91e4`.
- Identical harness: `d24087eedd21c6384c231fb119c8e98da7b370aa`,
  `tests/timer_calibration/runner`. Exact Git commit identities were verified with
  `scripts/git_identity.py`; clean commit archives were built without modifying
  generated product bytes. The runner has no binary VCS stamp (`buildvcs=false`);
  attribution uses the explicit source/archive, harness and binary identities.

This compares **both** product hunks (SQL microsecond selection and bounded probe
omission) against main. The earlier prototype comparison held the SQL correction
constant in both arms; it is not the same baseline and its results are not pooled.
Timing uses host monotonic wall/process CPU, not the corrected guest SQL timer.
The machine is not dedicated or thermal/frequency/CPU-affinity isolated.
Compilation finished before runs; its time is excluded. No new Ubuntu/pgmem/RSS
measurement or exclusive internal-stage attribution is claimed.

Six paired lifecycle batches per arm, each with eight Fresh and 16 sequential
Forks: 48 Fresh/96 Forks per measured arm. Shop70 has five paired suites per arm
at each P4/P8: 50 reads share one child and 20 writes each get a private child,
21 Forks total, cap=P+1. Schema/master seed is in the Snapshot; sample data is
inserted in each child. Complete wall includes preparation, Snapshot, tests and
cleanup. It is not a 48-child batch. One warmup process per arm/workload (six
warmups) is separately retained and excluded from summaries. Arms and P4/P8
order alternate; there are no outcome-selected repeats or discarded tails.
The first Fresh in each process includes lazy static-image initialization;
this is not cold installation performance.

## Results

Lifecycle values are medians of six batch medians. Complete-suite values are
medians of five runs. Percent changes compare those medians; faster-pair counts
use the original paired order. CPU is process CPU across all threads.

| Metric | Main | Candidate | Change | Faster pairs |
| --- | ---: | ---: | ---: | ---: |
| Fresh wall | 21.098 ms | 19.277 ms | -8.63% | 6/6 |
| Fork wall | 18.914 ms | 17.219 ms | -8.96% | 6/6 |
| Fresh CPU | 31.718 ms | 30.074 ms | -5.18% | 4/6 |
| Fork CPU | 33.035 ms | 30.240 ms | -8.46% | 5/6 |
| P4 complete wall | 565.997 ms | 578.597 ms | +2.23% | 2/5 |
| P8 complete wall | 712.912 ms | 566.953 ms | -20.47% | 3/5 |
| P4 complete CPU | 2238.519 ms | 2313.979 ms | +3.37% | — |
| P8 complete CPU | 2545.473 ms | 2455.110 ms | -3.55% | — |

Pooled sequential Fork p95 is 21.879 → 18.157 ms. P4 whole-suite ranges are
544.905–610.928 → 544.831–624.272 ms; P8 ranges are
478.873–807.611 → 491.735–679.558 ms. Five-run p95 is the maximum under the
nearest-rank definition; it is not a reliable population-tail estimate.

| Child metric (105 observations per arm/parallelism) | P4 main → candidate | P8 main → candidate |
| --- | ---: | ---: |
| Fork p50 | 24.096 → 22.276 ms | 32.368 → 28.142 ms |
| Fork p95 | 32.312 → 27.691 ms | 49.674 → 43.680 ms |
| Sample insertion p50 | 47.782 → 50.281 ms | 73.229 → 73.302 ms |
| Sample insertion p95 | 59.706 → 65.423 ms | 104.269 → 115.324 ms |
| Sample spans >100 ms | 0 → 0 | 11 → 12 |
| Sample maximum | 68.049 → 73.652 ms | 446.484 → 451.940 ms |
| Cleanup p50 (connection retirement included) | 3.056 → 3.263 ms | 3.422 → 3.421 ms |

The startup benefit survives in the assembled candidate. Concurrent Fork spans
also shorten in this cohort, while sample loading does not consistently improve.
P8 retains >400 ms sample spans in both arms; fewer total milliseconds in five
suites does not prove the tail mechanism is fixed. P4 shows no whole-suite gain.
These observations support the bounded startup claim, not uniform acceleration,
a proven whole-suite regression, or a causal explanation of sample-loading tails.
All pair deltas and distributions are in [summary.json](summary.json).

## Correctness and adoption conditions

All 38 warmup/measured processes completed with the required counts, baseline
isolation, settings, zero active mappings and empty scratch. Two additional
Pipe ANALYZE controls ran before timing. Baseline delayed queries had no
`r_total_time_ms` field despite 26.25–26.46 ms client wall; candidate reports
25.197/26.110/26.152 ms within [18, client wall+5] ms. Both arms preserved two
rows/one loop, following SELECT and cleanup. See [correctness.json](correctness.json).
Baseline execution/cleanup PASS does not mean its known SQL timer defect passed.

Review cross-check at the measured candidate, against
[the accepted direction](../../docs/decisions/wasi-timer-startup.md):

| Condition | Finding / detection |
| --- | --- |
| Two bounded canonical hunks, no API/Go shim/InnoDB change | Satisfied: `guest/source.patch` diff is +40 lines; timer selection changes reader/frequency together. |
| Other timer profiles and failure oracles retained | Satisfied: `tests/test_timer_source.py`, selection/calibration compiled controls and mutations; `tests/gointegration/timer_test.go` owns TCP/Pipe Fresh/two-child timing/isolation/disposal. |
| Installed generation and both-platform correctness | Satisfied at37023152: [canonical CI42959675387](https://github.com/masahitojp/mariamem/actions/runs/42959675387), all four jobs successful; [verified receipt](../../docs/reviews/timer-product-ci-42959675387/README.md). |
| Correspondence to measured head | `git diff 37023152 1f0e6fc4 -- internal guest scripts tests/gointegration tests/timer_source tests/test_timer_source.py` is empty. Receipt identities are unchanged; evidence/acceptance metadata edits are not relabeled runtime runs. |
| Development checks on measured head | [42991398660](https://github.com/masahitojp/mariamem/actions/runs/42991398660): check/integration/Live required gate PASS at1f0e6fc4. |
| Product-candidate performance comparison | Completed here on one Mac. Ubuntu performance, cold installation and population-wide speedup remain unverified; existing CI cannot prove them. |
| Usage/source ownership and decision boundaries | No contradictory changes found in README/go/python/releasing or release baselines/notes; no experimental overlay. [Generated diff/ownership record](../../docs/reviews/timer-product.md#pr-diff-and-receipt-retention). Main adoption remains Human-owned. |

No new unsatisfied technical condition was found in this scoped review. The
material limitation is whole-suite variability, with P4 wall/CPU increases in
this cohort; CI does not detect or establish that performance effect. If adoption
requires whole-suite speedup or a no-regression claim instead of the previously
accepted startup/correctness scope, this evidence does not meet it. A separate
larger, controlled paired campaign would need an agreed effect threshold and
budget. No additional campaign is started merely to seek a favorable outcome.
This review checks the changed boundary and prior acceptance, not an independent
semantic proof of every regenerated function or a release qualification.

## Replay, reproduction and retention

`python3 benchmarks/timer-product/analyze.py --check` recomputes all statistics
and paired deltas from the three compact CSVs, read-only and without temp files.
These include warmups and every observation used for the claims. Reduction was
compared against the original complete-trace analyzer and matched exactly.
Original hashes and omitted scope are in [retention.json](retention.json).
No CI REST payloads, routine transcripts, binaries or build caches are committed.

For a newly authorized run, use `experiment-workspace` with an 8 GiB workspace
budget and 8 GiB free-space reserve. Check out a clean report branch, copy
`reproduction/{build,run-pairs,compact}.py` to its `evidence/` and run `build.py`
under `experiment_workspace.py run --timeout 2700`. The script builds the two
pinned product archives with the exact pinned harness, independent of report HEAD.
After compilation and an inactivity check, run `run-pairs.py` with
`scripts/experiment_disk.py --work-dir <workspace> --budget-gib 8 --min-free-gib 8
--timeout 900 -- /opt/homebrew/bin/python3.14 <workspace>/evidence/run-pairs.py`.
`compact.py` fetches the original analyzer from its pinned Git object and verifies
CSV replay. Preserve compact results, then remove owned sources/binaries/caches
and the completed worktree. Never reuse these results as a different source's run.
