# Issue88 — large-table 16/8MiB after startup fix

**Conclusion: the capacity tradeoff persists.**8MiB reduces retained memory and
usually shortens Fork, but both table scans and the measured child lifecycle are
slower in all five pairs. With Fork/whole-test elapsed time the priority, retain
16MiB as the default recommendation;8MiB remains a possible memory-oriented
tradeoff for Human choice, not an adopted default. This fixed comparison is
complete. No automatic additional samples, parameter sweep or release work.

## Exact scope and source

Product source_commit `279fa530d03cab1bd025df91bf5130bbf845a721` includes the
adopted normal-startup-global-concurrency change. Measured source_commit
`9a8944545ef11a43ebd09cc70e5171413874b711`. Runtime/guest/release/module files
are unchanged from product main. Origin guest SHA256
`8e3761eaf65df842191c98cfc4bf493ae08df9374204774f453b9349e21711df`.
Experimental execution uses one Go binary with a guarded argv overlay:
only buffer_pool_size and size_max16M→8M differ. This origin guest hash is not a
separately rebuilt8MiB guest. inputs.json binds the executable and pre/post
source hashes. Selector preimage/negative tests PASS. Root effective settings,
serial child settings and read_threads1 are asserted. No internal timing/queue
observer is installed. The same selector validation path runs in both arms.

Apple M1/16GiB/macOS27.2, Go1.27.3, CGO0, GOMAXPROCS8/GOGC100, Pipe,
MaxForks4. Serial children for timing; separate processes retain0/1/4 children
for RSS after GC/FreeOSMemory/100ms settling. Desktop services and the disk guard
remain active; this is one host, not isolated-host or Ubuntu acceptance.

Reuses the previous issue88poolab fixture:24,576 rows ×1024-byte VARBINARY payload,
primary key. ANALYZE then information_schema reports28,901,376 allocated bytes
(27.5625MiB), exceeding both pools in all20 processes. This is allocated table
space, not an exact resident working-set census. Each arm prepares its own same
schema/seed. Five alternating pairs per mode, serial/hold order rotated. Ten
serial processes each run one separately recorded warmup and8 measured children;
ten hold processes each retain4 children; every process ends with a pristine
verification child.80 primary timed children,10 warmups,40 held,20 final children.
All records and tails are retained. Build104.6s is excluded from timing results.

## Child timing

Values are pooled primary-child p50. Paired change is the median of five paired
process-p50 changes; it need not equal the ratio of pooled medians.

|Boundary|16MiB ms|8MiB ms|Paired change|8MiB faster pairs|
|---|---:|---:|---:|---:|
|Fork elapsed|19.469|18.730|-2.94%|4/5|
|Fork process CPU|31.102|30.189|+0.48%|2/5|
|First scan, lazy connect included|32.287|33.630|+3.92%|0/5|
|Second full scan|31.113|32.717|+5.06%|0/5|
|UPDATE + point verification|0.582|0.590|+0.83%|1/5|
|Connection retirement|0.064|0.063|-0.10%|3/5|
|Close|2.059|1.999|-3.20%|4/5|
|Measured child lifecycle|86.855|88.874|+3.28%|0/5|

The child lifecycle is directly timed from before Fork through Close; it includes
connection setup, two full scans, committed UPDATE + point verification,
retirement, and the first child's effective-setting queries. It is not a sum of
phase medians. Fork p95 is21.979→24.103ms, so no uniform tail improvement.
Every measured individual SQL/Fork/Close phase is below100ms; one lifecycle in
each arm exceeds100ms as the sum of its work, not evidence of a100ms lock wait.
This does not resolve #140 or the deferred UPDATE issue.

Fork CPU improvement is not consistent (only2/5 paired medians improve); the
pooled median alone would give an overly favorable reading. RSS is a matched
checkpoint process increment from its own Snapshot-only baseline, not peak RSS.

|Retained state|16MiB increment|8MiB increment|
|---|---:|---:|
|1 child|72.438MiB|64.391MiB|
|4 children total|288.641MiB|255.625MiB|

## Preparation and whole invocation

Serial process wall from Start through final Snapshot.Close includes schema/seed,
ANALYZE, baseline oracle/capture, the separate warmup,8 measured children, and
final pristine-child verification. It excludes compilation and JSON output.
Its median is2218.575→2252.139ms (+1.51% ratio of medians);8MiB is slower in5/5
paired invocations. Preparation median1362.530→1387.816ms. These totals describe
this serial scan-heavy fixture, not the earlier shop70/P8 application suite.
Whole-process CPU median2810.900→2771.588ms; only3/5 pairs improve. All per-pair
values are in summary.json. Hold-mode totals include deliberate GC/settling and
are resource measurements, not application throughput comparisons.

## Correctness and interpretation

20/20 processes PASS, zero active mappings at each final cleanup. All children
validate pristine seed, serial children commit a mutation and check its point
result, and final children verify baseline preservation. All Close calls succeed.
This is bounded real-guest correctness, not native parity or release Qualification.

The earlier old-source large-table comparison also found a repeated-scan cost.
The new cohort independently supports that tradeoff after the startup fix; do
not combine their percentages. We measured the cost, not cache-miss attribution:
no claim is made about a specific eviction count or physical disk I/O bottleneck.
The standard guest uses its normal embedded storage path.

For the original Fork-time priority,8MiB's roughly0.7ms pooled median Fork saving
is outweighed here by roughly3ms of extra scanning. Therefore a universal speed
recommendation for8MiB is not supported. The stable retained-memory reduction can
still justify it for memory-constrained, small-working-set uses. Choosing that
product tradeoff is a separate Human decision; this report changes no default.
No new uncertainty campaign is needed merely to acknowledge this tradeoff.

## Replay and reproduce

`python3 benchmarks/issue88largecurrent/results/analyze.py --check` recomputes the
summary from compact observations and verifies SHA256SUMS without modifying any
file or reading deleted temp/build output.

For a new run, prepare an experiment worktree containing the measured source,
use Go1.27.3 and the pinned environment/plan.json, then run:

```
python3 scripts/experiment_workspace.py run --timeout 1800 NAME -- \
  python3 WORKSPACE/worktree/benchmarks/issue88largecurrent/run.py WORKSPACE
```

Use min-free8GiB/budget10GiB when preparing it. Runner verifies clean source via
git_identity.py and no product-boundary diff, tests the guarded selector, builds
one binary and executes exactly20 processes. Preserve the new evidence with its
new source identity; it is not another execution of this receipt. Final analysis
and this report are post-measurement tooling/records only. No runtime source was
changed after measurement. Compact JSON/report/checksums and source remain;
owned caches, binary, temporary overlay and completed worktree are disposable.
