# Disposable databases and fixed baselines

Status: maintainer-approved product contract, updated for D block storage and
Python shared-host main adoption on 2026-10-17. Release approval remains separate.
This contract describes adopted main. Published v0.5.0 retains the earlier
file-backed/save-load contract; see [version differences](../changes-since-v050.md).

## Product boundary

mariamem provides disposable real MariaDB databases for tests. Each test normally
owns one mutable DB; application connections can commit/rollback normally.
Disposal is the isolation boundary. It is not an automatic test-transaction
wrapper and not a persistent database service.

Expensive migrations/fixtures may be prepared once and shared as a fixed
Snapshot baseline. Fork creates independent mutable DBs from it. Child writes
never change the parent or siblings. A modified child can create a new baseline.

Snapshot/Fork names are retained because they describe fixing a state and
creating independent DBs from it. They do not promise Unix process-fork or
running-runtime cloning semantics.

## Lifecycle and persistence

Successful Snapshot creation ends the source DB. Precondition rejection keeps it
available. Closing the baseline prevents new Forks; successfully started
children own their lifetimes and remain usable until separately closed.

`snapshot()` fixes the current DB state in a process-local immutable baseline.
The maintainer approved removing persistence and loading during the D/shared-host
implementation on 2026-10-16. Path-taking capture such as `db.snapshot(path)` is not supported. Python
`snapshot_to`, `load_snapshot`,
`Snapshot.open(path)` and path-based acquisition, and Go `Destination` /
`LoadSnapshot`, are removed from the adopted implementation. Prepare from migration/seed inputs
again for each test process/session. No automatic cache is introduced.

Python automatically manages one host per independent root start lineage. DBs,
baselines and descendants in that lineage retain it. A host crash loses that
lineage; a normal SQL error or child Close does not close siblings. Every child
still owns an independent MariaDB runtime and endpoint. Root starts and xdist
workers do not share a process. Go uses its caller's process as before.

## Integrity follows ownership

Acquisition completely verifies prepared inventory, content and guest identity.
mariamem owns the exact verified backing; supported operations never mutate it.
Fork uses that same resource with cheap structural/lifetime/compatibility checks,
without recomputing full content hashes.

No public external import remains. An explicit different development host binary
may use a private temporary handoff; that boundary still independently copies and
verifies expected inventory/hashes and guest identity before ownership. It does
not expose a user-managed baseline artifact.

The contract explicitly does not promise detection on every Fork of silent
media corruption arising after acquisition. It is not an adversarial same-user
security boundary. Reducing repeated verification is supported by exact resource
ownership, not a path name, timestamp or cached boolean.

## pytest boundary

Baseline preparation may be session-scoped; mutable child state is
function-scoped. Built-in class fixtures that carry mutations between tests are
removed. Test classes remain useful organization and may use the function
fixtures. Deliberate custom sharing is not prohibited by the Python language,
but is outside the default isolation contract.

No new run-wide/shared fixture is added. Each xdist worker owns its session
fixtures. Fixture ergonomics are deferred to v0.6.0 dogfood evidence.

## Consequences

Ordinary baselines retain immutable Go blocks, not one backing FD per file.
Each child separates modified blocks. Closing a baseline does not revoke blocks
already owned by children. Removing the earlier file-backed public save/load API is an
intentional API removal; the earlier reports preserve that historical contract.
The maintainer accepted main adoption after bounded validation on both native
platforms. Final release validation and release approval remain separate.
See the [adoption decision and evidence](../reviews/d-heap-shared-host.md).
