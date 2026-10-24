# Preparation migration spike — bounded check complete

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
contacts must fail the campaign. The13 classifier unit cases pass. Native macOS results are recorded below;
Ubuntu and hosted macOS confirmation passed inCI40072694488 at84c8ee1.
The [Human Review](v06x-preparation-migration-human-review.md) distinguishes
this completed bounded check from recipe productization and main adoption.

## Results — local macOS arm64

Source_commit `4c6c3174debca83e359e82516864bf3ca54dff29`, Python3.14.9,
Alembic1.18.4, SQLAlchemy2.0.54 and PyMySQL1.2.3. Exact host/guest/tool/input
identity and outcomes are in the
[result receipt](v06x-preparation-migration-spike-evidence/macos-local/results.json).
[Stored/original hashes](v06x-preparation-migration-spike-evidence/macos-local/files.json)
explain path/whitespace normalization; nested receipt hashes refer to raw bytes.

| Check | Result and evidence |
| --- | --- |
| Ordered migration + seed | PASS: m2_addresses recorded; m1's legacy row retained with rating default0; seed row/address present; final columns, unique and foreign key verified |
| Snapshot -> two application tests | PASS: two tests used different child IDs; first committed a new row, second saw only prepared rows and retained foreign-key enforcement |
| Later-revision failure | PASS oracle: migration stage, exact missing_revision_oracle statement, original ProgrammingError/1146; no Snapshot attempt or test admission |
| Seed failure | PASS oracle: seed stage, distinct missing_seed_oracle statement and same original error class/errno; no Snapshot/test admission |
| Lifetime and original endpoint | PASS: one preparation per process, all3 source hosts reaped/directories removed, zero controlled original-endpoint contacts |
| Receipt classifier |13 PASS, including wrong statement/stage/errno/exit, unexpected Snapshot/test, host leak and contact rejection |
| Ubuntu / hosted macOS | Subsequently passed inCI40072694488; recorded separately below |

The observed partial state matters: after revision2 failed, `users.rating`
already existed while `alembic_version` still said m1_initial; addresses did not
exist. After seed failed, the schema/revision2 remained. This is not a migration
atomicity guarantee. No Snapshot was created from either failed source, and its
host was closed. No production helper retry/rollback policy is added.

## Hosted CI — both OSes passed

[CI40072694488](https://github.com/masahitojp/mariamem/actions/runs/40072694488)
passed at exact source_commit `84c8ee16e09ad63475f7185f04292e4624761a7c`.
[Assessment/job identities](v06x-preparation-migration-spike-evidence/ci-40072694488/assessment.json),
[artifact IDs/digests](v06x-preparation-migration-spike-evidence/ci-40072694488/artifacts.json),
[macOS receipt](v06x-preparation-migration-spike-evidence/ci-40072694488/macos/results.json)
and [Ubuntu receipt](v06x-preparation-migration-spike-evidence/ci-40072694488/ubuntu/results.json)
are saved. Source/SDK/fixture hashes and exact failure classification were
independently checked against the downloaded bytes. Each platform's files.json
explains original/stored hashes and path/whitespace/XML escaping transformations.
GitHub artifact digests are reported identities, not locally recomputed ZIP hashes.

The actual CI versions were Python3.14.7 on macOS15 and3.14.8 on Ubuntu24.04;
local macOS used3.14.9. Alembic/SQLAlchemy/PyMySQL pins matched on both CI jobs.
Each OS passed the two success tests and both exact failure oracles, with no
Snapshot/test admission after failed preparation, zero original contacts and
all three source hosts/directories cleaned. Both showed the same partial DDL
state described above. The13 classifier tests passed in both jobs. Negative
pytest runs intentionally have two setup errors; the outer gate accepts only
the exact injected statement/stage/errno, not arbitrary failing tests.

Python3.11 native migration execution is not covered by this campaign. It remains
an explicit minimum-version check for recipe productization, not a claimed PASS
or a defect reproduced in the existing3.11-supported runtime. No new full
framework/version support matrix is established by this bounded check.

## Technical judgment and next Human Review

For this bounded authored application, explicit target configuration is enough;
no preparation routing, SQL rewriting, new guest function or product helper was
needed. Recommend proceeding to a concrete migration/seed recipe with retained
acceptance; focused both-OS confirmation has passed. The decisive user benefit is that
setup lives in one callback and the second test only adds its marker/body.

The strongest limitation is input breadth: this is an authored example and
configuration-reading env.py, not an arbitrary legacy project. Different env.py
settings, Django/mysqlclient and dump-only workflows remain unverified; do not
advertise them as covered or silently remove them from the roadmap. A new helper
API should require evidence that a real configuration obstacle remains after
this recipe, rather than adding one solely because a spike succeeded.

The focused workflow verifies the same three scenarios on macOS15 and Ubuntu24.04
with Python3.14. It is not Qualification and does not run a broad compatibility
campaign. The results are ready for Human Review; no main integration or
release is part of this spike. No speed/usability timing is claimed.

[Fixture and reproduction](../../tests/preparation_migration_spike/reproduce.md)
contains exact commands and a copyable explicit-URL integration shape. The
runner saves source/tool/guest/host hashes, pytest JSON events/JUnit/logs and
partial-source state after deliberate failures. Copying the source fixture is
not a broad application/dump support promise.
