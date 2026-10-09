# mariamem v0.4.4 — UNRELEASED candidate

Product contract cleanup: disposable per-test databases, fixed prepared
baselines, and consistent acquisition/ownership semantics.

## Candidate changes

- Validate Snapshot creation/import completely, then own the exact backing used
  by Fork. Fork reuses that resource without content rehashing each time.
- Add Python `mariamem.load_snapshot(path)` to acquire a persisted baseline
  without starting a database.
- Keep `snapshot()` temporary-only and add `snapshot_to(path)` for creation-time
  persistence. Replace old `snapshot(path)` calls with `snapshot_to(path)`; the old
  positional/path-write form has no deprecated alias. Keep `fork()` and
  `start(snapshot=...)`.
  Constructors and existing lower-level open entrances remain available.
- Remove `mariamem_class_fork` and `mariamem_class_connection_info`. Replace
  them with function-scoped `mariamem_fork`/`mariamem_connection_info`;
  expensive baseline preparation can still be session-scoped.
- Remove public Go `Snapshot.Path()` and Python Snapshot `path`, `manifest`,
  `validate()`. Callers choose explicit persistence destinations when needed;
  acquisition performs required validation.
- Separate user contract, current architecture, continuing decisions and
  historical evidence in documentation.

## Integrity and lifecycle migration

Successful Snapshot ends its source DB. A child starts from fixed schema/data;
its commits, schema changes and growth cannot update siblings or the parent.
Snapshotting a modified child creates a new baseline.

Temporary capture storage is implementation-owned. Explicit output remains
after Snapshot Close. Loaded Snapshots own an independent template; later edits
or deletion of the original saved path do not affect them. Closing the imported
handle does not delete that source artifact.

After complete acquisition validation, silent damage arising in owned storage
is not guaranteed to be re-detected on every Fork. Cheap structural/lifetime/
guest checks remain. This is not an adversarial same-user security guarantee.

Persisted baselines are derived artifacts. The user remains responsible for
reproducible inputs, cache freshness, regeneration, coordination and deletion.
There is no automatic cache manager or new run-wide/shared pytest fixture.

## Qualification status

Production correctness, macOS arm64 / Ubuntu x86_64 acceptance, resource scaling
and benchmarks are separate qualification gates. Prior spike measurements are
not this candidate's release results. No performance promise or release
approval is made by these notes.

The MariaDB guest is unchanged. Guest race redesign, new diagnostics APIs,
Snapshot/Fork renaming and a full class redesign are outside this release.
See the [product decision](../docs/decisions/snapshot-product-contract.md) and
[project status](../docs/project-status.md).
