# Migration recipe — main adoption

2026-10-24. The Human approved proceeding after the
[adoption review](v06x-preparation-migration-adoption-review.md).
The selected landing commit is `ba379e1e204761013bc5153dcc5cb47151590323`, based on main
`22c647d39c94d1e912699613c70d762732c01598`. This record is a subsequent
documentation-only commit; it does not relabel the CI-tested source.

## Selected scope and identity

Adopted: the explicit Alembic migration/seed guide and Python/routing guide links,
`tests/preparation_migration_acceptance/`, its classifier test and
`.github/workflows/preparation-migration.yml`, with supporting design/review and
compact evidence records. The spike executable, spike classifier and spike
workflow are not adopted. Historical reproduction uses a fixed experiment SHA.
Experimental history is retained on `experiment/preparation-migrations`; main
receives a selected commit rather than that branch's history.

The stable acceptance directory, classifier and workflow are byte-identical to
CI source_commit `94d51e6ea6a663aaabfee92d2103bae1c7fefbf4`, verified by comparing
every selected file against Git objects. `python`, `internal`, `guest`, `release`,
`go.mod` and `go.sum` have no diff from the main base. No API/runtime/guest or
product dependency changes accompany this adoption.

## Verification and evidence limits

[CI40079827071](https://github.com/masahitojp/mariamem/actions/runs/40079827071)
and its [saved reassessment](v06x-preparation-migration-productization-evidence/ci-40079827071/assessment.json)
cover macOS arm64/Ubuntu x86_64, Python3.11/pytest7 and Python3.14/pytest9,
serial/two-worker success and both exact preparation-failure cases. Native CI
was not repeated locally for unchanged owners. The integration checks public
source/version rules, diff whitespace, local document references, exclusions
and exact executable-owner parity. Old spike-unit inputs in historical receipts
refer to the fixed experiment source, not a promise to install those tests on main.

The saved CI source is94d51e6, not the landing or later documentation SHA.
Pushing main starts its configured checks at the actual new main HEAD; their
completion is not inferred from the earlier candidate run. This is not
Qualification or a release.

The guide stays a bounded configuration-reading Alembic recipe. Other frameworks,
external legacy apps, dump import, automatic preparation routing and live reset
keep their existing separate decisions. No new release work is authorized.
