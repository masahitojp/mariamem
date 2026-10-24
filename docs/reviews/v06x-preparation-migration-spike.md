# Preparation migration spike — execution record

2026-10-24. Branch: `experiment/preparation-migrations`, based on design
`93c201756879f51bb30c92945f2e3bb509e3c16e` and adopted main
`22c647d39c94d1e912699613c70d762732c01598`.
The Human authorized the [bounded preparation check](v06x-preparation-import-design.md).
This is experiment-only fixture/tooling, not a product importer or API extension.

## Fixed input and scope

The input is a repository-authored, small Alembic project. It is not an external
production application, and success cannot establish compatibility of arbitrary
existing Alembic/Django environments. Alembic1.18.4 is reused from prior source
research; SQLAlchemy2.0.54/PyMySQL1.2.3 match the adopted consumer pins. Fixed
transitive development tools and pip archive identities are retained separately.
Go1.26.10 builds the unchanged runtime; the guest/converter/generated owners
are unchanged. No independent guest regeneration is needed or claimed here.

The two dependent revisions, explicit seed, final schema/data checks and ordinary
application tests exercise preparation -> disconnect -> Snapshot -> independent
children through the adopted plugin. A controlled local original-endpoint
listener must receive no connections. Preparation intentionally refuses the
original profile; it uses explicit source DB settings. Experiment-only snapshot
observation records attempted/successful capture; private host process/directory
state is read only for cleanup diagnostics.

Success and later-revision/seed failures are separate pytest processes. Negative
cases require the exact SQL oracle, preserved ProgrammingError/1146 and stage;
wrong errors, skipped cases, started tests/Snapshots, live hosts and original
contacts must fail the campaign. The13 classifier unit cases pass; native
results remain pending until the actual run below.

## Results

Native execution is pending. No migration/import PASS, Human adoption,
performance result, Qualification or release readiness is claimed.

[Fixture and reproduction](../../tests/preparation_migration_spike/reproduce.md)
contains exact commands and a copyable explicit-URL integration shape. The
runner saves source/tool/guest/host hashes, pytest JSON events/JUnit/logs and
partial-source state after deliberate failures. Copying the source fixture is
not a broad application/dump support promise.
