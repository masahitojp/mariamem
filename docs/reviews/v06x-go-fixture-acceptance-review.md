# G1 acceptance review after both-host completion

The decision now is whether to accept G1's bounded prepared-test entry evidence.
Recommendation: accept this milestone and proceed with P1 design. The fixed
schema/seed guarantee, owner cleanup and installed public helper path now have
source-bound evidence on both required hosts, including the missing physical
fault controls. The strongest objection is that failing-engine I/O paths use
controlled backends/interfaces, even though they own real OS resources. This is
acceptable for the helper's finite ownership contract because separate actual-
guest SQL/isolation, installed-consumer and resource tests anchor the real path;
it does not prove every generated-engine I/O failure or cold setup cost.
Main adoption, Qualification and release are not decisions in this review.

## Reviewed object and independent receipt checks

- Candidate: `f58eebcdcb9ddb38a08fdbbd4ace8f6717154ab8`.
- Base: `1e60257ff1eb3a2e8c9d4a8f4d6e8ad07ee0920a` (including approved CI efficiency).
- Artifact: `docs/reviews/v06x-go-fixture-completion.md` at that candidate.
- Executed PR merge source: `cccd12c9b586b960cfa4f71d0005316ddc1b2e89`.
  `scripts/git_identity.py` identifies a commit. Its tree and the candidate tree
  are both `099f49b76d924c6c14e59eb6c5a1f8a6e2babec0`.
- [Live run 40751031818](https://github.com/masahitojp/mariamem/actions/runs/40751031818),
  attempt 1, and [required gate 123078686977](https://github.com/masahitojp/mariamem/actions/runs/40751031818/job/123078686977)
  succeeded. macOS job 123039208971 and Ubuntu job 123039208836 both succeeded.
- [Saved assessment](v06x-go-fixture-completion-evidence/ci-40751031818/assessment.json)
  and raw ZIPs retain executed source identity. Official archive digests match;
  both validators replayed resource/control observations and completion raw logs.
  macOS artifact 12848307861: `d234ba6492ad338f6b428302e46798bfdfb1134cad2467b25089ee86f8fd0fae`.
  Ubuntu artifact 12844242061: `8d40ebf47fffbef4c03f33cb82b73958d871874803afab3a675c012716048b99`.
  The bundle has its own SHA256SUMS.json; old receipts are unchanged.

## Prior conditions and detection net

| Prior condition | Judgment and evidence | Existing detector |
| --- | --- | --- |
| Approved design before helper code; readable-owned profile fixed first | Satisfied: design 39f9757 and decision 5b0a20e are ancestors of the candidate; decision precedes first helper source 5c739b7 | check_fixture_design.py and acceptance chronology checks; Human approval itself remains a recorded decision |
| Preparation once, exact schema/seed after committed mutation or failed test | Satisfied for the fixed entry: real guest integration plus normal/shuffled outside-checkout consumer on both hosts | tests/gointegration/fixture_test.go; six consumer cases replayed by go_fixture_completion.py |
| Preserved/consumed/invalid source, backing unwind, original plus cleanup errors | Satisfied for controlled failure boundaries with physical FD/temp accounting; generic capture-internal cleanup is explicitly unverified | root TestSnapshotPhysicalOwnership, helper TestFixturePhysicalCleanup and TestCaptureFailureDoesNotClaimInternalCleanupKnown; named semantic mutation controls |
| Pool before child; exactly-once backend disposal; no admission after cleanup debt | Satisfied within helper ownership | fixture_test.go cleanup/debt/concurrent-close tests, physical tests and eight required overlay mutations |
| Cap 1/2 × parallel 1/4, package budget 1; retained baselines 1/2/3; three time outcomes and resource guards | Satisfied in both saved host campaigns; acquisition and human authoring time are not measured | go_fixture_campaign.validate_host replays all four modes, raw counters, time records, checksums and actual FD STOP |
| Actual installed helper; no replace/workspace fallback; source/host binding | Satisfied: private exact-byte module, both host runtime targets, normal/shuffle runs | go_fixture_completion.validate plus negative receipt/module tests, including Linux substituted for Mac |
| Both required hosts and original receipt identities retained | Satisfied: macOS 15.7.9 arm64 and Ubuntu 24.04 x86_64 at cccd12c9; earlier b594527 receipts remain pinned | Live required gate and saved official ZIP digest verification |

## Missing-things scan and scope limits

No additional unsatisfied G1 adoption prerequisite was found within the fixed
milestone. This is a recommendation to accept evidence, not Human acceptance or
permission to integrate. Protection/required-context policy was not changed by
this candidate. Human adoption remains invisible to runtime CI.

No contradictory released-use claim was found: docs/go.md explicitly marks the
helper unreleased and links the candidate guide. README.md, docs/python.md and
docs/releasing.md retain their released contracts. No guest/generated sources,
release baselines, ledger or dependency change is present. No stale cleanup-
completed claim remains in the inspected capture diagnostic/guide boundary.

Unreached boundaries remain explicit: arbitrary caller-owned connections,
noncooperative callbacks, hard kill/machine loss, every real engine I/O fault,
clean-machine acquisition cost, and universal upstream-application compatibility.
Unit mutation PASS is not evidence of all those behaviors; no existing CI
provides that proof. P1/EP1/EG1 are still required and D1 can only be deferred
with its concrete obstacle/impact recorded. No whole-v0.6 completion is implied.

Next: retain this exact candidate for Human adoption review and design P1 using
the existing pytest preparation/Snapshot/Fork entry. No merge, runtime rebuild,
new benchmark or release was performed for this documentation review.
