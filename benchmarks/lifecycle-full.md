# Fresh and Fork: complete mariamem / pgmem suites

2026-11-04. **Fresh complete suites were shorter for mariamem in this workload;
pgmem gained much more from switching to Fork.** At four workers the externally
measured48-case process was954ms/1876ms for Fresh, versus1000ms/431ms for Fork.
The earlier near-equal70-case application comparison was not a Fresh comparison.

The main Fork difference is visible in the actual parallel timelines: in two
P4 representative executions, each final worker handled12 cases, but their
cumulative startup cost was692ms/164ms. Connection retirement/Close also differed,
partly because this inherited probe explicitly waits for MariaDB disconnect.
The latter is a recipe choice, not an unavoidable cost of the standard Go helper.
P8 also retained long COUNT intervals; a slow child's duration is not simply
added to the whole parallel suite.

## Fixed comparison

- mariamem main source_commit `bc00b8e66e5fd57bc9b2127001faf8e05952b417`.
- pgmem v1.18.2 source_commit `a61005d37d01e6671f814fe8ca828222e8147df4`;
  tag_object_sha `145e5d2fc70983b89a4bdd8438e547fcd60244ed`.
- Measured harness_source_commit `f6eeb7aeb6ed14759b2929c31e7956ee5f7d0524`.
  Commit-object/tag identities and clean clones checked through git_identity.py;
  the mariamem diff from main contains only benchmarks/lifecyclefull. Both
  executable VCS stamps match this clean harness commit. No runtime overlay.
- Apple M1/16GiB/macOS27.2 arm64, Go1.27.3,CGO0,GOMAXPROCS8. MariaDB12.3.3 /
  PostgreSQL18.3, both TCP with their ordinary MySQL/pgx drivers.
-48 independent cases,1/4/8 in-flight workers. Three fresh-process repetitions
  per cell, one separately labelled warmup per cell. Rotate product/mode order
  and reverse worker-count order on the middle round. No exclusions or added
  primary trials. Download/build are outside measurement.
- Same integer table/1,000 rows. Each case connects, verifies SELECT1 and
  COUNT1000/SUM500500, commits an UPDATE and verifies its value. Subsequent cases
  must start pristine. One version query per process is included.

| Mode | Preparation and isolation |
| --- | --- |
| Fresh | Each case calls public Start and creates/seeds its own table. A worker retains its slot through SQL-client retirement and DB Close. |
| Fork | Start/connect/seed/Snapshot once; retire and close the root before cases. Each case calls Snapshot.Fork. Both Snapshots explicitly use cap=P. Final Snapshot Close is included. |

Each consumer pool has at most one physical connection. This is the existing
small lifecycle workload expanded with Fresh and full timing; it is not the
70-test application suite, an E2E server, a heavy migration or engine-only A/B.
In particular, Fresh's seed work also warms the live engine, whereas Fork starts
from saved database state. Buffer/cache state is not claimed identical.

## Complete process wall time

Seconds, median and observed min–max of three processes. **Primary total is the
external controller's process-start→process-exit interval**, including preparation,
48 cases, final cleanup, Go startup/exit and JSON output. The internal suite timer
is retained separately to explain measured phases; it does not cover all of that
external interval. No phase sum or isolated-Fork multiplication creates this table.

| Workers | mariamem Fresh | pgmem Fresh | mariamem Fork | pgmem Fork |
| ---: | ---: | ---: | ---: | ---: |
|1|2.656 (2.606–2.678)|3.638 (3.614–3.691)|2.533 (2.499–2.583)|0.768 (0.730–0.982)|
|4|0.954 (0.915–0.971)|1.876 (1.769–1.932)|1.000 (0.961–1.076)|0.431 (0.399–0.968)|
|8|0.813 (0.774–0.950)|1.577 (1.536–1.619)|1.151 (0.843–1.533)|0.448 (0.415–0.472)|

Fresh is shorter for mariamem in all nine paired cells. Fork is shorter for pgmem
in eight of nine paired cells; P4 round1 is967.8ms pgmem versus961.4ms mariamem.
That pgmem process has586.7ms outside the internal suite timer (see below).
No universal winner, statistical equivalence or release performance guarantee
follows from three desktop repetitions.

Median **internal suite** times (prepare→final cleanup), ms:

| Workers | mariamem Fresh | pgmem Fresh | mariamem Fork | pgmem Fork |
| ---: | ---: | ---: | ---: | ---: |
|1|2646.5|3556.4|2524.2|721.4|
|4|937.6|1778.7|990.8|381.1|
|8|803.5|1477.1|1139.6|360.2|

## Why a per-child difference becomes hundreds of milliseconds

Below are the **actual median-external-time processes** atP4:
`r0-mariamem-fork-p4` and `r2-pgmem-fork-p4`. For each, select the worker whose
last child finishes last. Its12 sequential children form the observed final
worker lane. Sum only that lane's spans; the other workers run concurrently.
This reconstructs the recorded wall time, rather than summing work across cores.

| Component, ms | mariamem | pgmem |
| --- | ---: | ---: |
| Initial root/schema/seed/Snapshot preparation |67.2|77.5|
| Final worker:12 Fork calls |692.2|163.7|
| Final worker: connections |25.1|63.7|
| Final worker: SELECT1/COUNT/UPDATE/verification/version |84.1|72.9|
| Final worker: client retirement |65.9|0.6|
| Final worker: DB Close |56.1|3.3|
| Worker gaps/join + final Snapshot cleanup |0.2|0.2|
| Outside internal timer: process entry/exit/output/controller boundary |8.9|48.9|
| **Observed external total** |**999.8**|**430.7**|

Rounded rows may not add exactly. Each underlying nanosecond worker budget does.
These are two actual executions, not independently selected phase medians or
proof that changing one component will recover its entire elapsed duration.

The final workers average about57.7ms/13.6ms per Fork. Their difference of44ms
occurs12 times: **about528ms of accumulated startup difference**. This explains
why using a serial30ms difference as a fixed parallel service time understated
the gap. Across the three processes, per-process median Fork latency rises with
workers: mariamem38.9→53.7→77.8ms, pgmem5.9→11.1→17.6ms. Both slow under parallel
execution, with a larger absolute increase for mariamem. Exact CPU scheduling,
bandwidth and engine synchronization contributions remain unseparated.

### Important recipe limitation: explicit disconnect waiting

The inherited probe closes its SQL connection/pool and calls MariaDB
WaitDisconnected before DB Close. That API polls every5ms
([source](https://github.com/masahitojp/mariamem/blob/bc00b8e66e5fd57bc9b2127001faf8e05952b417/mariamem.go#L269)).
The measured retirement phase is typically about5ms; that fits the policy, but
we did not isolate all transport cleanup from polling delay.

The standard Go fixture's child cleanup closes its pool and DB directly; its
WaitDisconnected call is on baseline preparation before Snapshot. Thus the
65.9ms retirement row is **not a mandatory cost for all mariamem applications**,
and the full118ms retirement/Close difference must not be advertised as such.
A direct-Close control or event-based waiting change was not added to this fixed
campaign. Even without assigning retirement cost to the product, the observed
528ms startup difference remains the principal P4 component. Removing a phase's
number arithmetically is not a measured optimized result.

## Long SQL waits and the slow P8 runs

Among144 primary children per worker-count cell:

| Path | P1 SQL spans >100ms | P4 | P8 |
| --- | ---: | ---: | ---: |
| mariamem Fresh |0|0|0|
| mariamem Fork |0|1|3|
| pgmem Fresh / Fork |0 /0|0 /0|0 /0|

All four long intervals are COUNT/SUM: P4 round2 child9 at786.1ms; P8 round0
child44 at791.2ms, round1 child46 at412.9ms, round2 child22 at404.3ms. SQL remains
correct and cleanup succeeds. This cohort does not instrument MariaDB's pool,
so it does not prove every interval has Issue68's previously observed cause.

AtP8, mariamem's internal totals are1522/1140/833ms. In the first two processes,
the final worker's COUNT spans total818/456ms and include the long query. In the
third, the404ms child finishes before another worker: the final lane's COUNT
spans total only68ms. Therefore a400ms child does **not** imply400ms is simply
added to suite time; other work can overlap it. No tail was subtracted or dropped.

pgmem also varies at the full-process boundary: P4 round1's internal suite is
381.1ms but external wall is967.8ms. The586.7ms residual is retained and unknown;
normal pgmem residuals here are roughly46–112ms, versus mariamem about9–17ms.
The boundary includes pre-main execution, result output, process shutdown and
controller handoff; this experiment does not attribute the outlier to any one
of them. It is not a measured pgmem SQL tail.

## Judgment and next action

The answer is **not that mariamem is uniformly slower**. Fresh suites are shorter
here, while pgmem's prepared Fork path removes much more of the startup expense.
For this small input mariamem obtains little whole-suite reduction from Fork,
and parallel Fork can be slower than Fresh when long SQL waits occur.
This does not mean Snapshot is useless for expensive real migrations/seed;
that workload was not measured.

Keep Issue88's16/8MiB comparison as a bounded startup-cost question. The previously
measured server-init interval is the main candidate boundary, but this campaign
does not assign it all to the buffer pool. Separately record the optional
WaitDisconnected recipe as a potential source of avoidable waiting. Issue84's
prewarming hypothesis still needs a matched overlap workload: these timings do
not implement or prove its benefit.

## Evidence and completion

36 primary processes/1728 cases,12 warmups/576 cases, four positive pilots/eight
cases all pass. Four wrong-seed pilots fail at the expected oracle and clean up
four admitted children. Owned scratch is empty after all56 processes; MariaDB's
active mapping/RW/reserved counters and release failures are zero. Both products'
SQL/isolation, case counts, lane non-overlap and configured worker bounds pass.

[Compact records](lifecyclefull/results/compact.json) preserve all case fields and
all19,986 phase spans exactly as integer nanoseconds, using a shared phase-name
map; [projection verification](lifecyclefull/results/projection-verification.json)
checks equality against the original records. Original raw-file hashes are kept;
JSON layout is not. [Summary](lifecyclefull/results/summary.json),
[inputs](lifecyclefull/results/inputs.json),
[assessment](lifecyclefull/results/assessment.json),
[checksums](lifecyclefull/results/SHA256SUMS.json).

```sh
python3 benchmarks/lifecyclefull/analyze.py --results benchmarks/lifecyclefull/results --check
```

This read-only reduction needs no source clones/binaries/caches. It checks all
56 process oracles, exact final-worker budgets, checksums and three analysis
mutations (missing case, hidden failure, overlapping spans). Two binary-path
preflight failures occurred before pilots; [setup record](lifecyclefull/results/setup-attempt.json)
retains their source identities and corrections. No measured trial was relabelled
or discarded. Tooling stayed with existing counters and bounded timestamps; no
new CI or runtime instrumentation was built.

To rerun, use a new disposable workspace (10GiB budget/16GiB free reserve),
checkout the exact measured harness in temp/mariamem and exact pgmem source/tag
in temp/pgmem, copy run.py into evidence, and set MARIAMEM_EXPERIMENT_TEMP and
MARIAMEM_EXPERIMENT_EVIDENCE. Run `python3 evidence/run.py --phase all` under
experiment_disk.py with a1800-second timeout. The runner owns its Go build/module
caches and scratch, checks identities and records its own executable hashes.
Result JSON and module-graph prefixes are normalized with original/published
hashes. A new run is a new cohort, not these historical receipts.

No guest/product/API/generated/release changes, prewarming implementation,
main integration, hosted CI, Linux replication or release qualification occurred.
Lifetime RSS is a process high-water mark, not private memory, retained-child
RSS or a sampled batch peak. All product conclusions are scoped to this input,
normal declared connection paths and one non-isolated desktop.
