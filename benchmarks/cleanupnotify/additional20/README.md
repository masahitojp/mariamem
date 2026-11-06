# Issue117: additional20 pairs — consistent cleanup gain, measurable CPU tradeoff

**Conclusion:** notification consistently shortens this recipe's cleanup, while
whole-batch CPU/child is about5% higher. Whole-batch elapsed improvement remains
uncertain. The additional20 pairs support a tradeoff decision; they do not
justify automatic rejection solely at the exact5% reference boundary, or an
unconditional suite-speedup/adoption claim.

Recommendation: retain notification as a candidate for lower WaitDisconnected/
cleanup latency, with the observed CPU cost explicit. The next Human decision
is whether that latency benefit is worth approximately3ms extra batch CPU per
child in this workload. The strongest objection is that full-batch elapsed time
has not reliably improved and its arithmetic mean is worse in this cohort.
If the objective is demonstrated whole-suite throughput with no CPU increase,
this evidence does not meet it. If lower confirmation/cleanup latency is itself
valuable, the local gain is repeatable and can support a conditional candidate.
Production adoption still requires its separate decision and relevant platform
correctness; no more sampling is automatically added here.

## Why this extension exists

The Human challenged the strength of a5-pair verdict and explicitly authorized
20 additional pairs of the unchanged implementation. The original5-pair report
and CPU guard FAIL remain unchanged at
[6f780e5a](https://github.com/masahitojp/mariamem/blob/6f780e5a7a44022e0f5c2c7bef888a233f821795/benchmarks/cleanupnotify/results/README.md).
These are20 new pairs, not a relabelled25-pair acceptance set; prior-summary.json
is retained for separate context. The plan, controller and analysis hashes were
frozen before execution. Old5% references remain visible, alongside magnitude
and uncertainty; the additional cohort is not judged by changing old receipts.

## Exact reuse and workload

- Product `1862f4a89397bddfa1820d835106d3437a438cf7`.
- Measured source `c37d578e68b3068173a6734b38f00e11782cb123`, unchanged.
- Guest `6d7442204d39bc28eb4b34401874b84b4d3f517c2bb698ba7f3a465027c36cbe`.
- Rebuilt binary SHA256 **0104b348e3357a64c798c8756b30b25da411f724df8f2b76235573bb20d94742**,
  exactly equal to the prior experiment. Source/clean checkout and logical
  overlay before/after hashes were checked before timing. No implementation,
  guest, public API, generated canonical code or setting change.
- Same Apple M1/16GiB/macOS27.2,Go1.27.3,CGO0,GOMAXPROCS8,GOGC100,
  Pipe,1,000 rows,48 children,P4/cap4,product defaults.
- 20 fresh pairs,10 notify-first/10 poll-first,strictly alternating order. Each
  arm has960 primary children. Warmups48/arm, wrong-seed1/arm and diagnostic48/arm
  are separate:46 measurement processes total, no extra repetition.
- All expected SQL/seed/update/value/affected-row/isolation, cap and owned-temp
  cleanup outcomes pass. Both wrong-seed controls fail as intended and clean up.
- Prior focused unit/host-race evidence is **REUSED**, bound to its original
  source/report and scope (generated/code excluded from race). It was not rerun
  or relabelled as a new PASS. verification-reuse.json proves identical source,
  overlay and binary. New runtime/reducer checks are separately recorded here.

The main time boundary is48-child Fork + connection + SQL + retirement + DB
Close. Root preparation/Snapshot and final Snapshot.Close are outside this
batch timer but executed and cleanup-checked. CPU is batch user+system/48,
not Fork-only CPU. Lifetime peak RSS in raw records is not retained-child RSS.
Primary holder logging is disabled; generated observer hooks are the same
no-ops in both arms. Diagnostics are separately instrumented.

## Whole-batch elapsed and CPU

All20 primary processes per arm, including every long SQL:

| Metric | Poll | Notify |
|---|---:|---:|
|Batch wall mean ms|649.503|714.751|
|Batch wall median ms|625.856|616.846|
|Batch CPU/child mean ms|61.354|64.524|

Mean wall increases10.05%; the mean paired absolute change is+65.25ms with a
paired-bootstrap95% interval **[-47.82,+178.38]ms**. There is no resolved average
wall benefit or regression from this finite cohort. The pair-median wall change
is-2.28%, interval **[-4.98,+8.45]%**, and12/20 notify processes are shorter.
The ratio of the two independent wall medians is about-1.44%; it is a different
statistic from the median of paired percentages.

CPU increases in17/20 pairs. Pair-median CPU change is **+5.35%**, interval
**[+2.90,+6.74]%**. Mean paired CPU difference is **+3.170ms/child**, interval
**[+1.998,+4.346]ms/child**. This is stronger evidence of a positive CPU cost
within this setup than the original5 pairs supplied; its exact relationship to
the5% reference remains uncertain. Notification-code CPU alone is not measured.

Intervals are prespecified seed117 percentile bootstrap,10,000 resamples of
whole pairs. No child is treated as an independent replicate. They describe
resampling uncertainty in this one-host/time-adjacent cohort, do not resolve
serial dependence or bound future rare tails, and are not a both-platform claim.

## Cleanup mechanism and timing

Pooled per-child medians over960 children/arm, milliseconds. Independent phase
medians do not sum exactly to the cleanup median.

| Phase | Poll | Notify |
|---|---:|---:|
|WaitDisconnected|5.1066|0.0836|
|DB Close|3.3562|4.8814|
|Complete cleanup|8.6083|5.0002|
|Fork|34.3060|35.3999|

All20 pairs meet the local wait>=3ms and cleanup>=2ms reduction references.
The mean of per-process median cleanup differences is **-3.583ms**, interval
**[-3.814,-3.338]ms**; pair-median cleanup change is-43.40%, interval
[-45.57,-37.83]%. The5ms confirmation delay is removed consistently, while
some time appears in longer Close/Fork intervals. This is not an additive
causal attribution or proof of why CPU changes; changed overlap/pacing is a
hypothesis. DB Close still waits for the same completed disposal/lease boundary.

Diagnostic final-session-deletion -> successful-zero confirmation p50 is
5.090167ms poll /0.002458ms notify. The diagnostic CPU/wall is not pooled into
primary estimates.

## Every pair

Positive percentage means notify is slower/more CPU. Times are milliseconds.

| Pair | First | Poll wall | Notify wall | Wall change % | Poll CPU/child | Notify CPU/child | CPU change % |
|---|---|---:|---:|---:|---:|---:|---:|
|1|notify|628.297|1274.488|+102.85|60.044|60.338|+0.49|
|2|poll|599.044|1094.618|+82.73|58.030|64.294|+10.80|
|3|notify|625.158|572.184|-8.47|60.483|64.191|+6.13|
|4|poll|585.615|573.434|-2.08|59.117|61.540|+4.10|
|5|notify|597.911|566.571|-5.24|59.092|62.981|+6.58|
|6|poll|589.108|554.341|-5.90|61.345|60.539|-1.31|
|7|notify|601.427|620.618|+3.19|58.850|66.261|+12.59|
|8|poll|627.191|631.811|+0.74|60.991|66.315|+8.73|
|9|notify|586.297|666.707|+13.71|59.453|68.068|+14.49|
|10|poll|633.010|632.345|-0.10|61.387|65.594|+6.85|
|11|notify|602.253|889.733|+47.73|60.980|59.853|-1.85|
|12|poll|1209.763|584.850|-51.66|58.951|62.856|+6.62|
|13|notify|637.619|607.546|-4.72|61.472|64.188|+4.42|
|14|poll|666.477|835.440|+25.35|63.119|65.421|+3.65|
|15|notify|623.299|1148.614|+84.28|64.452|70.754|+9.78|
|16|poll|627.576|594.244|-5.31|63.213|64.578|+2.16|
|17|notify|648.377|613.074|-5.44|63.348|66.239|+4.56|
|18|poll|622.151|606.751|-2.48|64.485|68.450|+6.15|
|19|notify|652.922|627.054|-3.96|65.152|64.104|-1.61|
|20|poll|626.555|600.601|-4.14|63.124|63.921|+1.26|

Prespecified order/block views (means of paired percentage changes; no rows
removed or selected for acceptance):

| Group | Pairs | Wall change % | CPU change % |
|---|---:|---:|---:|
|notify_first|10|+22.39|+5.56|
|poll_first|10|+3.71|+4.90|
|block_1_5|5|+33.96|+5.62|
|block_6_10|5|+2.33|+8.27|
|block_11_15|5|+20.20|+4.52|
|block_16_20|5|-4.27|+2.51|

CPU is higher on average in both order groups and all four sequential blocks;
the magnitude varies over time. This limits an explanation based solely on which
arm ran first, while not eliminating host/time-dependent confounding.

## Long SQL and requested UNDO holder logs

Primary SQL blocks over100ms: poll1/960,notify5/960; primary UPDATE over100ms:
poll0,notify1. All are retained. Notify r14 child17 has UPDATE801.325ms within
SQL807.531ms. Other long blocks contain short UPDATEs. This observed frequency
difference is not enough to establish a causal change in rare-tail probability.
No tail-filtered aggregate or optional extra run is used for judgment.

The separate96 diagnostic children produced complete untruncated holder/waiter
logs. [holders.csv](holders.csv) is the readable subset; undo-traces.tar.gz holds
all raw events with undo-SHA256SUMS.json. There are25,600 completed purge hold
scopes, zero aborts, two query rseg waits and two background header-page waits,
with no matched UPDATE/purge/page relay and no diagnostic UPDATE over100ms.
Maximum3,136 events/child against the8,192 limit.

Both background page waits are notify diagnostic child19: rseg17881408,
space1/page3,0.798833ms; then rseg17881536,space2/page3,0.024416ms. Entry owner
samples are FOR_IO/WRITE_FIX. Eight IO snapshots in selected logs are not eight
independent waits. Thread values are guest TLS, not OS PIDs, and writer-owner
values are a distinct domain. Samples do not establish continuous ownership or
physical-disk delay. The primary long UPDATE has no holder log because that
mode disables the observer; no diagnostic owner is assigned retrospectively.
Issue68 remains stopped; no new reproduction campaign was started.

## Relationship to the original5 pairs

| Separate cohort | Poll/notify wall median ms | Poll/notify wall mean ms | Pair-median CPU change |
|---|---|---|---:|
|Original5|623.876 /596.046|783.737 /792.627|+6.34%|
|Additional20|625.857 /616.846|649.503 /714.751|+5.35%|

The original CPU guard FAIL remains in its original report. In the new20,
the same numeric CPU-reference flag is also false; the local cleanup reference
passes20/20. The difference between5.00 and5.35 is not a standalone adoption
argument. The tradeoff and uncertainty above inform the Human decision.
The cohorts are not pooled to make a gate pass.

## Reproduction, verification and stop

`PYTHONDONTWRITEBYTECODE=1 python3 analyze.py --check` recomputes summary,
children.csv and holders.csv from retained reports/archive read-only, including
all bootstrap intervals. Run test_analysis.py and test_undo.py for malformed
primary evidence and wrong child/rseg/address/scope/thread/page/overlap controls.
SHA256SUMS.json binds the bundle; all96 raw archive-member hashes are separate.
Python tooling version used here is3.9.6.

For fresh execution, create a disposable workspace at exact c37d578e source.
Copy plan.json,build.py,run.py,frozen.json,prior-inputs.json,prior-summary.json,
analyze.py,undo_analysis.py,test_undo.py from this report into its evidence/.
Run build.py then run.py under the recorded toolchain/budgets. Do not copy
records.json before executing: the controller refuses to repeat a started run.
The controller verifies frozen script/input hashes before launch. New execution
creates new observations; deleted caches/overlay/binary are recreatable and are
not needed for analysis replay.

This Human-authorized extension is complete:20 new pairs plus the fixed controls,
zero runtime changes and zero heavy CI. No further repeats, implementation,
main integration, platform qualification or release happens automatically.
