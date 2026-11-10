# PR147 after adoption: before/after lifecycle measurement

## Conclusion

The adopted process-static image did **not demonstrate a consistent whole-suite
speedup** against immediately preceding main in this cohort. Paired suite changes
were small and mixed. Serial peak RSS decreased in every pair for both Fresh and
Fork. One after/Fork/P4 trial failed during Close; the campaign is
**COLLECTED_WITH_FAILURES**, not a correctness or performance PASS.

Recommendation: preserve this baseline and investigate the Close timeout before
another performance campaign or release claim. It occurred only in the after arm
here, but this small cohort does not establish whether static sharing introduced
it, changed the timing of a pre-existing issue, or interacted with the previously
adopted shutdown change. No runtime fix, rollback or additional sampling is made.

## Sources and fixed conditions

The Human authorized PR147 main integration and this immediate before/after
comparison. [PR147](https://github.com/masahitojp/mariamem/pull/147) squash-merged
to `b1218737ffa0bc1d08e9b1285b9bcf6ccf8adc50`; its tree equals approved head
`08a2246a50bf5ce63de97ddf2b118b8df09dca1f`. Development
[42727872452](https://github.com/masahitojp/mariamem/actions/runs/42727872452)
passed all three required checks at that head. Release remains separate.

- Before: `c375edbc1e77bf078f50abc75c9de32ce23a641a`, the merge's actual parent.
- After: `b1218737ffa0bc1d08e9b1285b9bcf6ccf8adc50`.
- Both already include Issue145 shutdown mode selection. Same MariaDB12.3.3
  guest/input pins, Go1.26.10, Apple M1 / 16GiB / macOS27.2 arm64, Pipe,
  GOMAXPROCS8, GOGC100, CGO disabled, buffer pool16MiB and read threads1.
- 1,000 seeded rows; each child verifies COUNT/SUM, changes one row and verifies
  it; next Fork must see the pristine seed. Fresh includes preparation per child.
- 48 cases per process, P1/P4, Fresh/Fork, five paired rounds, alternating arm
  order and rotating cell order. Fork cap equals P; Fresh is worker-bounded.
- Eight positive/negative control processes and eight warmup processes passed
  their expected oracles. Forty primary processes:39 successful, one failed.
  The wrong-seed controls deliberately failed their SQL oracle and cleaned up.
- First Start through final child/Snapshot cleanup is the suite boundary.
  Initial image construction is included once per after process. Compilation and
  downloads are excluded. Process spawn-to-exit is recorded separately.

The prior lifecycle probe is reused from
`dc654406f2a4ca2a4d58237156a0421060556cf8`; its Go sources are unchanged. The
[fixed harness/plan](https://github.com/masahitojp/mariamem/tree/f41b970d4bd34483d4072d719fdbc9a00dc6a62d/benchmarks/issue123postmerge)
binds exact clean product checkouts and hashes both binaries before execution.
This is not a v0.6.2 or pgmem rerun, Ubuntu measurement, or the earlier Go1.27.3
prototype cohort. Do not compose the earlier percentages with these results.

## Whole-suite results

Times are medians in milliseconds of matched successful trials. The percentage
column is the median of the **paired** percentages, not the percentage between
the two independent medians; these can have different signs in this small cohort.
The last column counts pairs where after completed faster.

| Mode | P | Successful pairs | Before suite | After suite | Paired change | Faster pairs |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Fresh | 1 | 5 | 1572.0 | 1566.5 | -0.72% | 3/5 |
| Fresh | 4 | 5 | 586.0 | 600.3 | +0.85% | 2/5 |
| Fork | 1 | 5 | 1172.5 | 1188.6 | -0.78% | 3/5 |
| Fork | 4 | **4; one other after trial failed** | 462.8 | 453.1 | +1.34% | 2/4 |

The failed Fork/P4 trial's40,476.5ms and error are retained below. Its matching
before trial is also excluded from the successful-pair speed statistics, but
neither trial is removed from the saved observations or the outcome census.
This table describes successful execution speed, not expected completion time
including failure. No outlier or slow successful trial was excluded.

## Startup, CPU and memory observations

Per-child values are medians of each process's child p50. RSS is the maximum
resident set over the **whole process lifetime**, not held-child RSS or MiB/DB.

| Mode | P | Start/Fork p50 before → after (ms) | Suite CPU before → after (ms) | Peak RSS before → after (MiB) |
| --- | ---: | ---: | ---: | ---: |
| Fresh | 1 | 21.39 → 20.80 | 2508.2 → 2486.5 | 134.19 → 127.73 |
| Fresh | 4 | 27.08 → 25.93 | 3318.5 → 3251.6 | 431.67 → 401.73 |
| Fork | 1 | 18.94 → 19.10 | 1973.9 → 1957.6 | 136.52 → 129.13 |
| Fork | 4 | 26.09 → 24.03 | 2216.2 → 2097.6 | 513.34 → 453.69 |

Serial RSS reductions were consistent: median paired -6.25MiB Fresh and
-7.17MiB Fork, both5/5. P4 RSS was variable: lower in3/5 Fresh and2/4 successful
Fork pairs, so the large independent-median differences are not stable savings.
CPU paired medians were approximately -0.4% to -1.7%; this is descriptive rather
than a proven portable improvement.

For Fork suites, initial root Start increased from32.20→45.31ms at P1 and
32.68→47.37ms at P4, with after slower in every successful pair. This boundary
includes lazy image creation. The child batch's paired median changes were
-20.02ms at P1 and -8.66ms at P4, while the initial Start cost increased by
13.12/15.36ms. These observations are consistent with a cold setup cost offsetting
some reuse gains, but this run did not separately profile image construction.
Medians of phases are not additive decompositions of the median total.

Successful trials had no Start/Fork or SQL span above100ms. Fresh/P4 Start p95
increased in all five pairs (median41.30→50.19ms), so a blanket startup-tail
improvement is not supported either. Process spawn-to-exit paired changes were
also mixed; they do not rescue a general speedup claim.

## Failed Close and continuation boundary

After/Fork/P4, round1, child43 on lane2:

- All48 child SQL oracles succeeded; the failing child's Fork was29.02ms.
- Retire completed in0.076ms; Close took40,002.45ms and reported guest cleanup
  timeout / disposal incomplete.
- Final counters:50 mapping creates,49 releases, one active mapping,
  2GiB reserved /664,141,824 writable bytes; `release_failures=0` does not mean
  completed disposal. These virtual mapping counts are not RSS.
- The process exited1. Two empty per-process scratch directories remained;
  no guest process survived the executable's exit. Full child timings, errors
  and counters remain in the [failure record](issue123-postmerge-evidence/failure-after-fork-p4-r1.json).

The initial collector stopped after30 processes (14 primary). A separately
committed [resume collector](https://github.com/masahitojp/mariamem/blob/80068033/benchmarks/issue123postmerge/resume.py)
validated the original binary and Go harness hashes, retained the failure and
ran only the26 originally planned remaining processes. No failed run, warmup,
or completed pair was repeated. The interruption occurred between pairs; host
state across that pause is not claimed identical. Remaining26 all succeeded.
This is an observed cleanup failure, not a claim that its cause is known.

## Evidence and reproduction

[Inputs](issue123-postmerge-evidence/inputs.json),
[compact trials](issue123-postmerge-evidence/trials.json),
[summary](issue123-postmerge-evidence/summary.json),
[CSV](issue123-postmerge-evidence/summary.csv),
[completion](issue123-postmerge-evidence/completion.json), and
[checksums](issue123-postmerge-evidence/SHA256SUMS.json) preserve identities,
all56 outcomes, per-run stage distributions, >100ms spans and cleanup counters.
The unique failed run's full timing record is retained; successful raw child
timelines and routine console/build logs are reduced, not copied into main.

Summary verification needs no binaries, temp tree, or network, and does not
rewrite evidence:

```sh
python3 docs/reviews/issue123-postmerge-evidence/analyze.py --check
```

To remeasure, prepare a disposable workspace at the fixed harness commit, then
run its `build.py` and `run.py` with the plan's12GiB free-space floor,8GiB owned
budget and1,800s timeout. Correctness/cleanup failure stops that original runner.
The observed finite continuation is separately pinned above; it is not a
general retry policy. Product sources and compiler are fixed in `plan.json`.
Preserve new results under their own source/host identities.

## Bounded diagnosis follow-up

The later [Close diagnosis](issue123-close-wait-diagnosis.md) used the same two
product sources with a delayed stack observer. Ten alternating Fork/P4 pairs
(960 children) did not reproduce the failure. This does not replace the failed
trial above, establish a fix, or change its COLLECTED_WITH_FAILURES disposition.
