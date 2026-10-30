# EP1 / EG1 current acceptance map — 2026-10-30

This is the current evidence map for [Issue #18](https://github.com/masahitojp/mariamem/issues/18),
which owns the actionable checklist. The [work-sequencing decision](../decisions/e2e-v060-work-sequencing.md)
applies the Human's v0.7.x resource deferral. Earlier checkpoint reports retain
their actual sources and original scope; their resource wording is not a current
v0.6.0 gate. EP1/EG1 remain incomplete until the functional conditions below are
reconciled, candidate checks pass and the Human approves adoption.

## Evidence already available

Historical hosted execution source_commit
`694e8911a817309d077bcfc441a5a8ca01dfe81c` passed both hosts and the required gate
in [CI40961347571](https://github.com/masahitojp/mariamem/actions/runs/40961347571).
[Saved assessment](e2e-ci-40961347571/assessment.json) binds both ZIP digests and
all four installed host/Python cells. Later controlled tests at
`b20decac44225c4b4b2dbed8814f1e7530bd4be1` passed locally as described in
[the partial-cleanup report](e2e-partial-cleanup-controls.md). The submitted
checkpoint `ee76ff0490937a6102d0b9b5befc3fdf0ffd869e` includes those tests and
records; the older hosted PASS does not qualify that later candidate.

| Condition | Evidence and detection | Current disposition / concrete next step |
| --- | --- | --- |
| Required pre-code probe decision | Decision ancestor3ead1bc8 and `tests/test_e2e_decision.py` | Satisfied; preserve ancestry through integration |
| Fixed app, two cases, seed/UNIQUE reset, installed use | Both-host/minor source and installed examples in CI40961347571; actual app tests and receipt census | Covered at694e8911. Final candidate checks remain; do not open another historical rerun task |
| Go idle physical pool and registered job | `TestHTTPPhysical*` both-host logs in CI40961347571, including public Case rejection and lying join hook | Covered for the declared Go controlled app. Not direct Python hook-fault evidence |
| Partial construction, combined original/cleanup errors, canceled setup | `tests/test_e2e_entry.py`, `TestHTTPPartialStart`, `TestHTTPPartialLiveCreationRetainsAllOwners`, `TestHTTPCanceledCaseStillStopsApp`; local b20decac results | Component conditions covered locally; include these tests in final hosted checks |
| Reset/Resume/external failure, assertion/interrupt, browser/HTTP cleanup, overlap | Existing entry component controls, Go Fatal/parallel subprocess tests and internal/protocol Live controls | Reconcile the layer boundary once. Close wait and Python physical-retirement reach remain unverified at the composed entry boundary; add a bounded control only for the named missing outcome |
| Two independent actual owners; order/failure isolation | Controlled-owner probe and sequential actual examples exist | Additional functional validation required: distinct app/Live identities and no cross-owner mutation, reverse order and post-assertion fresh state. No resource collector needed |
| First/second-test and repeat usability/timing | Runnable fixed examples and installed consumers already pass | Preserve the minimal authored second-test edit and bounded command/phase timings. No cold-machine or human-edit-time claim; no retained64-table input required |
| Declared lifecycle cleanup and budgets | App StopReap, case disposal, Live/baseline/source cleanup; physical Busy and cleanup-debt controls | Keep correctness gates. Check owner/process/session/FD/temp return at lifecycle boundaries where required, without turning this into peak-resource characterization |
| Final candidate acceptance | Existing Live workflow covers both hosts/minors; current later tests are locally checked | One final source-bound candidate receipt and adoption review remain. Historical PASS is not a substitute |

## Deferred work and review decisions

Detailed retained baselines1/2/3, peak RSS/FD/session/allocated-temp census,
resource guard campaigns and tuning are **deferred to shared v0.7.x work**.
They are neither satisfied nor v0.6.0 blockers. The unsubmitted prototype is
identified in the sequencing decision and is excluded from the E2E candidate.

The adoption review must assess the explicitly bounded controlled-fault evidence
and disclosed hook obligations; it must not silently demand all physical engine
failure modes. Any additional blocker must identify a violated retained condition
above. The Human's candidate adoption/main-integration decision remains open.
P1, D1, independent dbt, Qualification and release remain separately tracked.

## Immediate sequence

Boundary completion increment: Python component controls now cover waiting for
an active case before disposal and timeout without premature disposal; both
Python3.11/3.14 pass17 local cases. `test_retirement.py` adds actual Python
SQL/Live negative and positive controls: a lying hook retaining its physical
session must hit Busy, preserve generation0 and stop later admission; real
retirement permits two seed/UNIQUE resets and disposes each browser context.
This is a controlled SQL-owning app hook, not an arbitrary Django pool claim.
The bounded `e2e_workflow_timing.py` selects the first example case, both cases,
then one repeated run and records command wall time/census and the minimal
parametrization edit. The supported-host results for these additions are pending.
These tests implement the previously named gaps without adding resource gates.

Functional increment at code source
`1355912b575a71999e180b1342e1b0b802eb7a06`: the separate
`docs/examples/e2e_owned/python/test_independent.py` and
`docs/examples/e2e_owned/go/independent_test.go` exercise two actual app owners
in forward/reverse order. A second owner's Reset must preserve the first
owner's active committed mutation. Python additionally retains an intentional
assertion failure and verifies fresh seed on the following case. Existing Go
Fatal/continuation controls retain their separate boundary. The new tests reuse
the fixed app inputs and do not change the installed-consumer case census.
The existing Live workflow selects these tests on both hosts/minors. Actual
supported-host results for this increment remain pending; added tests are not
a PASS or completion claim. Close-wait/Python physical-retirement reconciliation,
minimal usability/timing evidence and final adoption review remain open.

Publication/log-reference repair → finite functional/usability gaps above →
final candidate supported-host checks → one adoption review → Human-approved
main integration. Do not add new measurement infrastructure to complete EP1/EG1.
