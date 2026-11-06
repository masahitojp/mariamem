# Issue123: initialized-page image over anonymous memory

**Conclusion:** static-page-only reuse is promising for P1 Fork and retained RSS,
but does **not** pass the predeclared P4 Fork-improvement screen. Keep this as an
experimental candidate, not an adopted product change. The fixed campaign is
complete; no additional repetitions were run to obtain a pass.

Recommend one narrowly scoped follow-up to understand P4: a fixed four-Fork wave
with SQL starting only after all four children are ready, compared against the
same anonymous control. Predeclare that it isolates overlap/initialization and
does not replace this full-suite acceptance result. Do not broaden into guest
settings or reopen #68. A Human decision on P4 evidence/accepted scope is still
needed before adoption.

The strongest objection is material: ordinary P4 Fork results are mixed, and the
new first-root image construction adds latency. A favorable separate diagnostic
pair or RSS result cannot turn the failed P4 timing criterion into PASS. Ubuntu
and product integration are also unverified. The completed work demonstrates
correctness on this Mac and a useful local effect, not general support.

## Results and evidence

Exact tested source `69181862b141aa71f25b5ecaa16a500301d15dd9`;
unchanged guest SHA256
`6d7442204d39bc28eb4b34401874b84b4d3f517c2bb698ba7f3a465027c36cbe`.
One ordinary binary for both performance/RSS arms; one separate diagnostic
binary for both diagnostic arms. Mac M1/16GiB, macOS27.2, Go1.27.3.

52 processes completed: all50 positive runs pass SQL/cleanup; both corrupt-seed
controls fail as expected. 1,400 child acquisitions include the two expected
negative children. No incomplete attempts, extra repetitions or tail removal.
Every process ends with zero active/reserved/RW mappings and zero image-owned
FDs. The192 diagnostic children have matching stage/UNDO owner logs, no
truncation, and per-child host phases reconcile with measured Fork time.

All times below are ms. Arm values are medians of five process-level metrics;
percentages are medians of matched-pair changes, not ratios of the two medians.

| Metric | P1 anonymous → pages | P1 paired median | P4 anonymous → pages | P4 paired median |
|---|---:|---:|---:|---:|
| fork_p50_ms | 33.85 → 32.62 | -4.24% | 43.69 → 45.60 | +0.77% |
| fork_p95_ms | 39.31 → 37.18 | -6.76% | 61.82 → 56.94 | +0.72% |
| first_select_p50_ms | 34.85 → 33.63 | -4.75% | 45.28 → 46.88 | +1.83% |
| batch_ms | 2141.99 → 2023.11 | -5.55% | 950.49 → 809.77 | -14.95% |
| suite_ms | 2199.50 → 2130.49 | -3.15% | 1009.34 → 950.65 | -4.57% |
| suite_cpu_ms | 3370.61 → 3339.84 | -2.19% | 4013.31 → 3955.34 | +0.32% |

P1 Fork improves5/5 pairs: −4.24%, −4.00%, −5.17%, −6.91%, −3.48%.
P4 Fork improves only2/5: −4.62%, +4.38%, +0.77%, +4.49%, −16.68%.
The predeclared >=3% / >=4-of-5 improvement criterion therefore passes P1 and
fails P4. All suite-wall/CPU/first-SELECT and RSS guard criteria pass; the overall
next-stage performance screen remains FAIL. A guard pass is not evidence of a
speedup. P1 per-Fork process CPU is also mixed (3/5 improve; paired median−1.23%).

### Retained memory

Process RSS after SQL, including the image cache:

| Held children | Anonymous | Pages | Paired median change | Pairs improving |
|---|---:|---:|---:|---:|
| 1 | 126.22 MiB | 119.34 MiB | −5.41% | 5/5 |
| 4 | 349.42 MiB | 321.66 MiB | −7.95% | 5/5 |

Baseline-to-held per-child increment is73.41→66.44MiB (hold1) and
74.07→67.19MiB (hold4). The retained cache adds one FD while alive; all are
closed at completion. RSS includes mapping/cache effects and is not PSS or a
count of shared physical pages.

### Startup cost and diagnostic limits

First root Start medians increase42.28→107.07ms at P1 and44.64→124.38ms at P4.
Image-build medians are67.44/84.09ms, once per process. The full-suite metric
includes this cost and final cache disposal. Short/Fresh-only users could lose;
this campaign does not claim a Fresh speedup or authorize changing defaults.

The one diagnostic pair per cell reports mean Module-init deltas of
−1.85ms(P1)/−2.69ms(P4), execute-to-ready deltas +0.13/−6.35ms, and total Fork
deltas −1.54/−9.73ms. P1 nested guest server_init changes only+0.06ms. This supports
the hypothesis that a static-only mapping can retain initialization savings
without the earlier whole-file execution penalty, but does not establish page
faults/CoW as the mechanism. P4 diagnostic timing is not the ordinary5-pair
result and cannot override it. Historical whole-file measurements are not pooled
with this cohort; absolute baseline times differ between campaigns.

### P4 timing is still inconclusive

The ordinary P4 cohort retains three anonymous SQL tails (UPDATE780.82ms,
COUNT775.73ms and775.20ms) and one pages COUNT tail810.19ms. Their intervals overlap
37/40/40 and20 later Fork calls respectively. This changes the workload's time
layout: a worker remains in SQL while others continue their lifecycle loops.
This observation does not establish how much of the Fork difference it caused.
One anonymous primary process also has four first-wave Forks at103–115ms.
All are included. Warmup/diagnostic tails remain separately listed in summary.json;
the pages diagnostic COUNT tail is not used to explain another process's tail.
No tail owner/cause is claimed for the uninstrumented ordinary runs, and #68
remains stopped.

`p4-schedule.json` records actual overlap from the retained timelines. Its
Fork-call-overlap metric includes waiting/transport; it is not CPU utilization
or the number of runnable guest threads. A fixed-wave follow-up would answer a
different, narrower question; it must not silently relabel this full-suite result.

### Correctness coverage

The initialized image subset is22 page-aligned ranges /8,863,744bytes (8.453125MiB)
on this16KiB-page Mac; ranges.json records every offset and length. The complete
initial256MiB hash remains
`a742525b94f94000341a4bdbd3136623a763a0c7c982035a5e97d065c8d3b2f7`.
Globals/DataEnd/drop state, child isolation/backing immutability, TLS/grow,
PROT_NONE guard, thread retirement, concurrent acquire/close, partial-overlay
failure and retryable cleanup ownership pass. Removing the init-flag page beyond
DataEnd is rejected by the full-byte comparison. Invalid/overlapping/out-of-range
regions are rejected before allocation. The old whole-image constructor tests
also pass; the page-only-specific test is intentionally skipped in that old arm.

Retained replay and eight negative controls pass (bad summary/oracle/ranges,
extra record, missing timing boundary, clock mismatch, missing owner and altered
stage summary). These are functional observation checks, not extra performance
samples. Main, public APIs, canonical guest and release inputs are unchanged.


This is a bounded Mac prototype, not product adoption. It tests whether retaining
anonymous backing outside initialized pages avoids the prior whole-file image's
post-construction startup penalty. Same-source ordinary anonymous versus
static-page-only arms; older whole-file results are historical, not a third arm
in this experiment. No guest rebuild, pgmem rerun, Ubuntu or CI.

## Mechanism and invariants

One process-local image is built exactly as before: a fresh generated Module,
scan the initial 256MiB, write nonzero OS pages to a sparse 2GiB image, reopen
read-only and unlink. This prototype additionally coalesces the recorded nonzero
pages into ranges. It does not assume `DataEnd` covers all initialized state:
the init flag at offset26981552 is beyond DataEnd17998969.

Each child first owns the usual 2GiB anonymous reservation with initial256MiB
accessible and the rest PROT_NONE. Only the selected ranges are replaced by
MAP_PRIVATE|MAP_FIXED file mappings at the corresponding offsets. MAP_FIXED is
confined to a validated range of the child's not-yet-published reservation;
it does not target arbitrary addresses or other children. The exact original
mapping slice remains the owner for one final Munmap over all segments.
Grow/protection, per-child Module state, thread joining and cleanup are unchanged.
On partial overlay failure, disposal covers both replaced and anonymous segments;
a failed disposal retains typed MemoryReleaseError ownership for retry.

The image factory's lock scope, first-build scan and guest settings are unchanged.
Image pages are initially shared with private writes; this is not sharing a
running InnoDB instance or mutable engine state between children. The snapshot
still restores prepared database files and starts the engine per Fork.

## Fixed campaign

Mac arm64, Go1.27.3, CGO0, GOMAXPROCS8, GOGC100, Pipe, identical1000-row SQL seed.
Ordinary Fork P1/P4 with MaxForks equal to parallel, 48 children, five alternating
pairs per cell (20 processes). Separate held-RSS measurements at hold1/4, five
pairs per cell (20 processes). Two semantic pilots, two expected-failing corrupt
seed controls, four warmups, and four separate diagnostic processes (one pair
per P1/P4), total52. No extra repetitions and no tail removal. Every diagnostic
child retains matching stage traces and UNDO owner logs. Ordinary timing does
not include those observers. RSS is process RSS, not PSS or proof of physical
sharing; forced GC is applied equally at the memory checkpoints.

Predeclared screen, unchanged from the prior whole-file experiment:
Fork paired median improvement >=3% and >=4/5 pairs improving in each P1/P4
cell; suite wall/CPU and first SELECT paired medians <=+5%, without >=4/5
pairs worse by >5%; held total RSS <=+10%. Correctness and cleanup must pass.
Failure of the screen does not authorize extra measurements until it passes.

## Reproduction and retention

Use the exact source in inputs.json in a fresh owned workspace. Run
`python3 -B benchmarks/staticimagepages/build.py` and
`python3 -B benchmarks/staticimagepages/run.py`. The scripts pin Git and guest
identity, isolate builds, enforce8GiB workspace/12GiB minimum free space, and
limit the runtime campaign to900s (each process at most190s). Copy the collection
scripts from this bundle into evidence and run collect.py before cleanup.

After cleanup, `python3 -B analyze.py . --check`,
`python3 -B diagnostic.py . --check`, and `python3 -B check_analysis.py` replay
using retained data only. SHA256SUMS.json covers the compact published bundle.
Original per-process reports and owner traces are retained locally as checked
archives; they are not frozen as hundreds of raw files in Git.
