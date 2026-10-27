# Human-approved Live main adoption

The Human approved the previously applied main protection requiring check and
integration, strict base freshness, GitHub Actions app 15368 and administrator
enforcement.

The Human authorized adopting reviewed Live candidate
`c1ee8d32e309dbef514d45db37f12fbb53acb7a9` through a PR against main, without
bypassing protection. The [adoption recommendation](v06x-live-correction-adoption-review.md)
and [six-job CI receipt](v06x-live-main-evidence/ci-40435625453/README.md) retain
their original source identities. The integration branch carries those exact
product/CI files plus evidence, this approval and current status updates.
The expected starting base is `bf3a29c292064ddbbd4c7b9a9c6e712504d0f4e4`.
PR checks must validate the current strict-base merge source; earlier candidate
CI is not relabelled as that source or the eventual main commit.

## Protection activation

The prepared protection-with-live.json was reread along with current repository
settings before application. A PATCH changes only required status checks,
preserving unrelated settings and any additional contexts. The
[policy readback](v06x-live-main-adoption/policy-assessment.json) verifies
check/integration/Live required gate, all bound to app 15368, strict=true and
administrator enforcement. Before/after API responses and the actual patch are
retained in that directory. This is administrative evidence, separate from CI.

## Submission and completion boundary

The approved integration is submitted through feature/live-main-adoption to main.
Do not use admin bypass or weaken required checks. Repository auto-merge is
currently disabled; submit and hand off CI without supervising it. On the Human's
CI-result report, continue the already-authorized adoption without a new approval
request: re-read the PR head/base, required checks and protection, merge the exact
head through the PR only when strict-base conditions pass, then record the actual
merge/main identity and API readback before declaring adoption complete.

At submission, integration is not yet complete. This approval is not version,
Qualification or publication approval, and no release ledger is changed.

## Separate follow-up after adoption

These are explicitly undecided follow-up choices, not completed evidence or new
conditions silently added to this adoption:

- Observe one real guide-only GitHub skip, or explicitly accept the existing unit
  model coverage. The Human has not selected either alternative yet.
- Decide whether docs/reviews-only PRs should enter the skip allowlist. Current
  selection stays conservative; the allowlist is not expanded here.
- Decide whether to expand Go/native interruption coverage beyond the present
  Python framed-control and existing real-runtime boundaries. No new coverage is
  claimed by this integration.

Qualification, version selection and publication require separate Human decisions.

## Completion after PR1

PR1 merged on 2026-10-27T05:34:27Z. The actual main squash/source commit is
`212bb07ffb8e89669c32d6b5a7ba94fc7aa18b2c`; approved head was
`fcc6bd856867afdf5909c8fec4abd5c586ec434e`. Actual CI source
`cf3991234efa3897a7a50466b07e29a97af2aa7c` has the identical tree. Protected
check/integration/Live required gate all passed; post-merge API readback confirms
all three app-bound contexts, strict and admin enforcement. The
[completion receipt](v06x-live-main-integration/README.md) preserves these separate
identities and original artifacts. This closes the submission-stage condition
above; Qualification, version/publication and the separate follow-up choices
remain undecided. The completion-record PR only updates docs/evidence.
