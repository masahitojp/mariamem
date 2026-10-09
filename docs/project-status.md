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

## Published baseline: v0.4.3

[v0.4.3](https://github.com/masahitojp/mariamem/releases/tag/v0.4.3) is released
from commit `c8bd25a56e9d5221abaf40b2c98102bd60c217ae`.
Its annotated tag object is `dd84ca4e9e0f2802766dd2f46d1c6ab24a41dc20`.
Generated-Go is the only supported production runtime; live Wasmer, bundle
resolution/provisioning and native executable packaging are retired.
Historical tags/reports retain that evidence, not a supported second runtime.

Snapshot captures cold prepared files and Fork starts fresh MariaDB execution.
No running heap/threads/TLS/locks/stacks are cloned. OS private file mappings
provide page-level CoW; no custom CoW filesystem or Unix fork is implemented.

The v0.4.3 characterization found per-Fork inventory/hash verification accounted
for roughly 53–62% of ready latency. The large COUNT cost was repeated scan work,
not an unexplained first-SQL penalty. Snapshot export and broad scans are distinct
costs. See [characterization](../benchmarks/v043-characterization.md),
[release baseline](../benchmarks/v043-release-baseline.md) and
[release notes](../release/NOTES-v0.4.3.md).
These historical measurements are not v0.4.4 performance results.

Earlier released milestones are retained as evidence:
[v0.4.0](../release/NOTES-v0.4.0.md) generated-Go integration,
[v0.4.1](../release/NOTES-v0.4.1.md) distribution cleanup, and
[v0.4.2](../release/NOTES-v0.4.2.md) disposable memory lifecycle.

## v0.4.4 — Accepted product contract, release preparation

The product audit and maintainer decisions are complete. Implementation aligns
ownership, language/pytest surfaces and documentation:

- Full validation at creation/import, followed by ownership of the exact backing
  used by Fork; no full content rehash on each Fork.
- Python `load_snapshot(path)` as normal persisted-baseline acquisition.
- Python `snapshot()` is temporary-only; `snapshot_to(path)` fixes and persists
  at creation time. The old `snapshot(path)` write form is removed. Go retains
  creation-time persistence through `SnapshotOptions.Destination`.
- Removal of mutable class-sharing fixtures and public Snapshot metadata hooks.
- User contract separated from architecture, continuing decisions and history.

The accepted integrity boundary excludes guaranteed detection on every Fork of
silent media corruption arising after ownership. Supported operations do not
mutate backing. External source edits/deletion after import cannot affect owned
Snapshots. The resource cost is approximately one read-only FD per prepared file
for the Snapshot lifetime.

The maintainer accepted this implementation, API cleanup and FD trade-off.
[Product CI](https://github.com/masahitojp/mariamem/actions/runs/37898847164)
passed correctness/lifecycle, installed pytest/xdist, resource scaling and
production performance on macOS arm64 and Ubuntu x86_64 for exact source
`c5f43106a8054bb59a2da9184a1c2103fe1a1d9f`. See the
[accepted runtime review](reviews/v044-implementation-review.md). Later
identity-tooling/docs changes do not acquire a new runtime test claim merely
by being integrated. Prior spike measurements remain feasibility evidence.

Release is authorized. The approved reuse route authenticates the unchanged
runtime against the exact Product CI source and both native artifacts. It records
the tested runtime basis separately from the final release source, while retaining
fresh final-version artifact/consumer/source/license guards. Invalid reuse intent
stops before build instead of repeating runtime qualification. Publication remains
pending one-shot Release CI. See the [reuse boundary](reviews/v044-release-runtime-reuse-design.md),
[tooling checks](reviews/v044-runtime-reuse-verification.md) and
[release notes](../release/NOTES-v0.4.4.md).

The first release run [37914496989](https://github.com/masahitojp/mariamem/actions/runs/37914496989)
stopped before publication at generated-source reproduction. Runtime evidence reuse
and both independent source-to-WASM builds passed. The regeneration copy list
omitted two already-tested handwritten OwnedPrepared files; the
[scoped tooling fix](reviews/v044-regeneration-fix.md) preserves runtime sources
and guards. The subsequent run
[37918195197](https://github.com/masahitojp/mariamem/actions/runs/37918195197)
passed full reproduction and offline source closure, then stopped before
publication on a stale `Snapshot.path` reference in SQLAlchemy Fork-mode fixture
setup on both platforms. The [consumer fixture repair](reviews/v044-sqlalchemy-fixture-fix.md)
preserves all SQL cases and requires fresh final-artifact ORM acceptance;
diagnosis does not automatically redispatch.

No automatic cache management, new shared fixture, naming change, diagnostics
API, guest upgrade or broad class redesign is included. A v0.4.5 theme should
emerge only from a coherent issue supported by validation, not be created in
advance.

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
