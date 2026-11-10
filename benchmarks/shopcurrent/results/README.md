# Current mariamem versus v0.6.2 and pgmem: shop70 / P4

## Result

**The current mariamem suite takes664.275ms versus866.888ms on v0.6.2 and
402.470ms on pinned pgmem1.18.2 (five-run medians).** The ratio to pgmem falls
from2.154× to1.650× in this matched cohort. Current mariamem is faster than
v0.6.2 in all five rounds (22.45–25.21% shorter, median paired change−23.83%).
The ratio of suite medians gives−23.37%, a different statistic. The median-time
gap to pgmem shrinks from464.418ms to261.805ms, about43.6% of the old gap.

This establishes improvement for this shop workload on this host; it is not a
universal speed ratio, a release qualification, or proof that any one optimization
caused the difference. All primary runs and tails are retained. There were no
>=100ms individual recorded spans in any of the15 primary runs. This does not
prove that rare long SQL/Close waits have been fixed.

[Open the standalone chart](report.html). GitHub's HTML source view does not render
it; download/open locally. The chart and summary reproduce from retained
observations without temporary checkouts, caches or binaries.

## What was measured

The Human asked to compare current performance with
[pgmem's Japanese homepage](https://shibukawa.github.io/pgmem/ja/) at parallel4.
That page describes70 shop tests (50 shared readers,20 isolated writers), Apple
M3, parallel8, five repeats and a204ms pgmem median. Those published numbers are
not the denominator here. We execute the repository's existing pinned SQL port
on the same M1 as all three arms, with Go Pipe and parallel4.

- Measured harness source_commit:
  `07009d27bf4ec4f5e3f2980f67d616442461831f`.
- Current product source_commit:
  `b1218737ffa0bc1d08e9b1285b9bcf6ccf8adc50`, verified remote main before execution.
- v0.6.2 source_commit: `47121e1be0b399ba4e2270ce3e25c411ade0e2eb`;
  annotated tag_object_sha: `cebdb4114187171bd418b0a1b419e1c27368808d`.
  Its release pin is kept in `release/baselines/v0.6.2.json`.
- pgmemv1.18.2 source_commit: `a61005d37d01e6671f814fe8ca828222e8147df4`;
  annotated tag_object_sha: `145e5d2fc70983b89a4bdd8438e547fcd60244ed`.
  Same pinned reference as previous comparisons; **not a claim about latest pgmem**.
- Named commits/tag objects are checked with scripts/git_identity.py before
  builds. Current runtime tree is unchanged; the experiment adds only the harness
  and release baseline pin. The old source is a verified Git archive; its archive
  hash is retained. Buildvcs stamping is disabled explicitly; inputs.json binds
  each actual binary hash to source and module replacement rather than pretending
  all three binaries have the harness/product's same VCS identity.
- Apple M1,16GiB, macOS27.2 arm64; all three built with Go1.27.3, CGO0.
  Runtime GOMAXPROCS8/GOGC100. This toolchain matches the earlier shop comparison;
  the separate48-child/Go1.26.10 experiments are not merged into this cohort.
- Same70 test bodies/expectations from the prior shop port at harness ancestor
  `f66b7dbb58e2e402ffc11a35749e607a0eb235ea`. The current runner changes only
  module/import paths and parallel4/cap5/shared-reader connection budget4.
  No timing-specific SQL or parameter overlay. Both mariamem arms assert default
  buffer-pool size/max16MiB; adopted product changes remain in the current arm.
- Master data:20 categories,500 products,1,000 users; five migrations with
  totals/audit triggers and a view. Every reader/writer fixture loads the same
  40 sample orders. Read/write expectations cover stock, audit, totals, errors,
  cascades and historical line prices.
- One immutable Snapshot per process. Both engines close the original source,
  fork one shared reader plus20 independent writer DBs: **21 Forks per suite**.
  The public pgmem model uses its existing template for reads and20 Forks. Our
  extra shared-reader Fork equalizes consuming-Snapshot ownership across engines;
  this is a deliberate adaptation, not a literal reproduction of the public plot.
- Cap5 accommodates one retained reader plus up to4 writer owners. Go test
  parallelism is4. Source, compiler and SQL are unchanged between timed runs.
- One separate warmup per arm, then five rounds rotating the three arms; only
  one workload process at a time.15 primary +3 warmups, no retries or exclusions.
  This shared desktop host is not isolated; a Virtualization service remained
  active (about41% of one CPU in the post-run snapshot). No user process was stopped.

## Complete suite and process times

The primary suite clock starts in TestMain before DB boot and ends after all test
and final public Close calls, immediately before trace serialization. It includes
schema/master seed, Snapshot, shared-reader and writer Forks, sample data, SQL and
cleanup. It excludes download, compilation, package initialization and process
launch/exit. Parent elapsed time includes launch, package init, output and exit;
it is reported separately rather than hiding that boundary.

| Arm | Run1 ms | Run2 ms | Run3 ms | Run4 ms | Run5 ms | Suite median ms | Process median ms | CPU median ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| mariamem0.6.2 |840.289|866.888|881.604|878.505|863.120|866.888|896.196|3483.900|
| mariamem current |641.521|648.344|671.559|664.275|669.310|664.275|719.450|2652.130|
| pgmem1.18.2 |368.022|402.631|402.470|388.898|464.160|402.470|469.522|1218.975|

Current versus old process CPU falls23.87% by the ratio of medians. This is CPU
time summed across the process during the suite, not CPU percentage or Fork-only
CPU. With the process-inclusive boundary, current/pgmem is about1.53×, old/pgmem
about1.91×; do not mix those with the primary suite ratios1.65×/2.15×. The process
boundary's extra time was not internally decomposed into initialization, logging
and disposal, so its difference is not attributed to one of them. RSS was not
measured in this campaign.

## Where the differences remain

Pooled duration medians, milliseconds. These stages overlap across tests;
**never add their medians to reconstruct total suite time**.

| Stage | v0.6.2 | Current | pgmem |
|---|---:|---:|---:|
| Boot |46.808|45.670|50.858|
| Schema/master seed import |43.840|39.667|69.921|
| Snapshot + source Close |4.383|4.503|16.220|
| Fork (21 per suite) |49.306|26.243|15.161|
| Load40 sample orders |64.036|59.726|23.472|
| Read test body |1.752|1.843|0.354|
| Write test body |1.669|1.715|1.085|
| Child/final cleanup |10.309|3.330|0.154|

The strongest observed progress is in Fork and cleanup, while repeated sample
loading and business SQL change much less. This explains why a large Fork
reduction does not turn into an equally large reduction in complete application
suite time. Current versus pgmem still differs by about11.1ms in a typical Fork
and36.3ms in a typical sample-load node. Those node differences are not exclusive
contributions to the261.8ms suite gap: they overlap, and pgmem/MariaDB use distinct
SQL dialects, plans and storage engines.

The shared reader's sample load is a prerequisite for its readers; each writer
also loads40 sample orders. Sample loading contains prepared INSERT/UPDATE work,
triggers and transaction commit. This campaign does not subdivide it or identify
a lock/UNDO/host-shim cause. It reuses the unchanged high-level recorder; prior
fine-grained diagnostics keep their original sources and are not proof here.

Cleanup is not an equal guarantee: mariamem waits for disconnect/public Close and
verifies zero active mappings; pgmem records its public Close success. Pgmem's
asynchronous resource retirement is not asserted complete here. The shorter
pgmem cleanup span cannot be read as equivalent complete-resource disposal work.

## Correctness and interpretation

All18 processes pass all70 cases:1,050 primary cases and210 warmup
cases. Each trace has50 read,20 write,21 Fork and21 sample nodes; reader/writer
case names are unique. Both mariamem arms assert16MiB/max and final active
mappings0. Every process leaves its owned scratch empty; pgmem scratch emptiness
is an observation, not a guarantee about all asynchronous resource retirement.

The SQL port retains its earlier documented differences: `$n`→`?` and argument
reordering; CONCAT prefix search; UPDATE JOIN; DIV integer discount semantics;
VARCHAR/AUTO_INCREMENT/inline ENUM; MariaDB per-event totals/audit triggers;
generated lowercase column/index; bulk VALUES master seed instead of
PostgreSQL generate_series; ANALYZE TABLE. ClientFoundRows preserves matched-row
counting. MariaDB DDL's normal implicit commits remain. This is the same
application-model comparison, not identical SQL or a general interoperability
claim. Pinned original hashes and MIT license remain alongside the harness.

The counterfactual old/current comparison uses the same fixture/toolchain/order
and is stronger evidence of improvement than comparing historical reports from
different CPUs/parallelism. It still has only five pairs on one shared Mac.
The absence of a tail here does not close the paused Close failure, #140 or #143.
No product default, architecture, release version or publication is changed.

## Evidence and reproduction

- inputs.json records source/tag/input-file identities, harness/module dependencies and
  actual binary hashes; observations.json combines all18 traces without copying
  raw logs into dozens of result files. original-files-sha256.json identifies
  original per-process logs/traces.
- Read-only replay: `python3 benchmarks/shopcurrent/results/analyze.py --check`.
  It validates all runs/cases, span bounds, Fork/sample census and mapping
  cleanup, then checks summary, standalone chart and SHA256SUMS.
- Three semantic controls reject a missing run, wrong case count and unreaped
  mapping without relying on a checksum mismatch. summary/chart generation has
  no dependency on removed temp/build paths or network.
- For a new authorized run: prepare a clean experiment-workspace at measured
  harness07009d27 with12GiB owned budget/12GiB free reserve, then run build.py
  followed by run.py under the runner's2400-second limit. Go1.27.3 and network
  acquisition of pinned pgmem/modules are required. build.py verifies identity
  and cleanliness and compiles all three test binaries before any measurements.
  run.py fixes18 processes and stops first unexpected failure. Analysis was added
  after measurement and is not relabeled as the measured harness.
- Build outputs, source copies, pgmem clone and task-local caches are disposable.
  Preserve compact source-bound observations and this report; no raw CI artifacts
  or generated source copies are required in a main report.

Recommendation: use this as the current P4 shop baseline. Further work should be
chosen by its effect on the complete suite, especially repeated fixture/sample
preparation, rather than assuming the remaining gap is all Fork. This report does
not automatically authorize another experiment or the #84 prewarm prototype.
