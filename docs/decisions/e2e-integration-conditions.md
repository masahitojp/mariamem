# E2E integration conditions — Human approval, 2026-10-30

The Human approved proceeding with bounded E2E adoption subject to the five
integration findings. [PR #28](https://github.com/masahitojp/mariamem/pull/28)
must use a **merge commit**, never squash/rebase: required pre-code decision
`3ead1bc8d1ebb984f912cf4062c7a6dd759698c9` and design
`ca3d3937c9dcc12c536bcedf75cb5b9ad090bb6c` are candidate ancestors that must
survive integration. `tests/test_e2e_decision.py` checks the first ancestor on
main too; PR CI cannot attest the future merge method. The probe result
`870af0ab793b7adc48c11f3e39108416dce0b330` is a separately preserved evidence
commit referenced by the decision, not an ancestor of this candidate. No
experimental history is merged just to change that fact. P1 #26's corresponding
ancestry requirement also requires merge-commit integration.

The first updated main baseline was a18b247d (#34). During its full CI,
main advanced through #35/#36 to
`55b09c3ae78f98d1b989cdc5d82bfa33ba96b72b`; that baseline is now merged too.
#35 makes heavy feature acceptance release-owned workflow_call only; #36 shares
normal daily check/integration compilation. Preserve those policies. E2E uses
job-local family outputs (main has no old scope job), gates both owned-entry
steps and uses SOURCE_COMMIT, not the caller's GITHUB_SHA. Full acceptance
selects all families. The boundary tests protect gating, conservative classification,
release-only workflow triggers and explicit candidate identity.

The first integrated full run41070798375 at67ef37dc had successful required
checks/native/macOS, but Ubuntu's G1 cap2/parallel4 observer reported zero RSS
at process exit and returned UNVERIFIED. The underlying runtime controls PASS,
returncode0, cleanup_complete true and final children/baselines0 are preserved in
[the failure receipt](../reviews/e2e-integration-ci-41070798375/attempt1-ubuntu-g1/assessment.json).
Attempt1 is not PASS. A one-time same-source Ubuntu retry was requested, then
canceled as superseded when the later main workflow/acceptance inputs were found.
No observation oracle was relaxed or missing counter synthesized.

The newer source still needs its own acceptance evidence. Since full Live now
runs only under Release CI, obtaining that evidence before integration entails
operation=verify and its wider qualification work, with no publication. The Human
selected operation=verify before integration, without publication. During its
final source check, P1 #26 landed on main as merge commit
`4a8a68350e8c43fc107843a6efe7781cad1a4e2a`. That latest baseline is now merged
here too; both ancestry lints and both complete feature workflow steps are
preserved. Verify41080127438 at the previous source was immediately requested
canceled as superseded, not treated as evidence for the P1/E2E union. The exact
new source is submitted to the same verify-only route after local checks.
Main then advanced to4a7966be (#37); that CI-only update is incorporated too,
including shared release-runtime wheel/host consumption. No duplicate P1 wheel
build or standalone full workflow is reintroduced.

New receipts are required for the integrated workflow/test source. The old
CI41058866706 remains evidence for edfee478 only; it is not the integrated
candidate's receipt. After source-bound full Live success, retain its artifact
hashes/results and pass all protected contexts before merging. If main moves,
inspect/reconcile its diff first; do not merge an untested runtime/workflow union.

Unreleased staging notes now retain both P1 and E2E sections. The P1 section
comes from candidate8912224a and now links to the adopted local documents. P1
is present through main merge4a8a6835. This integration keeps both announcements; a boundary
test detects dropping either. Notes do not independently adopt P1 or publish a
release. P1 was adopted by its separate owner; this action only incorporates the resulting main.

Limits remain unchanged: supplied hooks own arbitrary delayed/unregistered work,
routing and pool retirement; hard-kill/non-cooperative recovery is not promised;
some error paths use controlled owners/backends. Detailed peak-resource work is
shared v0.7.x work. The [adoption review](../reviews/e2e-v060-adoption-review.md)
retains its original source/evidence context and bounded recommendation.
