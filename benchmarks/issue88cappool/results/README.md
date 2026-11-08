# Issue88:16/8MiB with normal startup global cap

**8MiB reduced process peak RSS and CPU in this shop fixture, with a modest
improvement in typical Fork elapsed time. Whole-suite median was almost unchanged.**
A long global-dispatch interval was captured at8MiB despite the startup-cap
patch, so neither8MiB nor the patch is a complete PREPARE-tail fix.

Recommendation: retain8MiB as a promising memory/CPU candidate under the startup
patch; do not claim a major whole-suite speedup or change the default from this
small-fixture comparison alone. The buffer-capacity tradeoff for larger working
sets remains outside this run. Existing larger-fixture evidence keeps its original
source and cannot be relabelled as acceptance of the combined candidate.

## Fixed comparison

Both arms enable the exact prior normal-startup-cap overlay. Read group stays1.
Only `innodb_buffer_pool_size` and `innodb_buffer_pool_size_max` vary together,
16MiB versus8MiB. All25 original argv are checked before the existing selector
changes those two strings. Same binary, shop70/Pipe/P8/cap9, SQL/schema/seed
oracles and environment. Fresh schema/seed and Snapshot are prepared in each
process; logical contents are the same, not a claim of identical physical
buffer-cache state or buffer-dump input bytes.

One live SLEEP control,4 warmups separate,5 alternating pairs per observer mode.
Order alternates16/8 then8/16 and reverses mode ordering between pairs. No
additional samples are taken after observing a tail.

Effective SHOW confirms both buffer variables and read_io_threads1 per run.
The same21 Fork children execute load and recovery cap calls:42 events/process,
1050 total; all select automatic concurrency and resolve16, min1/max500. The
normal16 is the observed global desired concurrency, not16 read slots or an
exact worker count. Every observed I/O group limit remains1. The fresh root
does not execute the two startup cap call sites in this fixture.

## Observation-disabled results

| Metric |16MiB|8MiB|
| --- | ---: | ---: |
|Whole-suite wall median|656.770ms|648.620ms|
|Wall min - max|587.771 - 1258.341ms|571.109 - 854.356ms|
|Wall MAD|68.999ms|57.195ms|
|Per-process Fork p50, median across5 runs|43.149ms|40.986ms|
|Per-process Fork p95, median across5 runs|54.274ms|57.150ms|
|Process CPU median|3291.129ms|3153.710ms|
|Process peak RSS median|775.938MiB|692.844MiB|
|PREPARE >=100ms|2/315|2/315|

Descriptive changes: whole-suite median-1.2%, typical Fork p50-5.0%, CPU-4.2%,
peak RSS-83.094MiB (-10.7%).8MiB wins wall in3/5 pairs, CPU in4/5 and peak
RSS in4/5. Fork p95 increases from54.274 to57.150ms; the p50 improvement does
not imply a uniform tail improvement. A small five-pair sample is not a stable
speedup/variance claim. All pairs, including unfavorable ones, are retained.

Fork is caller elapsed time at P8 (21 children/process), not serial Fork or
Fork CPU. CPU is the entire process across all threads for the full workload.
RSS is Darwin Getrusage process peak. Do not divide its difference by child
count and call it a measured held-child RSS saving: lifetimes and peak timing
vary. A dedicated retention envelope is not remeasured here.

Whole-suite wall includes boot/schema/seed/Snapshot,70 cases, per-child sample
loading, SQL connection retirement and cleanup; compilation and post-workload
observer serialization are excluded. Disabled mode retains short-circuit hooks,
some task-word reads, DB labels, SQL timers and tiny cap receipts. It is not a
pristine product benchmark.

## Sample loading split, observation disabled

Per-loader phase total medians, then median across5 processes; these are not
single-statement latencies, and sums of phase medians need not equal median
loader duration. Each loader prepares3 statements, inserts40 orders and100
items, updates100 stock rows, and commits once.

|Phase total per loader|16MiB|8MiB|
| --- | ---: | ---: |
|prepare|6.287ms|5.966ms|
|order_insert|13.292ms|13.343ms|
|item_insert|46.794ms|44.744ms|
|stock_update|22.901ms|22.323ms|
|commit|0.342ms|0.295ms|

No large ordinary sample-loading regression is apparent in these medians. This
does not test scans/working sets exceeding8MiB; it does not replace the earlier
large-fixture tradeoff. Long PREPARE events remain separately counted.

## Diagnostic results and the remaining8MiB tail

|Metric|16MiB|8MiB|
| --- | ---: | ---: |
|Whole-suite median|661.312ms|684.328ms|
|Fork p50 median|47.129ms|38.300ms|
|CPU median|3485.638ms|3307.487ms|
|Peak RSS median|781.703MiB|692.562MiB|
|PREPARE >=100ms|0/315|2/315|
|Read requests, including background|19061|10714|
|Requests with global stage >=100ms|0|244|
|Group stages >=100ms|0|0|
|Median of per-run global-stage p95|20.702ms|10.497ms|
|Median of per-run global-stage p99|28.761ms|15.573ms|

The244 long requests belong to **one8MiB process**, not244 independent stalls.
Its global-stage p95/p99 are383.782/390.998ms. The five-run median percentile
in the table hides that single bad run, so use the retained per-run distribution
as well. Diagnostic whole-suite8MiB median is3.5% higher; CPU and RSS are lower
in all5 diagnostic pairs. Observer scans hold the guest mutex and affect
scheduling; these timings are not production estimates.

The foreground capture `natural-16-pool8-on`, `TestCreateOrder/two_lines`,
db2/scope1, orders INSERT PREPARE ordinal1, page10:0, request/notifier3:

- PREPARE caller394.149ms.
- Initial global queue389.421ms; initial read group0.001ms.
- Synchronous I/O0.002ms.
- Completion global queue6.559ms; completion group0.025ms.

The long **initial** stage has no retained blocked-gate event. The later
completion stage has active19-long0-waiting2=17 > cap16, but that cannot explain
the earlier389ms by itself. Do not generalize the prior cap1 rejection mechanism
to every remaining tail. Which progress condition delayed the initial task is
still unknown. The existing compact evidence is linked to #140; this step does
not start another instrumentation/parameter campaign.

This capture shows the patch is not a complete global-tail fix. It does not
establish that8MiB caused a regression: only one diagnostic8MiB process has it,
and unobserved PREPARE tails also occur at16MiB. Counter/profile observations
are point-in-time, not a continuous ownership history.

## All pairs

|Mode|Pair|16MiB wall|8MiB wall|Wall delta|CPU delta|Peak RSS delta|
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
|disabled|1|1258.341ms|854.356ms|-32.10%|-6.48%|-184.047MiB|
|disabled|2|587.771ms|591.425ms|+0.62%|-2.44%|-54.875MiB|
|disabled|3|777.366ms|648.620ms|-16.56%|-6.40%|+19.562MiB|
|disabled|4|656.257ms|571.109ms|-12.97%|-2.96%|-143.203MiB|
|disabled|5|656.770ms|666.296ms|+1.45%|+0.52%|-86.562MiB|
|diagnostic|1|661.312ms|684.328ms|+3.48%|-3.26%|-89.141MiB|
|diagnostic|2|741.978ms|686.391ms|-7.49%|-5.74%|-0.047MiB|
|diagnostic|3|620.927ms|642.734ms|+3.51%|-2.22%|-100.625MiB|
|diagnostic|4|645.745ms|620.941ms|-3.84%|-4.98%|-102.531MiB|
|diagnostic|5|666.734ms|695.873ms|+4.37%|-6.62%|-105.406MiB|

## Identity, checks and reproduction

Measured source_commit `73c358ebdb06ed88f8da1d45af8abaa2d0655425`. Parent diagnostic source
`87510b1a909d14846d010a62f6e575d7887f951b`; product source
`a3b2b6457147e2b8edbd31fec77ab6ec04f11b22`; origin guest
`14b41ceaec2b61d111eb749714cc1d6e40bb1fab503e8edc61abf76f16ab9fb1`.
Go1.27.3,macOS27.2 arm64,Apple M1,16GiB,GOMAXPROCS8,GOGC100,CGO0.
Clean Git commit identity is checked before build. The exact previous overlay
is reused; no new runtime hook or patch is introduced. Binary and all original/
overlay file hashes are in inputs.json. Committed internal/,guest/,release/,
go.mod/go.sum remain equal to the product pin. This is an experimental generated-
Go overlay, not canonical C/WASM regeneration or both-platform qualification.

Existing race observer/selector/startup-cap controls pass. Live SLEEP verifies
capture; nonempty I/O is required when observation is on. All1750 SQL cases
PASS,25 zero-mapping cleanups,286 observer closes,1050 resolved cap events, no
truncation. Single Mac only; no new native reference or Ubuntu campaign.

All-request compact timings, SQL phase arrays, traces, cap receipts, referenced
request metadata, the two bounded profiles, inputs and checksums are retained.
Unreferenced I/O metadata is explicitly reduced to census/digest, not a claim
that full counter history is recoverable. Queue observations are N/A with the
observer off. Profile bytes are verbatim, including trailing blank lines;
source/tooling whitespace checks are separate.

```sh
python3 benchmarks/issue88cappool/results/analyze.py --check
```

Replay checks effective buffer/read/cap values, all-child cap execution counts,
group/stage ordering, queue formula, profile/page/request/notifier binding,
SQL/cleanup counts, summary/checksums and seven negative mutations. It is read-
only and works after cleanup without deleted build/cache/network.

A separately authorized fresh reproduction uses the same disposable workspace
layout and `python3 benchmarks/issue88cappool/run.py WORKSPACE` under the existing
disk guard. Plan is committed; new receipts keep their own source. Rare tails
are not guaranteed. No automatic repetition follows this finite comparison.

Budget2h active/30min tooling/CI0. Elapsed wall through initial report is about6.8min,
including128.7s compilation; active/tooling time is not separately metered.
Owned recreated caches/build/worktree are removed after evidence is saved and
pushed. Pre-existing user edits are preserved. #88 remains open for disposition/
broader capacity acceptance; no default adoption, main integration or release.
