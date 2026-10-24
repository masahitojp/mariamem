# Human Review — explicit Alembic preparation

2026-10-24. Reviewed artifact:
[execution record](v06x-preparation-migration-spike.md) at candidate source_commit
`84c8ee16e09ad63475f7185f04292e4624761a7c` on
`experiment/preparation-migrations`. Base runtime is adopted main
`22c647d39c94d1e912699613c70d762732c01598`; approved bounded design is
`93c201756879f51bb30c92945f2e3bb509e3c16e`.
These inputs/decision are reconstructed from the preceding task and repository.

## Decision now

Recommend proceeding to productization of an **explicit Alembic migration/seed
recipe and retained regression tests**, using the existing preparation callback
and marker. No new runtime helper, implicit preparation routing or importer is
needed for the tested path. The decisive benefit is one reusable preparation
callback, followed by ordinary independent application tests; both native OSes
now confirm that path and its failed-preparation boundary.

The strongest objection is that the authored example does not demonstrate an
arbitrary legacy application's env.py or solve dump-only preparation. Keep the
published recipe specific to explicit configuration-reading Alembic environments
and retain those companion decisions. This supports a bounded useful recipe,
not a blanket claim about all migrations. Main integration/publication is not
approved by this recommendation; prepare the smallest reviewable production
recipe/test change first.

## Scope and evidence

[CI40072694488](https://github.com/masahitojp/mariamem/actions/runs/40072694488)
passed the exact candidate above on macOS15 and Ubuntu24.04. The
[saved assessment](v06x-preparation-migration-spike-evidence/ci-40072694488/assessment.json)
and linked platform receipts bind source, SDK/fixture hashes, tool versions,
guest/host identity, counts and original/stored evidence hashes. Reassessment
used the strict gate against downloaded raw events, rather than trusting CI's
headline success alone.

| Approved check | Judgment / evidence |
| --- | --- |
| Ordered revisions, final schema/data and seed | Satisfied on both OSes: m2 recorded, legacy row retained with default, seed data and unique/foreign-key metadata checked |
| Snapshot -> first commit and independent second child | Satisfied:2 tests, different child IDs, exact prepared rows in second child, constraint violation1452 remains recoverable |
| Later-revision and seed failure | Satisfied: exact different failed statements/stages, original ProgrammingError/1146; no successful/attempted Snapshot or admitted tests |
| Lifetime/original destination | Satisfied: all3 source hosts reaped and directories removed per OS, zero controlled original-endpoint contacts |
| Original state after failed DDL | Observed consistently: rating column already added with revision stillm1 after revision failure; not misrepresented as all-DDL rollback |
| Fixed inputs/reproduction/user recipe | Satisfied for the bounded example: pinned development tools, authored fixture and explicit-URL recipe; no performance/usability timing claim |

## Gaps and detection net

1. **Python3.11 native migration is unverified.** Both hosted jobs use3.14
   (`.github/workflows/preparation-migration-spike.yml`), and the classifier does
   not establish migration-tool runtime compatibility at the minimum. Include
   a3.11 native migration run when preparing the production recipe/acceptance.
   The product's existing3.11 routing checks are not substituted for that run.
2. **Existing external application breadth is unverified.** The fixture is
   repository-authored and env.py reads the explicit URL. Current CI cannot
   detect a user's different configuration loader or unsupported framework.
   Document the exact seam; retain Django/mysqlclient and further framework
   coverage as separate decisions, not suppressed failures.
3. **The current artifact is experiment tooling.** Keep useful success/failure
   assertions, but do not merge exploratory history wholesale. Integrate a
   small copyable recipe and stable test owner; preserve the exact failure
   oracles. Reuse an already-identified native host where practical instead of
   adding another broad guest build/Qualification campaign.
4. **Stage observations are experiment diagnostics.** The current SDK preserves
   original errors; this spike does not add a general user-facing structured
   preparation error API. Wider actionable-diagnostic work remains open.

The first three are concrete productization work, not reasons to repeat the
completed two-OS bounded spike or reopen its conclusions. The fourth belongs
to the continuing capability map and must not be described as implemented.

## Confirmed not gaps and stopping point

No guest/converter/generated owner, Python product API or product dependency
changed in this spike (`git diff 22c647d ... -- python internal guest release
go.mod go.sum` is empty). Existing Snapshot isolation and failure oracles were
not weakened. Current usage guides do not claim a new importer. No new
regeneration, performance measurement, Qualification or release was claimed.
No additional mismatch was found within the approved bounded scope.

Dump-client vs library import remains undecided; preparation routing stays out
of0.6.0 and is retained for0.6.x reconsideration. Live keeps its own task and
0.6.0 scope decision. Stop here for the Human's productization decision; do not
merge this branch or start release work automatically.
