# Issue88: realistic Pipe shop suite, five runs per arm

**Recommendation: retain16MiB for now.** The prior isolated experiment established
8MiB's Fork/RSS benefit, but this real-suite comparison does not establish a
whole-suite improvement.8MiB wins2/5 paired runs. Its complete-suite median is
1,411.5ms versus866.1ms for16MiB; pgmem reference is499.2ms on this same host.
Large variable delays occur in sample-data loading, not measured test bodies.
The observation cannot establish that8MiB causes those delays or their frequency.
No tail is removed, no new sampling campaign or product default change follows.

[Open the standalone timing report](report.html). It contains all five totals,
median-total-run timelines and a common-axis/individual-axis toggle. HTML has no
network dependencies. GitHub's source view does not execute HTML: download/open
it locally. All18 full traces, including3 separate warmups, are in
observations.json; summary.json is deterministically recomputable.

## What was measured

2026-11-08, M1/16GiB/macOS27.2, Go1.27.3, CGO0, GOMAXPROCS8, GOGC100,
Go `database/sql` over **Pipe on both engines**, Go test `-parallel=8`.
Product source_commit `a3b2b6457147e2b8edbd31fec77ab6ec04f11b22`;
measured harness source_commit `2c4827dc7a54e4247396a4afdaa306f03d4b8665`.
Mariamem origin guest:
`14b41ceaec2b61d111eb749714cc1d6e40bb1fab503e8edc61abf76f16ab9fb1`.
The validated two-argv overlay from the previous16/8MiB experiment is reused.
The **same MariaDB binary** handles both settings; effective size/max are asserted
on every root. Runtime/guest/release/API files are unchanged in Git. This is an
experimental argv selection, not a canonically regenerated8MiB guest.

Pgmem is the earlier comparison's pinnedv1.18.2:
source_commit `a61005d37d01e6671f814fe8ca828222e8147df4`, annotated tag_object_sha
`145e5d2fc70983b89a4bdd8438e547fcd60244ed`. Named identities were verified with
scripts/git_identity.py before builds. Inputs retain binary and overlay hashes,
module bindings/build information and host data. Neither engine was rebuilt or
changed between measured runs; engines run one process at a time, three-arm
order rotated. Compilation/download, process launch and package initialization
are excluded. Every run starts fresh engine/fixture state.

This adapts the public [pgmem benchmark](https://shibukawa.github.io/pgmem/benchmarks/)
and its pinned [MIT modelcase](https://github.com/shibukawa/pgmem/tree/a61005d37d01e6671f814fe8ca828222e8147df4/bench/modelcase):

-20 categories,500 products,1,000 users; five schema migrations, totals/audit
  triggers and a view.
-50 read cases: order lists/details, sales ranking, product search and revenue.
-20 isolated write cases: order creation/cancellation/shipping, user deletion,
  discounts. Each starts with the same40 sample orders.
-Original70 case expectations retained, including totals, audit rows, stock,
  errors, cascades and historical line prices. No driver/framework routing or
  product compatibility feature was added.

For equal Snapshot-source ownership, **both engines close the source and fork
one shared reader DB plus20 private writer DBs** (21 Forks per suite). Public
pgmem uses its original template for reads and20 Forks, so this is deliberately
not a literal rerun of the public204ms/M3 figure. Cap9 permits a retained reader
and up to8 concurrent writer owners. Independent test cases remain bounded by
Go test's8 slots. Whole time starts before boot and ends after case and final
public Close calls. MariaDB additionally waits for disconnect and requires final
active mappings0; pgmem's public Close guarantee is weaker and does not prove
all asynchronous resource disposal is complete. Do not equate their cleanup costs.

## Whole suite

| Arm | Run1 ms | Run2 ms | Run3 ms | Run4 ms | Run5 ms | Median ms | Range ms | CPU median ms |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Mariamem16MiB |866.1|1224.7|747.7|1087.9|796.1|**866.1**|747.7–1224.7|3538.6|
| Mariamem8MiB |812.9|1411.5|1454.0|1421.4|723.2|**1411.5**|723.2–1454.0|3482.3|
| Pgmem1.18.2 |464.5|499.2|593.1|507.2|496.1|**499.2**|464.5–593.1|1620.7|

Paired16→8 suite changes:−6.14%,+15.25%,+94.46%,+30.65%,−9.16%; median paired
change+15.25%. The ratio of the two pooled suite medians is a different statistic
(+63.0%); it must not be mislabeled the paired effect. Five runs are observations,
not a bound on future latency or a reliable estimate of rare-tail probability.
Process CPU covers all host threads during setup/cases/public cleanup, not CPU
percentage, and falls only about1.6% by the ratio of CPU medians here. No new
RSS campaign was run: the prior matched held-RSS results retain their own cohort.

## Where the time went

Pooled stage-duration p50 in milliseconds. Parallel durations overlap; **do not
sum these medians or node sums to reconstruct total elapsed time**. Setup has
five observations; case-level values have multiple observations per run.

| Span |16MiB|8MiB|pgmem|
|---|---:|---:|---:|
| Boot |45.392|45.189|76.227|
| Schema + master seed import |64.202|60.455|99.841|
| Snapshot + source Close |7.062|5.946|19.004|
| Fork, including shared reader |52.177|48.794|29.547|
| Load40 sample orders |130.564|122.678|47.696|
| Read test body |3.786|3.838|0.760|
| Write test body |2.826|2.943|1.881|
| Per-child/final cleanup |7.513|7.234|1.103|

Mariamem's small Fork improvement remains visible; on this workload, repeated
transactional sample loading and its tail dominate more than the tested business
SQL bodies. One sample span consists of many prepared INSERT/UPDATE operations,
triggers and a transaction commit: these traces **do not identify a single slow
SQL statement, lock holder, UNDO operation or shim**.

Sample-loading spans>500ms by run:

| Arm |1|2|3|4|5|Maximum sample span ms|
|---|---:|---:|---:|---:|---:|---:|
|16MiB|0|1|0|1|0|880.822|
|8MiB|1|1|1|2|0|868.641|
|pgmem|0|0|0|0|0|129.335|

The500ms classification is descriptive, not a predeclared acceptance threshold.
The8MiB sample tail sometimes overlaps other work (run1 still improves), and a
shared-reader sample tail delays many readers. Occurrence alone does not equal
its contribution to the critical path. No tail-filtered headline is reported.
Similar earlier #68 waits do not prove the same owner/mechanism in this suite.
No new owner tracing or root-cause claim was added.

## Dialect port and interpretation limits

postgres/store retains the upstream SQL. maria/store is a deliberate SQL port:
`$n`→`?` with explicit argument reordering; CONCAT for prefix matching; UPDATE JOIN
instead of UPDATE FROM; DIV to preserve integer discount semantics; VARCHAR,
AUTO_INCREMENT and inline ENUM schema; equivalent totals/audit trigger bodies
split into MariaDB's per-event triggers; generated lower(name) column/index
instead of the PostgreSQL expression index. Driver ClientFoundRows preserves
matched-row counting for0% discounts. Master seed uses bulk VALUES instead of
PostgreSQL generate_series, and ANALYZE TABLE replaces ANALYZE. MariaDB DDL has
its normal implicit commits. Shared-server resets are explicitly rejected because
this experiment never uses that model. The original70 read/write expectations
pass on all three arms. A general cross-engine schema or wire-support claim does
not follow from those tests.

Consequently16/8MiB is the controlled same-SQL comparison; pgmem is a matched
application-model reference, not identical SQL/plans/storage/cache/durability.
Source-query syntax and setup costs are not hidden or subtracted. Desktop VM,
OS services and experiment disk monitoring remain active. These local numbers
cannot be substituted for public M3 numbers, Ubuntu acceptance or release gates.

## Evidence, reproduction and completion

15/15 primary plus3/3 warmup processes PASS:1,050 primary cases (750 read,
300 write). Every process reports50/20 passed case counts and test exit0. All12
MariaDB processes (warmups included) end with active mappings0 and successful
Close. Pgmem records successful public Close only. All runs/tails retained.
No product candidate, main merge, version or publication is authorized here.

```sh
python3 benchmarks/issue88modelcase/results/analyze.py --check
node benchmarks/issue88modelcase/results/check-chart.cjs benchmarks/issue88modelcase/results/report.html
```

Both are read-only; summary and standalone HTML reproduce byte-for-byte without
temp/build inputs. Chart check executes the JavaScript, verifies three diagrams,
both axis modes and finite/in-bounds span geometry. Browser visual inspection
was unavailable because the CUA browser host was unavailable; no screenshot QA
is claimed. SHA256SUMS.json covers all retained result files.

For a new campaign, make a clean disposable checkout of this branch and clone
pgmemv1.18.2 at WORKSPACE/temp/pgmem. Run the checked-in source identity checks
and runner under the workspace disk guard:

```sh
python3 scripts/experiment_disk.py --work-dir WORKSPACE --min-free-gib 8 --budget-gib 10 --timeout 1200 -- python3 WORKTREE/benchmarks/issue88modelcase/run.py WORKSPACE
```

WORKSPACE contains worktree/,temp/,evidence/. Go1.27.3 and network dependency
acquisition are needed. The runner checks clean source/pgmem identities, builds
two binaries, asserts successful case counts, rotates the three arms for five
runs and writes combined observations. The checked-in runner adds an explicit
workspace argument and final trace aggregation to the original external runner;
assessment records its original hash. port.py preserves upstream source hashes
and can regenerate derived store/test sources (gofmt afterward); fixture.go.txt
and backend_test.go retain the explicit ownership adaptations. Preserve the
committed SQL migrations and license. Do not regenerate or change test bodies
during a timed campaign. Copy resulting observations into a new result directory,
analyze, preserve compact results and clean all disposable build/cache/clone state.

The finite realistic comparison is complete. Missing for an8MiB adoption claim:
a convincing whole-suite tradeoff on the intended workload, Human acceptance,
canonical guest regeneration and supported-platform functional acceptance. This
measurement does not authorize more samples automatically. While that decision
is pending,16MiB remains the unchanged product default.
