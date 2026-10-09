# mariamem project status

This document owns current state and future direction. The
[user guides](../README.md) own usage, [architecture](v04-generated-go-architecture.md)
owns current HOW, [decisions](decisions/snapshot-product-contract.md) own
continuing product constraints, and reports preserve historical evidence.
Version themes are direction; they are not release approval.

## Product contract

mariamem provides disposable real MariaDB databases for tests. Each test normally
owns one mutable DB, uses normal connections and commits/rollbacks, then discards
the DB. Expensive migrations/fixtures may be prepared once and reused as a fixed
Snapshot baseline. What is shared is the initial state, not previous tests'
mutations. Fork creates an independent mutable DB; a modified child can create
a new baseline without changing its parent.

Normal user entry points are acquisition functions and test-per-database fixtures.
Successful Snapshot consumes its source; rejected busy/transaction preconditions
preserve it. Close boundaries remain explicit.

Persisted baselines are advanced derived artifacts. mariamem does not manage
cache freshness, regeneration or deletion. Diagnostics do not define the normal
Snapshot lifecycle. These are product choices independent of reference-project
APIs. See the [adopted contract](decisions/snapshot-product-contract.md).

## Published baseline: v0.4.4

[v0.4.4](https://github.com/masahitojp/mariamem/releases/tag/v0.4.4) is released
from source `8ede4ad65def07436b64801076004ff80aec0799`; annotated tag object
`0a22ba1e02957b7bfd616836c65b72040698c617`. The
[release run](https://github.com/masahitojp/mariamem/actions/runs/37924209669)
passed final-artifact qualification, publication and both-platform public smoke.
Its runtime basis is `c5f43106a8054bb59a2da9184a1c2103fe1a1d9f`, qualified on
both platforms by [Product CI](https://github.com/masahitojp/mariamem/actions/runs/37898847164).
Final source and tested runtime source are intentionally distinct identities.

Creation/import validates the complete Snapshot, then mariamem owns the exact
backing used by Fork. Supported operations do not mutate it. Fork does not fully
rehash content; silent storage corruption arising after ownership is not promised
to be re-detected on each Fork. External source edits/deletion after import do
not affect the owned baseline. Live Snapshots retain one FD per prepared file.
Python uses `snapshot()`, `snapshot_to(path)`, `load_snapshot(path)` and `fork()`.
See the [contract](decisions/snapshot-product-contract.md),
[implementation review](reviews/v044-implementation-review.md),
[architecture](v04-generated-go-architecture.md) and
[release notes](../release/NOTES-v0.4.4.md).

Generated-Go is the only supported production runtime since v0.4.3. Snapshot is
cold prepared state; Fork starts fresh MariaDB execution rather than cloning
running heap/threads/TLS/locks/stacks. Private file mappings use OS page CoW;
there is no custom CoW filesystem or Unix fork. Historical measurements and
release repairs remain evidence, not instructions for the current user lifecycle.
See [v0.4.3 characterization](../benchmarks/v043-characterization.md) and the
[v0.4.4 review reports](reviews/v044-release-runtime-reuse-design.md).

## v0.4.5 — Infrastructure stabilization and measurement, in progress

The [infrastructure audit](https://github.com/masahitojp/mariamem/blob/d7b1c0f60591843b0e72327fba7c62d26b7a3ee4/docs/reviews/development-infrastructure-audit.md)
and [bounded plan](reviews/v045-stabilization-plan.md) own the work sequence.
Restore wire coverage, detach ordinary development from expiring Product receipts,
extract live helpers before retiring historical infrastructure, and establish
clear runtime/artifact/measurement responsibilities. Release qualification remains
fail-closed. Source reproducibility and handwritten inclusion remain required.

Snapshot latency, suite crossover and bounded product measurements follow stable
verification infrastructure; no performance optimization is approved in advance.
No guest upgrade or new product feature is included. A reusable runtime-evidence
model or reduction of required checks needs a focused Human Review first.

## Supported scope and limitations

- macOS 15+ arm64 and Ubuntu 24.04 x86_64. Canonical acceptance uses Go 1.26.8
  and Python 3.14; minimum package versions do not imply a broad tested matrix.
- Full generated guest is not Go race-detector clean. Preserve the
  [race census](../benchmarks/direct-link-race-scope.md); focused handwritten
  checks do not prove general race correctness.
- Forced timeout/hard-failure containment is not guaranteed. Normal cooperative
  cleanup and non-cooperative reclaim are distinct boundaries.
- Approximately one-second startup tails remain observable; do not suppress
  them or infer their cause from earlier individual traces.
- Go 1.27.0/1.27.1 arm64 are unsupported due to upstream compiler issue #81036.
- Physical footprint, RSS and reachable heap are different resource measures.
  The v0.4.2 lifecycle releases linear memory after joined workers; filesystem
  metadata remains GC-managed.
- Live Snapshots retain roughly one FD per prepared file. The 64-table fixture
  had 137 files and released its backing FDs after Close on both platforms.
  Many simultaneously retained baselines, especially file-heavy schemas, may
  approach process FD limits. Gather real workload evidence and improve the
  resource model if pressure is demonstrated; this is accepted and non-blocking
  for v0.4.4, not a reason by itself to create v0.4.5.
- The 0.x API may change. Corresponding guest source, licenses, notices and
  reproducible generation remain required.

## v0.5.0 — Stable guest

Select and migrate to a deliberate stable/LTS MariaDB release, refreshing
compatible guest/WASIX/toolchain inputs with reproducible generation.
No target version is selected here. Rerun SQL/protocol/auth/sessions/lifecycle,
Snapshot/Fork/isolation and consumer compatibility. Repeat the full shared-memory
race census on changed inputs; a guest upgrade is not assumed to fix it.
Measure a new performance/resource baseline.

## v0.6.0 — Dogfood and fixture ergonomics

Use real consumer/workload evidence, including Django, Alembic/migrations,
metadata-heavy and dbt-like workloads. Retain SQLAlchemy/GORM regression anchors.
Evaluate actual preparation, per-test isolation, resource and failure costs.

New run-wide baseline fixture ergonomics are deferred here. Existing session
fixtures remain worker-local under xdist. Do not promise new framework/platform
compatibility or introduce automatic cache policy before use-case evidence.

## Development discipline

Keep **Explore → Challenge → Human decision → Implement → Verify**.
Verification scope follows the changed boundary; explain a concrete dependency
before broadening. See [development](development.md#local-verification).

Experiments are disposable by default. Preserve compact measurements, reports,
hashes and reproduction inputs rather than recreatable caches, completed
worktrees/builds or source copies. Completion includes cleanup and a retained-path
audit. See the [workspace policy](experiment-workspace.md).

CI owns exact-source build, acceptance and release qualification after handoff;
a submitted verification run does not publish or approve a release.
See [release workflow](releasing.md).
