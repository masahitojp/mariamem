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

The actual updated main baseline is
`a18b247d91ac709cba550c7d0c623236ed541a31` (#34), newer than the initially
reported38d4476. It has been merged into this candidate. #34 intentionally
makes full Live acceptance manual and keeps required daily source/integration
smoke in Development. Preserve that division. The e2e family gates the two owned
entry steps through a job-local selection output because main no longer has the
old scope job. Manual full acceptance selects all families; conservative input
classification and both gate boundaries are tested in test_live_selection.py.
This does not reintroduce automatic full acceptance on PRs.

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
