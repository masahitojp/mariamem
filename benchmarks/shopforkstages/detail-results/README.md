# Timer correctness and collation attribution, 2026-11-10

**The millisecond-resolution probe dominates timer characterization, but its
removal trial is stopped at the baseline correctness gate.** SQL ANALYZE reports
zero execution times even for a query that takes about25ms. This needs a separate
clock-selection correction before performance treatment. SQL execution, following
SELECT and cleanup passed; this is not an ordinary-query failure or hang.

**Collation-hash preallocation is not the next worthwhile optimization.** Its77
growth calls total only0.028/0.031ms per child atP4/P8. The stronger target is the
five UCA deep-initialization calls totaling2.164/2.224ms, distinct from registry
construction at1.857/1.883ms. Individual UCA IDs and weight/contraction subcosts
remain unmeasured. Do not remove supported collations or share mutable descriptors.

These are observed elapsed costs in one diagnostic Mac build, not demonstrated
performance savings. In particular the P8 observed runs had sample-loading tails
and much longer suite times than controls; use the observations to select a
candidate, not to claim an uninstrumented partition or improvement.

## Exact source and bounded work

- Product source_commit: `b1218737ffa0bc1d08e9b1285b9bcf6ccf8adc50`.
- Measured harness source_commit: `ff6316626e9594428a36ffba2061e3b6c6edd075`.
- Guest SHA256: `8e3761eaf65df842191c98cfc4bf493ae08df9374204774f453b9349e21711df`.
- Diagnostic binary SHA256: `d1dd1bed0afa29ff40537741905b8746b18783809c1d9c2d4d2810436bb7c319`.
- Source audit: [timer/charset audit](https://github.com/masahitojp/mariamem/blob/76c7d9612a07a88b4cc5f48d0bb60b561e0f352d/benchmarks/timercharset/README.md).
- Go1.27.3, Apple M1/16GiB, macOS27.2; GOMAXPROCS8/GOGC100. Go Pipe,
  unchanged16MiB/read1. Shop70:50 reads sharing one child and20 private write
  children,21 Forks per process, cap=P+1. No unbounded admission or changed SQL.
- One diagnostic build, one ANALYZE process, then16 shop processes: three
  OFF/ON pairs each P4/P8 plus one warmup per cell.63 primary children per cell.
  Every shop process passed its SQL/count/cleanup assertions; no runtime retries.
  A sandbox-denied listener attempt failed before DB startup and was rerun with
  permission. Initial artifact acquisition also required network permission.

The plan allowed at most two builds and24 processes, stopping the timer
treatment if ANALYZE timing was unusable. That stop was honored: zero timer
treatments ran. No clock correction, collation optimization, guest regeneration,
product adoption, CI or release was performed. Canonical product bytes remain
unchanged; generated instructions were overlaid with observers for this binary.

## ANALYZE: an actual baseline limitation

The root creates a two-row InnoDB table, captures it, closes, and a Fork executes
three alternating pairs of these queries through Go Pipe:

```sql
ANALYZE FORMAT=JSON SELECT SUM(id) FROM timer_probe;
ANALYZE FORMAT=JSON SELECT SUM(id + SLEEP(0.01)) FROM timer_probe;
```

| Repeat | Ordinary query wall ms | Delayed query wall ms | Reported table / other time ms |
|---|---:|---:|---|
|0|0.998|24.724|0 / 0 in both queries|
|1|0.222|25.464|0 / 0 in both queries|
|2|0.239|25.240|0 / 0 in both queries|

All responses are valid JSON, report2 rows and1 loop, and omit
`query_block.r_total_time_ms`. Missing that optional field alone is not the
failure criterion: the delayed queries contain no nonzero execution time at all.
All six following `SELECT SUM(id)` calls return3; child/Snapshot cleanup succeeds
with zero active mappings and empty owned scratch. Raw responses survive in
`analyze.json`; assessment can be replayed without running SQL.

The source audit found compile-time cycle-counter selection while runtime cycle
frequency is zero. This cohort again records all cycle fields as zero. That is
a strong source-consistent explanation for missing/zero SQL timing, but no
clock-correction A/B or native ANALYZE comparison ran here. Do not label the
experiment a complete fix or generalize this to all ANALYZE query shapes.
The next timer step is a small, separate WASI clock-selection correction and
repeat of this oracle; preserve real timekeeping and subsequent SELECT behavior.

## Timer cost and an availability wrinkle

| Per-child elapsed, including skipped probes as0 | P4 p50 ms | P8 p50 ms |
|---|---:|---:|
| Entire timer characterization |0.976|0.962|
| Millisecond-resolution probe |0.941|0.932|
| Remaining timer characterization |0.033|0.034|

The probe is bracketed at its exact loop entry/result-store continuation in
`Fn5573`; it lies within the timer interval. Mean probe/total is1.546/1.582ms atP4
and1.289/1.329ms atP8. Thus the hypothesis about the busy resolution loop is now
directly supported; the subtraction is per child, not subtraction of medians.

However,10/63 P4 and5/63 P8 primary children mark the millisecond clock unavailable
(all four metadata fields zero) and skip the probe entirely. Both observer marks
are absent in exactly those cases; the analyzer requires that metadata/mark
agreement. Executed-only probe p50 is1.397ms (53 children) and1.194ms (58 children).
Four warmup children also skip it and are retained. No missing observation is
silently discarded or counted as a normal executed zero-duration probe.

Upstream discovery treats a zero clock reading as unavailable. The host monotonic
clock is time since its origin (`base.go:12635–12649`); the relation between early
zero millisecond reads and the observed availability variation is a source-based
hypothesis, not a separately captured initial return value. This strengthens the
case for fixing the bounded clock contract before optimizing calibration. The
previous cohort's all-available millisecond metadata remains its historical
observation, not a universal guarantee.

## Charset: repeated growth is cheap; deep initialization is material

| Per-child elapsed | P4 p50 ms | P8 p50 ms | Calls / child |
|---|---:|---:|---:|
| Registry initialization |1.857|1.883|1|
| Collation hash growth, summed |0.028|0.031|77|
| Selected charset lookup/init, summed |2.179|2.240|19|
| UCA deep initialization, summed |2.164|2.224|5|
| Entire interval after registry to common end |2.234|2.303|1|

These rows are nested, **not additive**: hash growth is inside registration;
UCA deep initialization is inside selected-charset initialization. Aggregate
function timers do not provide an individual-ID breakdown. Their totals explain
why UCA work is a strong next target, but are not a proof that every nanosecond of
the subsequent interval belongs to UCA. No2ms saving is promised.

Every primary child has1289 non-null registered descriptor slots,1289 insertion
attempts into each name hash, zero charset-hash growth and77 collation-hash
growth calls. Repeated charset-name attempts are expected because many collations
share a charset;1289 is not the number of distinct charset names. The collation
hash starts at64 elements and grows16 at a time; capacity expansion requests
are real, but their measured elapsed cost is too small for this prioritization.
No claim is made that every realloc copied its whole buffer.

The adopted prepared booster already bypasses one producer for two exact default
collation IDs. UCA initialization still includes tailoring, weight-page pointers,
modified pages, contractions and handler selection. Before a new preparation
patch, identify the expensive IDs/branches inside these five calls. Keep immutable
data separate from per-guest READY flags, pointers, locks and ownership.

## Observation controls and retained tails

| Parallel | OFF Fork p50 ms | ON Fork p50 ms | OFF suite p50 ms | ON suite p50 ms |
|---|---:|---:|---:|---:|
|4|24.418|26.632|558.512|579.075|
|8|31.102|34.948|490.936|753.035|

These are pooled child Fork medians and per-process suite medians, respectively.
P8 ON sample maxima were437.373/457.825/456.029ms; OFF maxima were
104.889/106.866/100.509ms. All are retained in observations and `tail-summary.json`.
No sample tail was attributed to the timer or removed from the report. This
observation-only run does not establish a product regression or candidate win.
P8 region p95s are larger: registry7.363ms, UCA9.072ms; elapsed includes scheduling.

Exact guest bytes and symbol map are reproduced using the pinned artifact and
Binaryen recipe. The existing observer binds canonical preimage hashes;
`overlay-detail.py` additionally binds symbols465/794/814/961/967 and their bodies.
It inserts per-module counters and aggregate entry/return timings, plus two
millisecond-probe marks. All callbacks are removed from the module at common
completion; output occurs afterward. Charset counters distinguish insertion
attempts, actual growth, and descriptor slots. Arrays/hash offsets are pinned to
this exact generated code, not portable ABI assumptions. `inputs.json` records
every final overlay file hash. These diagnostic additions can perturb timing.

## Reproduction, checks and retained evidence

Read-only replay after cleanup:

```sh
python3 benchmarks/shopforkstages/detail-results/analyze-detail.py --check
python3 benchmarks/shopforkstages/detail-results/assess_analyze.py --check
```

Both pass. Three negative controls reject a missing active-clock probe mark,
missing UCA measurements and truncated charset counters. Existing context-reader
unit tests passed. Source identity and unchanged product files were checked before
building. Syntax and diff checks cover the touched harness/analysis; unchanged
product release/consumer acceptance was not rerun.

For a separately authorized rerun, use the measured harness commit, acquire the
exact map with `acquire-map.py`, then `build.py`. `run-analyze.py` and
`assess_analyze.py` must be together in workspace evidence; use the former first.
Do not run a timer treatment unless its gate passes. `run.py` runs the fixed16
shop observations. The saved plan limits active work120min, tooling30min,
owned storage8GiB/free12GiB, no CI; acquisition600s, build1500s and per-process
150s guards were used. This is an experimental Go overlay, not a production
guest-source implementation.

One lossless deterministic gzip preserves all16 observations, warmups and roots.
Compact raw ANALYZE responses, source/binary bindings, scripts and checksums are
retained. Duplicate per-run traces, downloaded artifacts, symbol maps, build
outputs/caches and the completed worktree are disposable. No unrelated root
checkout changes are included.
