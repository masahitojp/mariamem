# Human Review — adopt the migration preparation recipe

2026-10-24. Reviewed artifact:
[updated productization record](https://github.com/masahitojp/mariamem/blob/11badeb0b694e8af430c356e77ad1db79a22735f/docs/reviews/v06x-preparation-migration-productization.md)
at artifact_commit `11badeb0b694e8af430c356e77ad1db79a22735f`.
CI tested source_commit `94d51e6ea6a663aaabfee92d2103bae1c7fefbf4`;
base is adopted main `22c647d39c94d1e912699613c70d762732c01598`.
These review inputs are taken from the preceding task and exact repository/CI
identities. The artifact commit adds receipts and documentation only; it is not
misidentified as the CI-tested source.

## One decision now

**Recommend adopting the explicit migration/seed recipe and stable acceptance
tests on main.** Users gain a concrete setup callback that prepares once and
feeds independent ordinary application tests. Both native OSes now confirm the
minimum Python/pytest boundary and two-worker reuse/failure behavior, closing
the additional productization conditions.

The strongest objection is breadth: the application and env.py are authored
examples, not a demonstration of arbitrary legacy migration configuration or
dump import. The guide makes that explicit and requires the application to pass
the preparation URL through its actual configuration seam. That is sufficient
for a useful bounded recipe, without advertising a universal adapter.
Approval here means main adoption of this recipe/test change only; Qualification,
release and any new importer remain separate.

## Accepted conditions checked

Prior conditions are pinned in the
[corrected Human Review at bfcab22](https://github.com/masahitojp/mariamem/blob/bfcab22c974f9bc4bb0dfd8e2d1f438eace89dc7/docs/reviews/v06x-preparation-migration-human-review.md#productization-acceptance--not-yet-satisfied).
[CI40079827071](https://github.com/masahitojp/mariamem/actions/runs/40079827071)
succeeded at the exact source above. The
[saved independent assessment](v06x-preparation-migration-productization-evidence/ci-40079827071/assessment.json)
binds jobs120830863509/120830863657, actual interpreter/package versions,
source/fixture/SDK hashes, guest identity and per-OS host identity. Raw event
classification and JUnit counts were independently recomputed after download.

| Condition | Judgment and detection |
| --- | --- |
| Python3.11/pytest7 native migration, seed, independent children | Satisfied on macOS/Ubuntu; serial success has four passing cases, exact final revision/schema/seed and isolated commit/FK recovery |
| Python3.14/pytest9 native regression | Satisfied on both OSes with the identical source-bound host used by3.11 within each OS |
| Two-worker migration reuse and isolation, both interpreter boundaries | Satisfied on both OSes; one prepare/capture per worker, two tests reuse each worker's baseline, distinct source IDs/host PIDs and four distinct child IDs |
| Exact revision/seed failure, original errors, no Snapshot/test admission, cleanup | Satisfied in serial and xdist on both interpreter/OS boundaries; separate SQL-derived oracle/stage/ProgrammingError1146, four expected setup errors and no skips; every source host reaped/directory removed |
| Explicit configuration and existing API | Satisfied: recipe/config-reading env.py, no automatic preparation routing, no new runtime helper; zero contacts to controlled original endpoint |
| Stable detection net after adoption | Satisfied: dedicated main paths trigger and pinned native runner; mutation tests reject missing/extra workers, repeated preparation/capture/cycles, shared child/source, unexpected SQL errors, contacts and cleanup failures |

Actual Python versions differ by runner and are retained in the record:
macOS3.11.9/3.14.7, Ubuntu3.11.17/3.14.8. All use pytest7.0.0/9.0.2 respectively
and xdist3.8.0. No attempt is made to substitute local patch versions.
Negative pytest setup errors are expected oracle evidence, not silently ignored
CI failures. Package/archive identities and original/stored evidence hashes are
retained; reported GitHub ZIP digests were not locally recomputed.

## Gaps and limits

No unsatisfied adoption condition was found within the approved scope.

- External legacy applications, other migration frameworks and dump import are
  unverified. This CI cannot establish those paths; the guide limits the claim
  rather than using the authored example as blanket compatibility evidence.
- This is not a test of migrations performed separately inside child databases.
  Migrations prepare the source before Snapshot; the tested isolation concerns
  subsequent child mutations. No additional guarantee is inferred.
- Fixture stage events are test diagnostics. General user-facing preparation
  error classification is not implemented; the SDK preserves original errors.
- Qualification and performance are outside this recipe gate. No throughput,
  preparation-time savings or release-readiness claim is made.

These limits do not require repeating the completed bounded check. Broader
framework/import coverage remains a separate product decision.

## Confirmed not gaps

`git diff 22c647d..94d51e6 -- python internal guest release go.mod go.sum` is
empty: no runtime/API/dependency or generated-source owner changes. Regeneration,
HANDWRITTEN_FILES, guest patches, canonical/provenance inputs and release ledger
updates are therefore not missing work for this candidate. Source fixtures and
strict failure assertions are in the stable acceptance owner; no existing oracle
or release guard is weakened. The user guides describe unreleased behavior and
explicit preparation; no mismatch with the continuing Snapshot product contract
was found. No contradictory stale runtime comment was introduced.

## Integration scope and stopping point

Integrate the production recipe/guide links, stable
`tests/preparation_migration_acceptance/` owner, classifier tests and dedicated
workflow from94d51e6, plus the necessary current status/review/evidence records.
Keep supporting historical evidence as documentation or pinned source links;
do not merge exploratory runtime history or adopt the old spike executable/
workflow merely because it is present on this experiment branch. Check the
selected diff and references against current main before integration.

Stop for Human main-adoption approval. No main merge/push, new CI submission,
Qualification or publication has been performed by this review.
