# Issue140: keep normal global concurrency through startup

**The temporary global cap is an effective intervention point in the diagnostic
cohort. Keeping normal concurrency eliminated >=100ms global-dispatch intervals
in the five patched diagnostic processes. Observation-disabled whole-suite
median and spread improved, but long PREPARE calls remained.**

Recommendation: keep this as a promising bounded candidate for review; do not
claim a complete fix, a production52% speedup, or adopt a new default yet. The
strongest objection is the collector interaction: the largest effect is in the
mutex-scanning diagnostic cohort, while unobserved tails persist and CPU rises
slightly. No extra sampling or second remedy is started in this step.

## Exact intervention

Read group remains1 and buffer pool remains16MiB. Only the two startup calls
in `buf_dump_load_func` and redo recovery change from
`set_concurrency(srv_n_read_io_threads)` to `set_concurrency()` (argument0).
The original load/recovery work, subsequent restoration, mutex, min/max clamps,
read/write task groups, queue order, SQL behavior and cleanup remain intact.

The normal calculation is2 times guest-reported hardware concurrency, clamped
by the existing min/max. It resolves to **16**, with min1/max500 here. This is
a desired global concurrency used for wake/create decisions, not an exact
thread count or unlimited mode. The experiment does not measure peak worker
count; process CPU/RSS are observed resource outcomes.

`candidate.patch` shows the C equivalent against pinned MariaDB12.3.3. This
spike does **not** rebuild canonical C/WASM: a guarded generated-Go overlay
changes only those two virtual-call arguments. It is not canonical guest
qualification. Vtable slot12 maps to Fn16604 (T0 index12320). Exact function
preimages bind Fn17499(load), Fn18569(recovery), Fn16604(set_concurrency);
the original clamp/store is used and effective values are recorded immediately
after the original store under its existing mutex. Source excerpts and all
original/overlay hashes are retained.

All21 Fork children in each process execute both patched call sites exactly
once:42 events/process,1050 events across25 valid processes. Requested read
count is1 throughout. Baseline resolves1, candidate16. The fresh root does not
execute these two call sites in this fixture; this does not claim Fresh benefit.
Root SHOW verifies read_io_threads1, and every observed I/O group limit is1.

## Observation-disabled comparison

Five alternating pairs; same binary with read registry/profiler disabled. Hook
calls, task-word reads, empty registry lookups, DB labels and SQL phase timers
remain, plus tiny startup cap receipts in both arms. This is not pristine-product
benchmarking. Warmups and the live SLEEP control are excluded.

| Metric | Temporary cap1 | Normal cap16 |
| --- | ---: | ---: |
| Whole-suite median |738.690ms|663.754ms|
| Minimum - maximum |550.256 -1323.374ms|569.435 -994.400ms|
| Median absolute deviation (MAD) |188.434ms|94.319ms|
| Process CPU median |2806.114ms|2853.875ms|
| Process peak RSS median |756.406MiB|766.266MiB|
| PREPARE >=100ms |4/315|4/315|
| Processes with long PREPARE |4/5|3/5|

The descriptive median improvement is10.1%; MAD is about50% smaller. Candidate
wins3/5 paired whole-suite times and loses2/5. CPU median increases1.7%; CPU
increases in4/5 individual pairs. Peak RSS medians differ by9.86MiB, with mixed
paired changes including one+148MiB pair (all values retained). Five runs do
not establish a stable variance reduction, future tail rate or negligible
resource regression. The four remaining candidate PREPARE tails are unprofiled;
their waiting layer is **unknown**, not automatically the same global pool.

Whole-suite wall includes boot/schema/seed/Snapshot,70 cases, sample loading,
retirement and cleanup. CPU includes all host threads for that workload. Peak
RSS is Darwin Getrusage process peak, not per-child retained RSS. Post-workload
observer serialization and compilation are excluded from these workload metrics.

## Diagnostic comparison

| Metric | Temporary cap1 | Normal cap16 |
| --- | ---: | ---: |
| Whole-suite median |1322.394ms|629.052ms|
| Minimum - maximum |1031.406 -1352.293ms|587.553 -651.177ms|
| MAD |29.899ms|6.332ms|
| Process CPU median |3052.723ms|3005.275ms|
| Process peak RSS median |778.328MiB|775.578MiB|
| PREPARE >=100ms |6/315|0/315|
| Read requests (including background/startup) |17675|17976|
| Requests with global stage >=100ms |2072|0|
| Group stages >=100ms |0|0|
| Median of per-process global-stage p95 |775.092ms|21.209ms|
| Median of per-process global-stage p99 |780.712ms|31.604ms|

All5 diagnostic pairs improve in wall time. This is a strong intervention result
for the observed dispatch mechanism, **not a52% production speedup claim**. The
observer scans queued tasks under the guest mutex; changing concurrency may
change sensitivity to those added costs. On/off cohorts are separate samples,
not replay of identical scheduling.2072 requests are correlated work from five
processes, not2072 independent stalls. Every read has two dispatch stages. The
percentile table uses the median of five per-process percentiles, not a pooled
quantile. Full per-run p50/p95/p99/max, timings and denominators are retained.

## All fixed pairs

| Mode | Pair | Baseline wall | Candidate wall | Delta | Long PREPARE baseline/candidate |
| --- | ---: | ---: | ---: | ---: | ---: |
|disabled|1|738.690ms|663.754ms|-10.14%|1/1|
|disabled|2|560.383ms|994.400ms|+77.45%|1/1|
|disabled|3|1214.509ms|569.435ms|-53.11%|1/0|
|disabled|4|1323.374ms|896.560ms|-32.25%|1/2|
|disabled|5|550.256ms|594.642ms|+8.07%|0/0|
|diagnostic|1|1337.438ms|629.052ms|-52.97%|2/0|
|diagnostic|2|1261.940ms|651.177ms|-48.40%|1/0|
|diagnostic|3|1031.406ms|624.000ms|-39.50%|1/0|
|diagnostic|4|1322.394ms|635.384ms|-51.95%|1/0|
|diagnostic|5|1352.293ms|587.553ms|-56.55%|1/0|

## Checks, failure and evidence

Valid measured source_commit `8d36aed9054618f0ed6993bfdedaab69d0119acc`. Product source
`a3b2b6457147e2b8edbd31fec77ab6ec04f11b22`; origin guest
`14b41ceaec2b61d111eb749714cc1d6e40bb1fab503e8edc61abf76f16ab9fb1`.
Same binary across arms; clean source identity checked before build with
git_identity.py. Committed internal/,guest/,release/,go.mod/go.sum unchanged.
Go1.27.3/macOS27.2 arm64/Apple M1/16GiB/GOMAXPROCS8/GOGC100/CGO0.

One positive control,4 warmups,20 natural suites: **1750 SQL cases PASS**,
zero active mappings after25 processes,286 closed read observers and no
truncation. Existing observer/selector controls plus startup argument/phase
validation and resolution tests pass with `-race`. This fixture is not arbitrary
app support, native parity requalification or Ubuntu acceptance.

Initial source f937d899 had a collector-composition bug: the p8 replacement
discarded inherited read/I/O hooks. SQL and cap receipts were present but all
I/O lists empty; the analyzer rejected them. That attempt is INVALID for queue
comparison and is excluded above. `invalid-attempt1.json` preserves its identity
and bounded outcomes. The fixed source composes the new hook onto the inherited
overlay and rejects empty I/O observations immediately after the live control.
No failed receipt is relabelled. The second run uses experiment_disk.py with
the same disk/time budgets because the workspace helper permits only one run
per fresh workspace; the original helper receipt remains unchanged.

All-request compact timing tuples, SQL phase arrays, trace spans, cap receipts,
referenced request metadata, selected profiles, source/binary hashes and checksums
are retained. Unreferenced I/O metadata is reduced to a census/digest; its full
counter history is not reconstructable from a digest. Disabled queue observations
are N/A, never zero. Verbatim profile bytes retain their trailing blank lines;
source/tooling diffs are checked separately.

```sh
python3 benchmarks/issue140startupcap/results/analyze.py --check
```

Read-only replay checks effective settings/cap phases, all-child call counts,
min/max bounds, stage/group chronology, queue gate formula, page/request/actual
notifier/profile bindings, case/cleanup counts, summary/checksums and six negative
mutations. No deleted source/build/cache or network is required.

For a separately authorized reproduction, create a disposable clean checkout
at the valid source with worktree/temp/evidence, and run the existing disk guard
with `python3 WORKTREE/benchmarks/issue140startupcap/run.py WORKSPACE`. Plan and
source acquisition pins are committed. New runs retain their own identity and
are not guaranteed to capture a rare tail.

The2h active/30min tooling/CI0 budgets are retained. Elapsed wall through valid
measurement was about20min, including builds/waits; active/tooling time was not
separately metered, but cannot exceed that wall interval. Reporting/cleanup
continues afterward. Owned recreated caches/build/worktree are removed after
preserving/pushing evidence. No new parameter sweep, product adoption, main
integration, Qualification or release is authorized by this spike.

## What remains decidable

This intervention is more promising than simply raising read_io_threads: it
keeps the read group fixed and directly avoids the startup cap. A bounded
candidate review can now weigh this mechanism evidence against the remaining
unobserved PREPARE tails and small CPU cost. If production work is chosen, the
minimal C patch needs canonical regeneration and appropriate platform/correctness
checks; that is a separate step. Do not require indefinite additional sampling
before acknowledging the observed improvement, or call all remaining tails fixed.
