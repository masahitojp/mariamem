# mariamem project status

This document owns current release state, known limits and human-selected next
direction. User contracts belong in [Go](go.md) and [Python](python.md), current
implementation detail in [architecture](v04-generated-go-architecture.md), and
continuing rationale in [decisions](decisions/README.md). Experiments retain their
own source-specific reports. Keep Explore → Challenge → Human decision →
Implement → Verify; version themes alone do not approve implementation.

## Current product and release

mariamem provides a disposable real MariaDB for Go/Python tests. A test can use
its application's own connections and commit normally, then discard its database.
Expensive setup can be shared as a fixed Snapshot; Fork creates independent
mutable databases from that initial state. Successful Snapshot creation ends
the source DB. Clients, DBs and Snapshots have explicitly owned cleanup scopes.
The guest derives from shyim/lite4mariadb; corresponding source and notices remain
required. This is not a SQL/InnoDB emulation or a production database service.

[v0.4.3](https://github.com/masahitojp/mariamem/releases/tag/v0.4.3) is released.
Generated-Go is the only supported runtime. Go uses the module source; Python
uses a host-only platform wheel. Legacy Wasmer/native-bundle overrides are
rejected. The release did not change Snapshot ownership or per-Fork validation.
Current prepared-file mappings provide OS page-level CoW; no live runtime is
cloned and mariamem Fork is not Unix fork. See the
[current implementation summary](v04-generated-go-architecture.md#v043-consolidation-and-prepared-file-sharing).

Supported platforms are macOS 15+ arm64 and Ubuntu 24.04 x86_64. Canonical
acceptance uses Go 1.26.8/Python 3.14; package minimums are not a broad tested
matrix. GitHub Release wheels remain the Python installation path while PyPI
publication is unavailable. The 0.x API may change.

## Selected v0.4.4 direction

The human accepted Product Contract Audit Decisions 1, 2, 3, 5 and 6:

- Core uses: disposable SQL/transaction/application databases, with optional
  prepare-once/test-many reuse. Broader real HTTP/heavy migration workloads need
  evidence before compatibility claims.
- Required concepts: mutable disposable Database and immutable lifetime-bound
  initial state. Keep the names Snapshot and Fork. State source termination and
  the exact objects/lifetimes shared by fixtures.
- Integrity target: fully validate at creation/import, own that exact backing,
  never modify it through supported operations, and Fork without rehashing all
  content. Do not promise per-Fork detection of later silent media corruption.
- Productionize the smallest owned-backing candidate from current main; do not
  merge experiment history or treat its prior CI as qualification of new code.
- Separate current user contract, implementation, continuing decisions and
  historical evidence. Correct current navigation before rewriting history.

See [product decision](decisions/product-contract.md) and
[integrity decision / bounded implementation boundary](decisions/snapshot-integrity.md).
The existing [OwnedPrepared review](https://github.com/masahitojp/mariamem/blob/09443d4de999b833cddc2ca536d43f9120130c79/benchmarks/v044-owned-ci-review.md)
is supporting evidence, not merged production behavior.

Decision 4 public API migration remains under discussion. Its constructor,
introspection and class-fixture removals are not automatically approved by the
core/integrity decisions. Arbitrary path writes are the maintainer's removal
direction; explicit read/import remains acceptable. Do not claim those signatures
have changed in shipped v0.4.3. No release or v0.4.5 is selected by this document.

## Known limitations

- Full generated guest Go `-race` is not clean: **GENERAL SHARED-MEMORY MODEL
  WORK REQUIRED**. Focused handwritten/runtime races remain required; no
  suppression hides the conflicts. See the [race evidence](../benchmarks/direct-link-race-scope.md).
- Forced timeout/hard failure containment is not guaranteed. Non-cooperative
  in-process execution cannot currently be forcibly reclaimed. Ordinary SQL
  errors and idle disconnects remain usable; an interrupted active query
  invalidates its DB. See the language guides for recovery.
- Resource measurements are boundary-specific. v0.4.2 releases linear memory
  after cooperative worker join; filesystem/metadata heap remains GC-managed.
  Reachable heap, RSS and OS physical accounting are different measures.
- Go 1.27.0/1.27.1 arm64 are unsupported due to upstream compiler issue #81036;
  there is no local generated-source/compiler workaround.
- Approximately one-second startup tails remain observable; existing traces do
  not establish the cause of every slow run. No shortened timer suppresses them.
- Current guest session capacity is 16, not a permanent API/throughput guarantee.
  Server-side prepared statements are unsupported. Default test credentials do
  not promise production account/grant authentication coverage.
- Released v0.4.3 still spends roughly 53–62% of the characterized Fork-ready
  boundary on inventory/hash checks. The large COUNT cost is a recurring broad
  scan, not a hidden Fork initialization penalty. See
  [characterization](../benchmarks/v043-characterization.md) and
  [exact release measurements](../benchmarks/v043-release-baseline.md).

## Release history and evidence

| Released milestone | Responsibility | Evidence |
|---|---|---|
| v0.4.0 | Generated-Go creation/normal runtime | [Release notes](../release/NOTES-v0.4.0.md), [historical comparison](../benchmarks/v04-integrated-candidate.md) |
| v0.4.1 | Distribution cleanup | [Distribution report](https://github.com/masahitojp/mariamem/blob/022011d724b6114a842b0996ed358dbb2f2d4c95/benchmarks/v041-distribution-cleanup.md) |
| v0.4.2 | Disposable memory lifecycle | [Accepted candidate](https://github.com/masahitojp/mariamem/blob/dc939de87087cadf229f017c1a5942496aae45da/benchmarks/v042-production-candidate.md) |
| v0.4.3 | Wasmer retirement and characterization | [Retirement](../benchmarks/v043-retirement-current.md), [release notes](../release/NOTES-v0.4.3.md), [release baseline](../benchmarks/v043-release-baseline.md) |

Old readiness gates are completed evidence, not a second current roadmap.
Detailed prior status remains in [the pre-audit source](https://github.com/masahitojp/mariamem/blob/c8bd25a56e9d5221abaf40b2c98102bd60c217ae/docs/project-status.md).
Do not carry earlier allocator/timing observations across changed source inputs.

## Later roadmap

v0.5 aims to select a stable/LTS MariaDB lineage with reproducible guest/toolchain
inputs. No target version is selected and this task does not start the migration.
Requalify SQL/protocol/session/lifecycle/Snapshot/Fork and consumer behavior on
new inputs, and revisit guest races rather than assuming an upgrade fixes them.

Broader workload evidence, including Django, Alembic/migrations, metadata-heavy
clients and dbt-like workloads, remains later work. Stronger hard failure
containment, session capacity and platform expansion remain evidence-driven
options. Ready-heap/live-worker reentry is not selected; preserve the historical
[reentry](../benchmarks/reentry-feasibility.md) and
[prepared-files](../benchmarks/prepared-clone-feasibility.md) findings.

## Development and evidence discipline

Use [local verification](development.md#local-verification) for the changed
boundary; explain a concrete dependency before broadening it. Release acceptance
and canonical benchmarks are separate. Preserve source identities, compact
measurements/reports/checksums and reproduction commands. Experiment worktrees,
caches and recreatable build trees are disposable; completion includes cleanup
and retention verification. See [workspace policy](experiment-workspace.md).
