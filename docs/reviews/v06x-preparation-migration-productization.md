# Explicit migration preparation — productization candidate

2026-10-24. The Human approved proceeding after the
[SHA/acceptance correction](https://github.com/masahitojp/mariamem/blob/bfcab22c974f9bc4bb0dfd8e2d1f438eace89dc7/docs/reviews/v06x-preparation-migration-human-review.md).
This authorizes the recipe and stable regression-test work, not main integration,
Qualification or release. Implementation starts from source_commit
`bfcab22c974f9bc4bb0dfd8e2d1f438eace89dc7`, on adopted runtime main
`22c647d39c94d1e912699613c70d762732c01598`.
The historical spike and CI40072694488 remain prior evidence; they are not
acceptance of this new candidate or Python3.11/xdist execution.

## Result and next gate

A [user recipe](../preparing-test-data.md) and
[stable acceptance owner](../../tests/preparation_migration_acceptance/reproduce.md)
are implemented. No public API, runtime, guest, converter or product dependency
changes are needed. Preparation uses an explicit source URL, tests retain normal
application SQL/transactions and the approved marker, and each worker owns its
baseline. Alembic is the concrete example, not a restriction on mariamem_prepare.

Local classifier/collection checks and the expanded native acceptance passed.
[CI40079827071](https://github.com/masahitojp/mariamem/actions/runs/40079827071)
tested exact source_commit `94d51e6ea6a663aaabfee92d2103bae1c7fefbf4` on both
OSes. Downloaded raw receipts were hash-checked and independently reassessed.
The candidate is ready for main-adoption Human Review; it is not yet adopted.
The strongest limitation remains input breadth: this authored application does
not establish arbitrary legacy env.py, dump import or other frameworks.

## Production scope and ownership

- `docs/preparing-test-data.md`: explicit URL/configuration seam, source schema,
  migration, seed, connection disposal, routing setup, tests, worker ownership,
  partial-DDL failure behavior. Linked from the Python and routing guides.
- `tests/preparation_migration_acceptance/`: stable authored application and
  migration chain with test-only event wrappers/injections. The experiment
  source remains unchanged for its historical reproduction; no exploratory
  runtime behavior is adopted. New owner differences are environment matrix,
  source-verified host reuse, worker-local receipts and strict distributed gates.
- `tests/test_preparation_migration_acceptance.py`: exact positive/negative
  receipt classification and worker/cycle/identity mutations. The original
  spike's13 classifier tests also still pass.
- `.github/workflows/preparation-migration.yml`: macOS15 arm64 and Ubuntu24.04
  x86_64, Python3.11/pytest7.0.0 and Python3.14/pytest9.0.2, pinned xdist3.8.0.
  Build the exact-source Go1.26.10 host once per OS and verify it again when
  reusing it with the other Python interpreter. The main paths trigger retains
  the native gate after adoption; this is not an extra release Qualification.

## Acceptance and evidence

| Check | Current result |
| --- | --- |
| Python3.11/pytest7 classifier, including original spike oracles | PASS locally; saved inputs/output below |
| Python3.14/pytest9 classifier, including original spike oracles | PASS locally; saved inputs/output below |
| Four application test cases collect with plugin/xdist on both interpreters | PASS locally; collection only, not native execution |
| Python3.11 native migration/seed/isolation and both failure oracles | PASS on both OSes at94d51e6 |
| Python3.14 native regression on this candidate | PASS on both OSes at94d51e6; prior spike is not substituted |
| Migration-specific two-worker reuse/isolation and failure oracles, both interpreters | PASS on both OSes at94d51e6 |
| Public source/version and diff/reference checks | PASS locally before submission |
| Qualification/performance/dump import/external application | Not run; outside this candidate |

Local compact evidence is in
[productization-local](v06x-preparation-migration-productization-evidence/local/results.json).
It records actual interpreter/package versions, tested worktree file hashes and
raw log hashes; files.json records original/stored dependency-report hashes and
normalization of local prefixes (including upstream README examples). Package
archive identities are unchanged. Its base_commit is not claimed as a native tested candidate.

Each interpreter's native runner executes six scenarios: serial and xdist each
have success, later-revision failure and seed failure. The success path executes
four tests (two commit/next-child pairs); xdist group scheduling requires each
worker to reuse one baseline for its pair. Gates require distinct source IDs,
four distinct child IDs, exact prepared contents/schema, recoverable FK1452,
zero original contacts and source cleanup. Failures require the original
ProgrammingError1146 with the exact injected SQL-derived oracle/stage in each
worker, no Snapshot/test admission and cleanup. Another worker's result cannot
hide a failed/missing worker. Worker-local files prevent concurrent JSONL writes.

## Native CI receipts

[Assessment and job identities](v06x-preparation-migration-productization-evidence/ci-40079827071/assessment.json)
record all six scenarios per interpreter/OS and distinct source-host PIDs per
worker. [Artifact identities](v06x-preparation-migration-productization-evidence/ci-40079827071/artifacts.json)
are GitHub-reported ZIP digests, not locally recomputed ZIP hashes. Each platform
has py311/py314 results, events, JUnit and dependency receipts with files.json
original/stored SHA256 and normalization rules. Nested raw hashes are not claimed
to hash normalized copies.

| OS | Actual minimum Python | Actual current Python | Serial / xdist / both failures |
| --- | --- | --- | --- |
| macOS15 arm64 |3.11.9 / pytest7.0.0 |3.14.7 / pytest9.0.2 | PASS for both interpreter environments |
| Ubuntu24.04 x86_64 |3.11.17 / pytest7.0.0 |3.14.8 / pytest9.0.2 | PASS for both interpreter environments |

All use xdist3.8.0, Alembic1.18.4, SQLAlchemy2.0.54 and PyMySQL1.2.3.
Within each OS the two interpreter environments used the identical host hash;
source/Go stamp and guest identity were verified. Original-endpoint contacts
were zero; every scenario's source hosts were reaped and directories removed.
Intentional negative pytest invocations reported four setup errors each; the
strict outer gate accepted the exact injected SQL-derived oracle/stage/1146,
not arbitrary errors. Runtime/test code is unchanged in this receipt follow-up.

## Conditions retained

No preparation automatic routing, saved Snapshot API, importer, new user-facing
error API or general migration adapter is introduced. The callback return is
ignored, not a finalizer. User setup closes connections before capture. DDL
persistence before failure is documented, not silently repaired or retried.
The original migration/failure assertions are retained in the stable owner;
no guest/generated ownership, strict Snapshot oracle or release guard changes.

Main adoption, any later Qualification and release remain separate Human decisions.
