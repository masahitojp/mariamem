# Issue53 — finite Fork candidate adoption

Human decision,2026-11-04: adopt the finite per-Snapshot Fork candidate in PR85,
including the Go-host WASI write-error cleanup prerequisite, with the E1/E2
documentation corrections below. This decision does not authorize a version,
publication or main integration; integration remains the next separate action.

Adopted runtime/source_commit: `cddd8dcbd6d664171907ffc1769b83e472640875`.
Review/evidence head: `9e788a2582e31447e359590db0cc2edae09339d9`, whose non-doc
tree is identical. The E1/E2 record is documentation-only and preserves runtime code. It also
changes README wording, which is outside docs/ and therefore changes the saved
non-doc fingerprint; do not claim fingerprint equality for that later record.
The inspected diff contains only README and docs paths, with no runtime change.
[Exact verify41778273108](https://github.com/masahitojp/mariamem/actions/runs/41778273108)
passes both hosts/Python minors and final aggregate. The
[final review](../reviews/issue53-fork-limit-final-adoption-review.md) and
[checksummed receipts](../reviews/issue53-fork-limit-evidence/ci-41778273108/README.md)
retain technical scope. Their original CI assessment's adoption=PENDING is the
state at evidence acquisition, not the current Human decision.

## E1 — capture cleanup can latch admission permanently

If capture fails and closing its newly owned Snapshot also fails, the shared
host retains `captureDebt` without a clearing path. `Owned.Close` caches the
error, drops its descriptor list and cannot retry. The originating lease remains
occupied and its parent pool's admission remains stopped, even after runtime
disposal completes. Cleanup retry and Live Reset cannot clear this capture debt.
Safely close remaining owners and prepare a fresh independent lineage rather
than expecting recovery of the affected pool.

This is stricter than retryable child-runtime cleanup debt and is a named limit
of the adopted candidate. It is not a newly reproduced end-to-end fault or a
claim that unknown disposal eventually succeeds. The limit is now recorded in
README, Go/Python usage limits, unreleased notes and the final review. No runtime
behavior or failure oracle is changed by this documentation correction.

Source: `internal/control/shared.go` capture failure, `internal/control/fork.go`
disposed/settle/retryCleanup, `internal/snapshot/owned.go` Owned.Close.

## E2 — current matrix versus historical checkpoints

P1 (new-head exact matrix) is satisfied at cddd8dcb/41778273108. Earlier local
checkpoints in the follow-up are explicitly historical and state the later
resolution. The original c53771cd review is labelled historical; its tree-reuse
advice applies only to that old checkpoint and did not waive the later matrix.
No old receipt or checksum is edited or rebound to a newer source.
