# mariamem v0.4.4

Prepare expensive migrations/fixtures once, then give each test an independent
real MariaDB and discard it afterward. Tests may use normal connections and
commit/rollback; what is shared is the initial baseline, not earlier mutations.

- Snapshots validate their initial state completely and own the state used by
  subsequent Forks. Fork no longer hashes every prepared file on each startup.
- Python `db.snapshot()` fixes a temporary baseline; `db.snapshot_to(path)` fixes
  and persists one at creation time. Replace the previous `snapshot(path)` form
  with `snapshot_to(path)`.
- Python `mariamem.load_snapshot(path)` acquires a saved baseline without starting
  a DB. Later edits/deletion of the source path do not affect the loaded baseline.
- Remove `mariamem_class_fork` / `mariamem_class_connection_info`; use per-test
  `mariamem_fork` / `mariamem_connection_info` with a reusable session baseline.
- Remove public Snapshot path/manifest/validate hooks. `start(snapshot=baseline)`,
  constructors and lower-level acquisition entrances remain available.
- User documentation now explains the test lifecycle separately from architecture
  and historical investigations.

Successful snapshot creation ends the source DB. Child writes, schema changes,
growth and commits cannot change the parent or siblings. Snapshotting a modified
child creates a new baseline. Close each DB and baseline when finished.

Persisted baselines are advanced derived artifacts: users manage reproducible
inputs, freshness, regeneration and deletion. There is no automatic cache manager
or new run-wide pytest fixture. Persistence is selected at creation; Snapshot
has no later save/persist operation.

Validation is performed at creation/loading. mariamem does not guarantee detection
on every Fork of silent media corruption arising after ownership. See the
[contract](../docs/decisions/snapshot-product-contract.md) and
[current limitations](../docs/project-status.md#supported-scope-and-limitations).

The MariaDB guest and supported platforms are unchanged: macOS 15+ arm64 and
Ubuntu 24.04 x86_64. Both-platform runtime qualification is recorded at exact
source `c5f43106a8054bb59a2da9184a1c2103fe1a1d9f`; the final release independently
checks its artifacts, source, licenses, provenance and installed consumers.
No spike performance result is presented as a final-release benchmark promise.
