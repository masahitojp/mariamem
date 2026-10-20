# Disposable databases and fixed baselines

Status: maintainer-approved product contract, updated for D block storage and
Python shared-host main adoption on 2026-10-17. Release approval remains separate.
The ownership update below was approved for productization on 2026-10-17 and
subsequently adopted on main at candidate `52c078b`, then published in
[v0.5.2](../../release/NOTES-v0.5.2.md). The current published v0.5.3 retains that
ownership contract. Historical v0.5.1 has the earlier D/shared-host implementation;
v0.5.0 retains the
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

A successful ordinary heap Snapshot fixes the source's content after guest workers
have stopped, seals that same backing, and prevents subsequent changes through
normal APIs. Capture is bound to the source before execution. Acquisition checks
the source/guest identity, completed capture, inventory, layout and seal state;
it does not reconstruct or rescan the file contents. Fork creates independent
metadata and copies inherited blocks before writing. Parent and sibling content
remains unchanged; children retain their own lifetime after baseline Close.

The heap ownership path does not promise post hoc detection, by a full content
scan, of faults that directly alter private process-memory bytes. This detection
boundary was explicitly accepted for productization; it is not a relaxation of
normal API isolation or permission to treat a failed strict oracle as success.
The development review retains the difference from the earlier acquire-time
content-hash check. Private memory faults are not a public user operation.

An explicit different development host binary may use a private temporary
handoff. This serialization/copy boundary still independently verifies expected
inventory, content hashes and guest identity before ownership. A borrowed file
mapping is materialized into owned heap blocks before it can escape its source
instance, with source/target content validation. Strict digest-bearing Heap
imports retain their checks and detach mutable producer aliases. No public
external import or user-managed baseline artifact is introduced.

Reducing rereads follows from the same sealed resource and its lifetime, not a
path name, timestamp or cached boolean. Fork does not rescan every byte or promise
detection of later arbitrary corruption. This is not an adversarial same-user
security boundary.

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

The Human approved the ownership boundary above and the minimal FileStore/Root/
capture-binding implementation, adapters and ownership oracles on 2026-10-17.
See [productization status](../reviews/snapshot-owned-root-productization.md).
The Human subsequently approved main adoption of fixed candidate `52c078b`.
See [current adoption status](../project-status.md#adopted-ownership-optimization--unreleased).
Neither approval authorizes a release.

## Approved routine candidate boundary — not yet adopted

On 2026-10-20 the Human approved the minimum-routine implementation scope and
its product-managed `mysql.proc` structure boundary. In that candidate, Fresh
creates the pinned structure before ready; a restored baseline with missing or
incompatible structure is rejected at Fork startup, without automatic repair.
Creating/dropping user routines changes rows and remains supported per-child
state; parent/sibling isolation is unchanged. This approval does not make the
candidate part of current main/published behavior or choose its version. Main
integration, Qualification and release remain separate. See the
[routine bootstrap design](../reviews/v06x-routine-bootstrap-design.md) and
[implementation evidence](../reviews/v06x-routine-bootstrap-implementation.md).
