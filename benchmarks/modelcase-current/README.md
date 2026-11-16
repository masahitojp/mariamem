# Official modelcase adaptation after MemoryEA (2026-11-15)

Conclusion: at P8 mariamem suite median is 422.820ms versus pgmem381.198ms
(+41.622ms, +10.92% ratio of independent medians). Paired suite ratio median is
+6.84%; these statistics differ. Fork p50 is close; sample insertion and test
bodies remain slower. Startup/import are faster. No universal speed or engine
causality is established; this shared-host five-pair comparison is workload-bound.

Sources: mariamem source_commit86328176 (full SHA in results.json), PR201 still
pending at campaign start; this is the approved integration candidate, not a
claim that main merged. pgmem source_commit a61005d37d01e6671f814fe8ca828222e8147df4,
fetched official main, unmodified. Both built Go1.27.4, CGO0, GOMAXPROCS8/GOGC100,
macOS arm64. This is a new cohort; don't subtract earlier Go1.26.10 or older
pgmem release results as a measured improvement.

## Workload and adaptation

[Official website](https://shibukawa.github.io/pgmem/ja/) and its
[modelcase source](https://github.com/shibukawa/pgmem/tree/a61005d37d01e6671f814fe8ca828222e8147df4/bench/modelcase)
define 70 tests:50 reader/20 writer,20 categories/500 products/1000 users and
40 sample orders. Official main store.go compared with our pg adapter differs
only in the revenue query selector/import. Website numbers use a different
machine/date/cohort and are not used as comparison measurements here.

The preserved Close-corrected adaptation comes from Git object
523a8883d434af381f7a9d00a2c6ae571eefc172:benchmarks/memory-ea-inline/suite-20261115/harness.tar.gz
SHA256 e10c2ba5ab3bd7a0185506904a4f3649c7e4be1dc0002946e774d23176b6de1c.
Both arms close the parent then Fork a shared reader DB after Snapshot, and Fork
20 writer DBs. Close errors fail. Maria uses its default parameter interpolation
and in-process transport; PostgreSQL uses pgx and its native wire path. Different
engine/driver/transport implementation remains part of the product comparison.

Both keep SUM total-recalculation triggers and audit. Maria enables
`AFTER UPDATE OF status ON orders` via MARIA_AUDIT_OF=1, consistent with the
[MariaDB12 trigger syntax](https://mariadb.com/docs/server/server-usage/triggers-events/triggers/create-trigger).
The body also checks OLD/NEW status so unchanged status creates no audit row,
matching PostgreSQL. Existing known MDEV-42129 is not re-investigated.

REVENUE_PREAGG=1 on both arms replaces joining raw item rows into outer categories
and aggregating there with an inner SUM GROUP BY product.category_id, then LEFT
JOINs the category totals. All categories, zero totals, filters and order remain.
The original query remains in each store.go. Before timing, TestMatchedSemantics
passed on both engines: original/rewrite results equal; non-status UPDATE and
status=status create no audit; a changed status adds exactly one audit row.
The full suite keeps expected total/order/isolation assertions. This is an
adaptation using equivalent SQL, not unchanged official SQL benchmarking.

## Observations

One warmup per arm, then five alternating pairs at each P1/P4/P8. All36 processes
PASS:2520 test bodies,720 writer Forks,756 sample loads including warmups.
All observations retained in results.json. Builds completed before timings;
capacity monitor active throughout; no profile hooks. No extra repetitions.

|P|Maria suite ms|PG suite ms|Paired suite difference median|Maria process wall ms|PG process wall ms|
|---|---:|---:|---:|---:|---:|
|1|1221.341|793.968|+54.07%|1263.911|850.618|
|4|497.820|415.334|+19.26%|556.718|506.422|
|8|422.820|381.198|+6.84%|451.673|458.477|

Process wall includes startup/exit; suite elapsed is the trace's internal timer.
P8 independent process-wall medians are close (451.7/458.5ms), but their ratio
is not the suite gap. CPU is2161/1465ms, maximum RSS667/1088MB respectively;
wall proximity does not imply equal CPU or memory. RSS is the process's observed
peak, not unique physical memory or a memory ceiling.

Phase values below are per-process p50, then median of five measured processes.
Overlapping phases cannot be added into elapsed time.

|P8 phase|Maria ms|PG ms|
|---|---:|---:|
|boot|42.730|51.833|
|import|27.581|66.237|
|snapshot|5.416|16.273|
|reader_fork|15.750|8.944|
|fork|25.796|24.887|
|sample|69.522|42.499|
|test|1.674|0.972|

Recommendation: the remaining sample-insertion cost is the next relevant target
if further performance work is approved. This campaign does not identify a new
root cause or authorize another optimization investigation.

## Reproduce

harness/ retains SQL, fixture, test and trace source, with module replacement
placeholders. Resolve <MARIAMEM_SOURCE>/<PGMEM_SOURCE> to the pinned clean checkouts.
Build each store package with GOTOOLCHAIN=go1.27.4 CGO_ENABLED=0 GOMAXPROCS=8
`go test -c -p 1 -vet=off -o <workspace>/temp/{maria,pg}.test ./store`.
Place resolved harnesses in temp/maria-suite and temp/pg-suite, run each binary
with -test.run=^TestMatchedSemantics$ and the matched environment first.
Then `python3 measure.py <workspace>` (temp/ and evidence/ must exist), under
scripts/experiment_disk.py with budget6GiB/minfree6GiB/timeout900. The runner
requires macOS /usr/bin/time -l and records all process/phase aggregates.
Binary SHA/buildinfo and source identities are in results.json. No runtime
changes, release or main adoption are introduced by this measurement.
