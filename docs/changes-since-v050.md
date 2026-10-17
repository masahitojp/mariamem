# v0.5.1 changes since v0.5.0

Updated 2026-10-17. [v0.5.0](https://github.com/masahitojp/mariamem/releases/tag/v0.5.0)
was published on 2026-10-13 from source
`44100ec676c8c9064f32f3a01bd9a990d487bb61`; annotated tag object
`bfd854da1cecbe71ad761d1578b3f2c710a1c07f`.
The changes below shipped in [v0.5.1](https://github.com/masahitojp/mariamem/releases/tag/v0.5.1)
on 2026-10-17 JST from source `7a82f338cf111d5d52538b5a3f7bf129c12e2dbb`;
annotated tag object `089b32e09608902f6d46e7ab9527d09922dcf065`.
They are not in v0.5.0's Go module or Python wheels. Release CI completed
publication and both native public smokes in
[run 38959312232](https://github.com/masahitojp/mariamem/actions/runs/38959312232).
The earlier qualified/measured source and final released source remain separate identities.

## Behavior and API differences

| Area | Published v0.5.0 | v0.5.1 source |
| --- | --- | --- |
| MariaDB | 12.3.3 | 12.3.3; includes the page-cleaner startup ordering correction |
| Snapshot backing | Verified file-backed prepared state | Verified immutable 16 KiB blocks in Go memory; child changes are private |
| Python host ownership | Separate child hosts, with acquired baseline backing retained by Python | One automatically managed host per independent root lineage, retaining its baselines and DBs |
| Reuse | During a test run and through explicit saved artifacts | Process/session-local baseline reuse; prepare again in another process/run |
| Isolation and lifecycle | Independent MariaDB children; successful Snapshot consumes the source | Retained; normal connections, commit/rollback, independent child lifetimes and derived baselines |
| Connection capacity | 16 per DB | 16 per DB; sharing a host does not make this a lineage-wide pool |

The removed public interfaces are:

| Language | Removed in v0.5.1 | Migration |
| --- | --- | --- |
| Python | `db.snapshot_to(path)` | Use `db.snapshot()` to create a live in-memory baseline |
| Python | `mariamem.load_snapshot(path)`, `Snapshot.open(path)`, direct saved-Snapshot construction | Run migrations/seed in a setup DB, then call `snapshot()` |
| Python | Path passed as `snapshot=` to `mariamem.start` / `Database` | Pass a live baseline handle, or call `baseline.fork()` |
| Go | `SnapshotOptions.Destination` | Use `SnapshotOptions{}` or keep only `Rollback` |
| Go | `LoadSnapshot(ctx, path, opts)` | Prepare with `Start`, SQL migrations/seed and `Snapshot`, then `Fork` |

Python capture accepts keyword-only `rollback` and `timeout`; it accepts no
destination argument. Positional `db.snapshot(path)` was already unsupported in
published v0.5.0 and remains rejected; it is not a newly removed v0.5.0 API.
Go `SnapshotOptions` contains only `Rollback`.
Existing saved artifacts cannot be loaded by v0.5.1, even if their guest identity
matches. Retain migration/seed inputs to recreate preparation for every test
process/session. There is no automatic cache or replacement public persistence API.

The normal flow stays: start a setup DB → migrate/seed → close SQL clients and
wait for disconnect cleanup → Snapshot → Fork each test's independent DB → Close.
Prepare once per pytest worker/session and reuse its live baseline. Closing a
baseline prevents new Forks; successfully started children remain usable.
Busy/transaction precondition rejection preserves the source. Failure after
capture acceptance can consume it; inspect `HostError.closed` / `HostError.Closed`.
See the current [Python](python.md) and [Go](go.md) guides for examples.

## Shared-host lifetime

A Python root `start()`, its baseline, children and derived baselines retain one
automatically managed host. Each DB still has an independent MariaDB runtime,
SQL endpoint and private changes. Normal SQL errors and a child's Close do not
close siblings. A host process crash loses all DBs/baselines in that lineage,
so recreate preparation. Independent root starts and xdist workers use separate
hosts. Go continues to run inside its caller's process.

The host is reaped after the last owner and admitted operation finish. The
ordinary Snapshot/Fork path does not materialize payload into temporary files.
Logs, control directories/sockets and linear-memory mappings still exist.
An explicit different development host binary may use a verified private
temporary handoff; it is not a user-managed save/load interface.

## Adoption and validation status

The [startup correction](reviews/v050-startup-tail-source-fix-integration.md)
and [D/shared-host implementation](reviews/d-heap-shared-host.md) are adopted
on main. Both supported native platforms passed their relevant bounded checks.
The D/shared-host runtime input, independently regenerated provenance, failure
oracles and installed-consumer evidence are recorded in the implementation report.

Final Qualification passed for combined source
`c97e55fc065f6ee7b560325077726da53e5d95d7` in
[verify run 38935990860](https://github.com/masahitojp/mariamem/actions/runs/38935990860);
both native platforms and the aggregate guard returned READY. The
[Qualification review](reviews/main-storage-qualification.md) retains exact
receipts and explicit SKIPs. The later bounded macOS
[Product Verification](../benchmarks/main-product-verification.md) completed 274
executions; its [Human Review](reviews/main-product-verification.md) was accepted
for v0.5.1. The earlier slow resource-observed small case did not recur in the
bounded repeats; its cause is not established. The adverse 100 MiB Go Fresh
observation is an explicitly approved post-release investigation. Ubuntu
performance remains unmeasured. Existing general race-detector and
non-cooperative cleanup limits remain. The release workflow must accept the
exact final-version source/artifacts; later commits do not inherit exact-SHA
READY by relabelling earlier evidence.
