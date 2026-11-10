# Shop70 / P8: current mariamem versus v0.6.2 and pgmem

**Current mariamem:544.846ms; pgmem:387.054ms; v0.6.2:741.540ms** (five-run
suite medians). Current/pgmem is **1.408×**, versus old/pgmem1.916× in this
P8 cohort. Current is faster than v0.6.2 in all five rounds; ratio of medians
is−26.53%, median paired change−25.33%. These are distinct statistics.

[Standalone chart](report.html) includes all five rounds and the previous P4
comparison. Download/open locally; GitHub's HTML source view is not rendered.

## All runs; no exclusions

| Arm | Run1 ms | Run2 ms | Run3 ms | Run4 ms | Run5 ms | Suite median ms | Process median ms | CPU median ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
|mariamem0.6.2|706.461|741.540|1420.415|1360.140|702.648|741.540|805.614|3911.830|
|mariamem current|527.528|677.779|573.025|537.491|544.846|544.846|589.586|2798.113|
|pgmem1.18.2|489.239|366.952|367.318|387.054|398.658|387.054|471.445|1384.054|

All15 primary and3 warmup processes pass their70 cases (1,050 primary +210
warmup cases). Trace census is50 read/20 write/21 Fork/21 sample nodes each.
Both MariaDB arms end with zero active mappings; scratch is empty for all arms.
No failed run was retried or excluded. This does not resolve previously paused
rare Close failures or prove an absence of SQL waits.

### Tails are still present

- Old r2(1,420.415ms) has one876.066ms sample node. Old r3(1,360.140ms) has
  two813.670/876.294ms sample nodes. All three exceed500ms. These are sample
  loading spans, not a newly identified lock/UNDO/shim cause.
- Current r1(677.779ms) has one437.477ms sample node; current sample p95 is
  123.167ms. There are no >=500ms sample nodes in current's five runs, but it
  would be misleading to call the current distribution tail-free.
- Pgmem r0(489.239ms) has104.171ms in Snapshot + source Close, versus its
  median15.730ms. Pgmem also varies. Its sample maximum is75.191ms.

A fixed500ms cutoff is reported for continuity; it is not a reason to remove
observations. Exact spans and >=100ms counts are retained in summary/observations.
No instrumentation of internal wait owners was added in this campaign.

## Previous P4 versus this P8

| Arm | P4 median ms | P8 median ms | Difference |
|---|---:|---:|---:|
|mariamem0.6.2|866.888|741.540|-14.46%|
|mariamem current|664.275|544.846|-17.98%|
|pgmem1.18.2|402.470|387.054|-3.83%|

The current/pgmem ratio changes from1.650× at P4 to1.408× at P8; median wall
gap changes261.805→157.792ms. Current whole-suite wall is about18% lower at P8,
while its process CPU median rises2,652.130→2,798.113ms(5.50%). Pgmem CPU rises
1,218.975→1,384.054ms(13.54%). These are separately timed cohorts on a shared
Mac, not interleaved P4/P8 pairs. They support testing P8 for this workload,
not a universal claim about optimal parallelism or a pure parallelism effect.
No RSS measurements were taken.

## Stage distributions

Pooled per-node medians in ms. Overlapping stages cannot be summed to explain
complete-suite time. Forks are21 per suite, not70.

| Stage | v0.6.2 P8 | Current P8 | pgmem P8 | Current P4 | pgmem P4 |
|---|---:|---:|---:|---:|---:|
|boot|47.360|45.824|51.185|45.670|50.858|
|import|46.781|39.641|72.554|39.667|69.921|
|snapshot|4.885|4.578|15.730|4.503|16.220|
|fork|69.529|34.715|25.659|26.243|15.161|
|sample|97.760|86.462|40.273|59.726|23.472|
|read|2.998|2.886|0.616|1.843|0.354|
|write|2.245|1.980|1.397|1.715|1.085|
|cleanup|11.504|3.812|0.610|3.330|0.154|

Individual operations get longer at higher parallelism even though more overlap
makes the complete suite shorter. Current Fork26.243→34.715ms and sample
59.726→86.462ms do not contradict whole-suite664.275→544.846ms.
Pgmem Fork15.161→25.659ms and sample23.472→40.273ms also increase.

The current P8 typical Fork gap is about9.1ms; the sample-load gap is46.2ms.
These are not exclusive contributions to the157.8ms suite gap. Sample loads
include order INSERTs, line INSERTs, stock UPDATEs, triggers, prepared execution
and COMMIT. Further tuning should be judged on the full workload and sample
preparation too, rather than treating all remaining time as Fork startup.
This campaign does not identify which sample operation causes the difference.

Recommendation: retain this as the P8 baseline alongside P4. P8 is useful on
this host/workload; do not declare a hard ceiling at4. Keep the remaining sample
load tails visible. No new product change or follow-up campaign is authorized
by this report.

## Method and limits

- Same product sources as P4: current mariamem `b1218737ffa0bc1d08e9b1285b9bcf6ccf8adc50`,
  v0.6.2 source `47121e1be0b399ba4e2270ce3e25c411ade0e2eb` / annotated tag object
  `cebdb4114187171bd418b0a1b419e1c27368808d`, and pgmem v1.18.2 source
  `a61005d37d01e6671f814fe8ca828222e8147df4` / tag object
  `145e5d2fc70983b89a4bdd8438e547fcd60244ed`.
  `scripts/git_identity.py` verifies commit/tag identities before builds.
  No claim about the latest pgmem or remote main after the P4 source pin.
- Apple M1,16GiB, macOS27.2 arm64; Go1.27.3, CGO0, runtime GOMAXPROCS8/GOGC100.
  Shared desktop, not an isolated benchmark machine; no other user process stopped.
- The existing shop model has50 reader cases and20 independent writer cases.
  Both products close the original source and Fork one shared reader plus20 writers:
  21 Forks. This differs from the website's20 Forks using its original read template.
  Master seed:20 categories,500 products,1,000 users. Each child loads40 orders.
  Five migrations include totals/audit triggers and a view.
- All Go/SQL bodies match the P4 harness apart from module imports and named
  P8 controls, verified in p4-p8-source-comparison.json. Parallelism8, Fork cap9
  (one retained reader + eight writers), shared-reader SQL pool8. Both MariaDB
  arms use canonical16MiB/read1 without runtime settings overlays; actual16MiB
  pool size/max is asserted. Same source and SQL between measured runs.
- SQL dialect differences remain: placeholders/argument ordering, CONCAT, UPDATE
  JOIN, DIV, AUTO_INCREMENT/ENUM, per-event triggers, generated lowercase index,
  bulk VALUES instead of generate_series, ANALYZE TABLE, and normal MariaDB DDL
  implicit commits. ClientFoundRows preserves matched-row behavior. This compares
  the same application model, not identical SQL or identical storage engines.
- One warmup per arm, then five rotating rounds; only one workload process at a
  time, no retries and no excluded tails. Suite wall begins before boot in TestMain
  and ends after final public cleanup, before trace serialization. Includes master
  seed, Snapshot, Forks, sample data, test SQL, cleanup. Excludes package init,
  process launch/exit, compilation and downloads. Parent process elapsed is a
  separate boundary. CPU is process CPU during the suite, not CPU utilization.
- maria waits for disconnect/Close and asserts zero mappings. pgmem records public
  Close success; complete asynchronous resource disposal is not asserted. Their
  cleanup times do not represent equal disposal guarantees. RSS is not measured.
- P4 source/results are pinned at2429cc77 and copied into p4-summary.json. Those
  medians came from a separate earlier cohort. P4/P8 comparison is descriptive,
  not a paired experiment proving the causal effect of parallelism. Website M3
  results are not the denominator. Stage spans overlap: do not add their medians
  into whole-suite time. No individual optimization is isolated here.

## Reproduction and retention

Read-only replay: `python3 benchmarks/shopcurrentp8/results/analyze.py --check`.
Retained observations suffice; no temporary build source or cache is required.
Checks validate all18 runs, case/Fork/sample census, span bounds, cleanup, summary,
HTML and checksums. Separate semantic mutation controls reject missing runs,
wrong case counts and unreaped mappings before checksum validation.

For a new authorized measurement, prepare a clean experiment workspace at the
measured harness commit in inputs.json (12GiB budget and12GiB minimum free).
Run `python3 benchmarks/shopcurrentp8/build.py` then
`python3 benchmarks/shopcurrentp8/run.py` under a2400-second workspace guard.
Build verifies source/cleanliness, obtains pinned pgmem/modules, compiles all arms
with the same SDK, and binds binary hashes/module replacements in inputs.json.
Old mariamem comes from a verified Git archive; archive SHA256 is retained.
Buildvcs stamping is explicitly disabled. Run stops on the first unexpected
failure. Analysis files were added after measurement, not relabeled as measured
source. The P8 harness's parent product runtime is unchanged.

Results remain on an experiment branch; no product adoption, release, default
change, Close-failure closure or additional experiment is implied. Build outputs,
source copies and task-local caches are deleted after source/results are pushed.

Measured harness source_commit: `8157db344940fc0870fb984d53d08c3e4ef99ac1`.
