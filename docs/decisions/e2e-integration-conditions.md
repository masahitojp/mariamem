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
is choosing between that route and explicitly changing the timing of full
acceptance to release verification. Neither is silently assumed here.

New receipts are required for the integrated workflow/test source. The old
CI41058866706 remains evidence for edfee478 only; it is not the integrated
candidate's receipt. After source-bound full Live success, retain its artifact
hashes/results and pass all protected contexts before merging. If main moves,
inspect/reconcile its diff first; do not merge an untested runtime/workflow union.

Unreleased staging notes now retain both P1 and E2E sections. The P1 section
comes from candidate8912224a and links to that fixed source while P1 is not yet
present here. The later integration must keep both announcements; a boundary
test detects dropping either. Notes do not independently adopt P1 or publish a
release. P1 remains separately owned and is not merged by this E2E action.

Limits remain unchanged: supplied hooks own arbitrary delayed/unregistered work,
routing and pool retirement; hard-kill/non-cooperative recovery is not promised;
some error paths use controlled owners/backends. Detailed peak-resource work is
shared v0.7.x work. The [adoption review](../reviews/e2e-v060-adoption-review.md)
retains its original source/evidence context and bounded recommendation.
