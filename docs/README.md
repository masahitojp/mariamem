# Documentation

For installation, start with the [repository README](../README.md#installation).
[Project status](project-status.md) records the published release, approved
contracts and remaining direction. [Release notes](../release/NOTES-v0.6.2.md)
describe 0.6.2; [unreleased staging](release-notes/unreleased.md) contains only
changes not yet published.

## User guides

| Task | Guide |
| --- | --- |
| Python fixtures, preparation, manual Forks and failures | [Python](python.md) |
| Go pools, fixtures, Forks and opt-in Pipe | [Go](go.md), [prepared helper](go-prepared-fixture.md) |
| Route existing Python application connections | [Scoped routing](connection-routing.md) |
| Prepare migrations/seed or import a bounded dump | [Preparation](preparing-test-data.md), [dump reader](importing-dump.md) |
| Ordinary Django rollback/flush testing | [Standard runner](django-testing.md), [example](examples/django/README.md) |
| Prepared Django classes and local xdist | [Prepared Django](django-prepared.md#configure-worker-count) |
| Sequential browser/HTTP tests | [Live](live.md), [owned entries](examples/e2e_owned/README.md), [manual examples](examples/live/README.md) |
| Connect Node ORMs | [TypeORM / MikroORM](node-orm.md) |
| Understand protocol and toolchain limits | [MySQL protocol](mysql-protocol.md), [Go compatibility](go-compatibility.md) |
| Migrate old Snapshot save/load usage | [Changes from 0.5.0](changes-since-v050.md), [0.5.2 ownership update](changes-since-v051.md) |

## Maintainer guides

- [Architecture](v04-generated-go-architecture.md) and [Snapshot contract](decisions/snapshot-product-contract.md)
- [Startup, Snapshot and Fork lifecycle (日本語)](internals/startup-lifecycle.md) — processing stages, reuse and measurement boundaries
- [Development and proportional verification](development.md)
- [Release preparation and CI handoff](releasing.md)
- [Disposable experiment workspaces](experiment-workspace.md)
- [Artifact licenses](v04-license-inventory.md)

## Historical material

`reviews/`, versioned readiness/acceptance reports, old Wasmer/native-bundle
instructions and benchmark reports preserve their original source, result and
approval boundaries. Their FAIL, SKIP, pending work and old commands describe
those checkpoints, not current installation or release requirements. Use their
pinned source when reproducing an old observation. Current instructions are
listed above; Wasmer and native-bundle startup have no supported fallback path.

The old chronological status log and removed draft notes remain in Git history;
[project status](project-status.md#historical-decisions-and-evidence) links the
fixed pre-cleanup source. Published notes and raw evidence are retained.
