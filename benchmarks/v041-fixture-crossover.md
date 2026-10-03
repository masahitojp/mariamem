# v0.4.1 fresh/prepared-state crossover diagnostic

## Boundary and source

- Exact common source: released `v0.4.0`,
  `39537e9bb2fbbc28315e1ff672960ad734a9e399`.
- Experiment branch: `experiment/v041-fixture-crossover`; production code and
  configuration are unchanged. The nested diagnostic module deliberately
  replaces its mariamem dependency with that exact worktree. This is not the
  external-consumer distribution experiment.
- Apple M1, 16 GiB; macOS 27.0.1 (26A434), arm64; Go 1.26.8.
  Measurement began 2026-10-03 10:17 UTC.
- Runtime: public `Options{}` / direct-linked generated-Go, MySQL wire.
  Every suite reports `13.1.0-MariaDB-embedded`.
  Guest SHA-256:
  `33d351b4edaddce9dd52db375c6c3f2a5ff13c259bc6788794daf5bf8bf3e008`.
- Three repetitions of each actual 10/50/100-test suite, both modes and both
  fixtures: **36 independent suite processes, 1,920 measured isolated tests**.
  Four one-test warmups are excluded from statistics. The whole compile and
  measurement campaign held the common fan-out exclusive lock; no competing
  benchmark/build workload ran concurrently.

A suite reuses **one consumer process** and its ordinary Go heap/allocator for
all tests. Each test receives a fresh database/runtime; the prepared mode shares
only the published immutable files. No forced GC, scavenging, sleeps, reset SQL,
MariaDB setting changes, or slow-run removal is used. OS caches are not flushed.

Stop conditions were any SQL/fixture/transaction/isolation/cleanup failure,
incomplete suite, or 900-second supervisor deadline. No condition fired.
The supervisor's ability to terminate its diagnostic process is not in-process
forced guest reclamation.

## Existing preparation workloads

| Level | Existing source | Preparation actually performed |
| --- | --- | --- |
| Current bulk fixture | [canonical Go fixture](goisolation/main.go) | One InnoDB `benchmark_rows` table; 1,000 rows with INT PK and 32-character VARCHAR payload, bulk insert transaction, COMMIT and COUNT/data verification |
| Ordinary ORM migration/fixture | [GORM dogfood](../tests/consumer/gorm/dogfood_test.go) | Unchanged User/Address model shapes; real GORM AutoMigrate/schema discovery, unique index, foreign key, timestamps, one seeded parent/child pair |

The existing ORM example is representative of a small application schema, but
its preparation is cheap. No existing substantial application migration/large
fixture workload was found in the current repository. This lane does not invent
one or inflate inserts/migrations to favor Fork. The heavier-preparation
crossover therefore remains unmeasured.

Fresh mode includes Start, ordinary client/GORM initialization, identical
preparation and fixture verification on every test. Prepared mode includes one
Start + that preparation + disconnect acknowledgement + Snapshot publication
and source Close at suite entry, then Fork and identical fixture verification
per test. Each test commits a private update, verifies rollback, closes its SQL
pool, waits for disconnect and closes the DB. Each next DB verifies pristine
seed values, detecting committed-write leakage. Final Snapshot removal is
included in suite time. No test inherits a session or active transaction.

## Actual complete suite times

Seconds; medians of three independent suites. Ranges retain every run.

| Preparation | Tests | Fresh total p50 (range) | Prepared total p50 (range) | Prepared minus Fresh |
| --- | ---: | ---: | ---: | ---: |
| 1,000-row fixture | 10 | 2.384 (2.271–3.440) | 4.671 (3.961–4.906) | +2.287 s / +95.9% |
| 1,000-row fixture | 50 | 15.185 (15.085–17.146) | 22.045 (19.195–25.100) | +6.860 s / +45.2% |
| 1,000-row fixture | 100 | 35.136 (34.970–35.341) | 41.616 (41.526–42.656) | +6.480 s / +18.4% |
| GORM User/Address | 10 | 2.470 (2.459–2.552) | 4.479 (3.778–4.538) | +2.009 s / +81.3% |
| GORM User/Address | 50 | 16.259 (14.996–16.958) | 20.320 (20.057–20.967) | +4.061 s / +25.0% |
| GORM User/Address | 100 | 30.487 (29.222–30.818) | 38.336 (36.151–39.016) | +7.849 s / +25.7% |

Fresh wins all **18 paired suites**, not just the medians. Three suite repetitions
are diagnostic evidence, not a canonical tail-confidence campaign.

## One-time and per-test costs

One-time prepared setup is explicitly paid, not hidden or assumed free.
Phase medians are independent and do not necessarily sum to setup median.

| Preparation | Base Start → first SQL p50 | Prepare + verification p50 | Disconnect p50 | Snapshot p50 | Full one-time setup p50 / mean |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1,000-row fixture | 41.4 ms | 5.0 ms | 5.7 ms | 682.8 ms | 1047.4 / 1125.7 ms |
| GORM User/Address | 40.6 ms | 4.2 ms | 6.3 ms | 430.2 ms | 479.1 / 605.6 ms |

Per-test statistics pool all 480 cases per preparation/mode. Readiness includes
API entry, client initialization, preparation where applicable, and fixture
verification. Complete case time also includes transaction work and cleanup.
Percentiles use linear interpolation; no samples are removed.

| Preparation / mode | Ready p50 / p95 | Fresh preparation p50 | Complete case mean | Complete case p50 | Ready ≥500 / ≥900 ms |
| --- | ---: | ---: | ---: | ---: | ---: |
| 1,000-row Fresh | 336.8 / 375.1 ms | 4.8 ms | 335.3 ms | 345.2 ms | 3 / 3 of 480 |
| 1,000-row Fork | 398.4 / 441.0 ms | — | 406.7 ms | 407.3 ms | 7 / 1 of 480 |
| GORM Fresh | 311.0 / 348.0 ms | 3.2 ms | 304.6 ms | 319.9 ms | 1 / 1 of 480 |
| GORM Fork | 377.1 / 413.0 ms | — | 379.4 ms | 386.3 ms | 4 / 0 of 480 |

### Why these are not the canonical 38/105 ms startup medians

The first per-test API entry in each independent suite has median approximately
**41 ms Fresh / 110 ms Fork** in both scenarios. Later entries in the same
consumer process are substantially slower: pooled API-entry medians are
331/396 ms for the bulk fixture and 307/376 ms for GORM. Preparation is only
3–5 ms and normal Close is about 7–8 ms. Most additional time is therefore
inside the public Start/Fork call in repeated same-process use, rather than
migration SQL or test cleanup.

This observation includes natural runtime/allocator/scheduling effects; this
lane did not profile them or prove an exact cause. Do not replace the canonical
independent-process startup baseline with these suite percentiles, infer a
live-object leak, or attribute every slow case to the known page-cleaner race.
The [lifetime investigation](v04-snapshot-memory-lifetime.md) and parallel soak
lane address different resource/lifetime questions.

## Crossover and product interpretation

For a descriptive constant-cost model:

`Fresh(N) = N × mean complete Fresh case`

`Prepared(N) = mean one-time setup + N × mean complete Fork case`

The observed means give:

- Bulk fixture: `335.3 × N` versus `1125.7 + 406.7 × N` milliseconds.
- GORM: `304.6 × N` versus `605.6 + 379.4 × N` milliseconds.

The per-case savings denominator is **negative** (−71.4 ms / −74.8 ms), so
neither measured workload has a finite crossover under this model. Actual
10/50/100 totals above are authoritative; pooled constant-cost estimates do not
model the observed process-lifetime effects exactly.

A heavier preparation would need to reverse that per-test difference before
one-time Snapshot cost can be amortized. This is not a universal 75 ms threshold:
a larger prepared database also changes Snapshot validation/copy/startup cost.
Measure a real workload before estimating its crossover.

The [integrated installed-Python/SQLAlchemy result](v04-integrated-candidate.md)
already shows 100-test Fork **20.430 s** versus Start **34.025 s**. That result
remains evidence for prepared-state value under its installed host process,
SQLAlchemy preparation and lifecycle boundary. It must not be numerically
mixed with this direct-Go, two-model, same-process suite. This lane neither
invalidates that result nor establishes that Fork is unnecessary generally.

For these current Go preparations, making Fork faster is not a prerequisite to
using disposable isolation: Fresh is cheaper and passes the same isolation
checks. A broad Fork/storage project is not justified by these workloads alone.
The next product experiment should use an actual consumer's costly migrations
and fixture setup, with preparation and cleanup ownership held equivalent.
Do not optimize Fork or manufacture a heavy fixture in this lane.

## Evidence, reproducibility and scope

- Harness and boundary instructions: [fixturecrossover](fixturecrossover/README.md).
- Portable summary, phase distributions and hashes of all raw suite files:
  [v041-fixture-crossover.json](v041-fixture-crossover.json).
- All 1,920 individual samples, including tails:
  [v041-fixture-crossover.csv](v041-fixture-crossover.csv), SHA-256
  `2461be4bb9888cf17b09358f7f0e9e2857695dc9d384ce27ed9d211b9a71d19d`.
- Large diagnostic binary and full per-suite JSON remain in the ignored external
  `fanout-v041/crossover-raw` work area; no platform image, build tree or runtime
  artifact is committed. The tracked summary records each raw filename/hash.
- All 1,920 measured cases and four warmups pass fixture verification, COMMIT,
  ROLLBACK, next-child pristine data and normal disconnect/Close. All temporary
  Snapshots are removed. No correctness failure or deadline occurs.
- Production runtime/API, guest source/provenance, Snapshot format and defaults
  are unchanged. No normal-path optimization, integration or release is made.
- Python harness syntax, summary/sample count and recorded harness identity
  consistency pass. The public-source check passes on a staged publication
  tree (596 files), and `git diff --check` passes. Staging omits the worktree's
  `.git` pointer file, which the existing checker does not accept as a public
  root file; no checker or production behavior is modified.

## Verdict

This verdict applies to the two measured **Go preparation workloads**. Heavy
setup and the previously demonstrated Python prepared-state value remain
separate product questions; they are not ruled out by this experiment.

`FRESH START IS SUFFICIENT FOR CURRENT WORKLOADS`
