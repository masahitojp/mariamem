# Corrected Live candidate — main adoption recommendation

Decision now: adopt exact corrected candidate c1ee8d3 on main. Recommend adoption
within the documented sequential E2E bound, with Live required-check activation
and readback included in the approved integration step. The fresh source-bound
native/both-host matrix and new aggregate all pass, closing the prior CI hold.
The strongest material concern remains application coordination: idle physical
connections or delayed work prevent safe reset. The guide requires quiescing
requests/jobs and retiring connections, and the authored applications satisfy
that bound. Broader pool/session continuity or job fencing would change this
recommendation's scope. Qualification and publication are not being decided.

## Fixed object and evidence

The Human reported completion of the submitted correction run. The review inputs
are reconstructed from that request and the previously pinned adoption report:

- Artifact: docs/reviews/v06x-live-main-adoption-review.md at
  source_commit `c1ee8d32e309dbef514d45db37f12fbb53acb7a9`.
- Candidate: `c1ee8d32e309dbef514d45db37f12fbb53acb7a9`,
  experiment/live-review-fixes. Stable base:
  `bf3a29c292064ddbbd4c7b9a9c6e712504d0f4e4`.
- Prior review: [held adoption report](v06x-live-main-adoption-review.md), its
  F1/F2/F3 references, [selection record](v06x-live-main-selection.json) and
  [three correction records](v06x-live-review-fixes/README.md).
- Fresh [CI40435625453](https://github.com/masahitojp/mariamem/actions/runs/40435625453)
  has six successful jobs on exact c1ee: scope121963485362,
  native3.11/3.14 jobs121963582914/121963582844,
  macOS121964165154, Ubuntu121964165197 and required121974370999.

One authenticated run metadata read confirmed completion/source. The saved
[receipt](v06x-live-main-evidence/ci-40435625453/README.md) preserves four original
ZIPs with official digests, all member hashes, scope/aggregate logs and API data.
Its validator re-applies exact-candidate predicates to native/browser XML/events,
real controls, installed consumers and actual aggregate NEEDS_JSON. No guest,
benchmark or CI rerun was performed to review these records. Candidate refs and
older receipts remain fixed under their original source identity.

## Prior conditions and detection net

| Condition | Judgment and evidence | Detection / remaining action |
| --- | --- | --- |
| F1 maintained Live acceptance | CI wiring satisfied: scope selects full matrix and the actual aggregate verifies all dependency results | scripts/live_ci.py:21 and tests/test_live_ci_workflow.py cover missing/failure/cancellation/unexpected-skip states; full route observed on GitHub. Guide-only skip remains unit/model coverage |
| F2 real adapter cleanup retry | Satisfied within reviewed boundary; product source is unchanged from6edcd29 and the three Go race packages pass again | original old-adapter/endpoint negative evidence retained; fresh live-race.txt includes Live, control and public package |
| F3 minimal production selection and docs | Satisfied; selected runtime/SDK/tests/guide/CI plus explicit correction tooling, not exploratory history | selection manifest; no product Python/Go, guest/generated, dependency, version or release-ledger delta from6ed |
| OpenSSL4 documentation | Satisfied in development.md:87 and python.md:243; original local FAIL retained | CI is OpenSSL3, so this remains a documented environment limit, not CI-proven OpenSSL4 support |
| Ordinary-operation interruption | New12 cases pass in canonical Python3.14 on both hosts; local99-case suites pass on both3.11/3.14 and reject missing/double cleanup mutations | test_owned_snapshot_unit.py:272; framed fake-host request/ownership coverage, not every native SQL interrupt point. CI's per-interpreter Live loop remains53 cases per cell |
| Repository required checks | Existing check/integration enforcement verified; Live required gate activation still open as an integration action | fresh protection-readback.json verifies strict/app15368/admin enforcement. CI cannot prove or monitor repository policy. Add/read back Live after Human adoption |

The raw canonical check is1083 PASS/45 explicit SKIP/76 subtest passes once per
host, on default Python3.14. The existing focused loop totals212 passes across
four OS/Python cells. Fresh native controls total4, positive public Live routes8,
actual lifecycle defects detected16, Fork campaigns12 and real SQL controls48.
Raw browser suites deliberately retain the exact post-commit assertion failure;
it is checked together with next-case isolation, not converted to a raw PASS.
Installed wheel consumers use default Python3.14 on each host; external Go uses
an exact local source replacement, not a published-module download.

## Missing-things scan and limits

No additional usage/version contradiction was found in README, Go/Python/Live
and release guidance. The unreleased source feature remains separate from
published v0.5.3. No generated-source ownership or release bookkeeping gap was
found; guest inputs, HANDWRITTEN_FILES, baselines and ledger are unchanged. No
stale changed product comment was found. No additional unlisted adoption gate
was found beyond the explicitly open repository-setting action and required PR
checks. Neither independent regeneration nor new performance evidence is claimed.

Observed guest hosts are macOS arm64 and Ubuntu x86_64 with both Python minors
as recorded in assessment.json. Native reference is Ubuntu MariaDB12.3.3 with
exact-source authored applications. This does not establish arbitrary Django,
legacy-app/MySQL-dump support, cold/setup improvement, parallel shared Live,
session continuity or delayed-job fencing. Python3.11 ordinary interruption is
locally verified; automatic canonical coverage for those new cases is3.14.
No reproduced product harm or runtime delta was found by these corrections.

## Approved-integration procedure, not authorization

If the Human adopts this candidate, use a PR for the selected candidate with
existing required check/integration contexts satisfied on the tested merge
source. Preserve any intervening main protection settings; add Live required
gate using the prepared payload and verify all three app-bound contexts, strict
freshness and admin enforcement by API readback. Do not declare adoption complete
before that setting is confirmed. Carry the new receipt/status documentation
with its original source identities; do not merge exploratory branches or relabel
an old CI run as the integration SHA. No additional product code work is requested.

This review recommends; it does not approve or perform main integration,
Qualification or release. Those actions remain Human decisions.
