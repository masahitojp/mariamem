# mariamem v0.5.1 — In-memory baselines and shared Python host

This release reduces the cost of preparing a real MariaDB database once and
reusing it across independent tests. MariaDB remains 12.3.3, with the existing
generated-Go runtime and supported Go/Python platforms.

## Highlights

- Snapshot retains verified immutable 16 KiB blocks in Go memory. Fork shares
  the initial state and keeps each child's changes private. The ordinary path
  no longer materializes Snapshot payload into temporary files.
- Python automatically manages one Go host per root lineage, holding the root,
  its baselines, children and derived baselines. Independent root starts and
  pytest-xdist workers use separate hosts.
- The page-cleaner startup ordering correction removes the identified wait
  responsible for the previous approximately one-second startup mode.

## API migration

**Public Snapshot persistence/loading is removed.** Prepare migrations and seed
once per test process/session, call `snapshot()`, then reuse `baseline.fork()`.
Saved artifacts from older releases cannot be loaded, even with a matching
guest identity. Keep migration/seed inputs to recreate the baseline.

Python removes `snapshot_to(path)`, `load_snapshot(path)`, `Snapshot.open(path)`,
saved-Snapshot construction and path-based `snapshot=` acquisition. Go removes
`SnapshotOptions.Destination` and `LoadSnapshot`; `SnapshotOptions` retains
`Rollback`. Python capture remains keyword-only `rollback` and `timeout`;
positional `snapshot(path)` was already unsupported in v0.5.0.
See the [migration guide](../docs/changes-since-v050.md) for replacements.

Successful Snapshot still consumes its source. Each Fork has its own MariaDB
runtime, SQL endpoint and mutable state. Normal SQL errors and child Close do
not close siblings. A Python host crash loses all DBs and baselines in its root
lineage; recreate preparation in that case. Per-DB connection capacity remains 16.

## Measured benefits and retained tradeoff

The bounded macOS arm64 comparison against v0.5.0 completed 274 executions with
the existing SQL, transaction, isolation and cleanup oracles. Four-test
Light/10 MiB Fork suites improved by approximately 13–36%. The Python workflow
from preparation through Snapshot, multiple children and all Close calls
improved by 27.3% for the small fixture, 7.9% for medium and 2.9% for 100 MiB
with sixteen children. Snapshot itself took approximately half the time.
Go 10 MiB Fork process RSS median fell from 664 to 177 MiB, and cumulative
allocation from 670 to 117 MiB; allocation is not simultaneous retained memory.

These are scoped observations, not universal speed guarantees. The adverse
100 MiB Go Fresh case was 7.2% slower across the original and three added
observations; the first trial was 29.0% slower. The maintainer accepted this
tradeoff and scheduled investigation after this release. Ubuntu performance
was not measured. See the [complete results](../benchmarks/main-product-verification.md)
and [Human decision](../docs/reviews/main-product-verification.md).

## Verification and distribution

The unchanged runtime basis passed [both-native Qualification](../docs/reviews/main-storage-qualification.md).
The earlier tested/measured source is recorded separately from this final-version
source; Release CI builds and accepts the exact final-version artifacts, checks
source/licenses/provenance, and owns publication and public smoke.

Support remains macOS 15+ arm64 and Ubuntu 24.04 x86_64. Minimums remain Go1.26.0
and Python3.9; canonical release checks use Go1.26.8 and Python3.14.
Python distribution remains host-only GitHub Release wheels; this release does
not publish to PyPI. The ordinary Go module requires no guest executable or
separate runtime download. GPL corresponding source, notices and checksums remain
part of the release. Existing non-cooperative-worker cleanup and full-guest
race-detector observation limits are unchanged.
