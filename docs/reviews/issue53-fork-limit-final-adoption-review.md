# Issue53 — final correction candidate adoption review

Subsequent Human decision,2026-11-04: adopt, including the WASI cleanup
prerequisite, with E1/E2 documentation corrections. The
[decision record](../decisions/issue53-fork-limit-adoption.md) owns that approval.
The recommendation below preserves its review context; integration/release were
not authorized by this decision.

Decision needed now: adopt PR85's finite per-Snapshot Fork limits, including its
host WASI write-error cleanup prerequisite. **Recommendation: adopt.** The final
corrections now have an exact-source both-host/interpreter matrix; capacity is
reserved before startup, with readable capacity diagnostics. Normal disposal
confirmation releases its slot; failed owned-Snapshot capture cleanup can instead
permanently latch the slot and parent admission as described below.

The strongest objection remains the ownership complexity across consuming
capture, Live recovery and different-host transfer. The fixed race/failure
controls and actual installed entries cover those supported paths, but do not
prove arbitrary non-cooperative guests can always be reclaimed. Keep that named
limit; it does not justify adding an unbounded route or extending this fixed
exit into a resource campaign. This is a recommendation, not Human approval or
permission to merge, choose a version or publish.

## Reviewed object

The inputs were reconstructed from the request to continue after successful CI:

- Candidate/source_commit: `cddd8dcbd6d664171907ffc1769b83e472640875`,
  branch `feat/issue53-fork-limit`, [PR85](https://github.com/masahitojp/mariamem/pull/85).
- Base/main: `8f42948340265ce38fde2d1fa6b2f82bf14ae9d2` (commit identity inspected).
  GitHub reports ready-for-review and MERGEABLE at the metadata read.
- Claims: the [fixed eighteen-row design](issue53-fork-limit-design.md#fixed-acceptance-and-stopping-point),
  [historical adoption review](issue53-fork-limit-adoption-review.md) and
  [G1–G3/P1–P6 follow-up](issue53-review-followup.md), read from the candidate.
- Contract constraints: [Snapshot product contract](../decisions/snapshot-product-contract.md)
  and [prepared consumer exceptions](../decisions/prepared-consumer-exceptions.md).
- Evidence: [verify41778273108](https://github.com/masahitojp/mariamem/actions/runs/41778273108),
  operation=verify/mode=auto; exact head matches,33 jobs succeed,3 expected
  recovery/publication/smoke jobs skip. No failed job. Both core/installed
  verification jobs, all feature owners and final aggregate succeed.

The9e788a25 evidence/wording commit is docs-only and reuses this tested
non-doc tree. Its fingerprint is in [assessment.json](issue53-fork-limit-evidence/ci-41778273108/assessment.json).
No receipt is relabelled to the later docs commit. The subsequent E1/E2
correction changes only docs and README wording. It preserves runtime code but
not the docs-excluding fingerprint, which includes README; that later equality
is not claimed. The original candidate CI receipt remains unchanged.

## Checked acceptance and corrections

[Saved receipts](issue53-fork-limit-evidence/ci-41778273108/README.md) include
10 checked ZIP digests,48 selected member hashes,43 published receipts and the
large-guard projections. Wheel identities agree across aggregate, platform
acceptance and installed consumers. External owned Go consumer product-file
hashes agree with the candidate; no replace directive is used in that consumer.
D1 records installed=true, clean source/adapter identity and matching host SHA.

| Host | Python | Ownership/transport | Actual guest | Installed Live / owned E2E | D1 serial / xdist |
| --- | --- | --- | --- | --- | --- |
| macOS15 arm64 |3.11|105 PASS|9 PASS|PASS|20 /15 PASS|
| macOS15 arm64 |3.14|105 PASS|9 PASS|PASS|20 /15 PASS|
| Ubuntu24.04 x86_64 |3.11|105 PASS|9 PASS|PASS|20 /15 PASS|
| Ubuntu24.04 x86_64 |3.14|105 PASS|9 PASS|PASS|20 /15 PASS|

All eighteen fixed rows are technically satisfied within their indexed
controlled/actual scopes; [assessment.json](issue53-fork-limit-evidence/ci-41778273108/assessment.json)
retains the per-row detectors. The original parent-lock/Close, cap2 explicit
Live recovery, bounded watchdog, shared numeric range, consume/preserve,
late-outcome ownership and D1 cap1 conditions remain in that set. Controlled
cleanup faults are not described as real-engine OOM reproductions.

| Review condition | Result and detection net |
| --- | --- |
| G1 diagnostics | Satisfied: pool Usage/Describe, public/control errors and Python full-reply/timeout paths report cap and observed occupancy. Pool/public/control/Python tests and installed consumers assert diagnostics without losing error identity. Counts are sampled, not an admission guarantee. |
| G2 historical/current consistency | Satisfied by current status and follow-up; old c53771cd and8566c8ad contexts retain their identities. Prose freshness is review-only, not detected by ordinary CI. |
| G3 memory observation/fallback | Satisfied within scope: `memory_sources_test.go` injects exact sysinfo units, proc fields, source failures and minimum/fallback cases on both hosts; core logs show native forklimit package PASS. Individual Linux adapter skip status is not observable in nonverbose logs; no observed physical-RAM value is claimed. |
| P1 new exact matrix | Satisfied by41778273108 at cddd8dcb, not old c53771cd READY. Source/wheel binding guards are mechanical. |
| P2 real automatic capture | Satisfied: `test_mapped_child_resnapshot_preserves_independent_lineage` asserts both real capture values in1..MaxInt32. Local exact-host case and both-host core module pass. Policy tests assert arithmetic; positive-value checks alone do not reject a legitimate1 or prove CPU-optimal sizing. |
| P3 hidden cgroup | Satisfied by README, Go/Python guides and notes: unreadable limits may expose host-RAM sizing and over-admit. Choose an explicit cap. Documentation is review-only. |
| P4 default wait disclosure | Satisfied by README entry/limits and guides/notes; candidate explicitly unreleased, absent from published0.6.0. Semantic wording is review-only. |
| P5 root Start | Satisfied: independent root Start is outside Snapshot caps; “no unlimited” describes Snapshot/Fork settings. Review-only scope wording. |
| P6 negative zero | Satisfied: raw -0 rejects request-locally; token and shared-host survival tests execute in core. Public Go zero remains auto; Python explicit zero remains invalid. |

## Missing-things scan and limits

No unresolved technical blocker was found in the fixed exit. E1 identifies a
named recovery limitation: when failed-capture cleanup calls `Owned.Close` and
that Close fails, `captureDebt` is never cleared. `db.disposed` remains false and
`retryCleanup` cannot settle the lease; `Owned.Close` discards its file list and
returns the cached error on later calls. The slot and parent admission remain
latched even after runtime disposal. Live Reset cannot recover this debt.
See `internal/control/shared.go` snapshot error handling,
`internal/control/fork.go` disposed/settle/retryCleanup and
`internal/snapshot/owned.go` Owned.Close. This is code-inspected behavior, not a
new actual-fault reproduction; the permanent-capture path has no dedicated
end-to-end detector. It is now explicit in README, Go/Python limits and notes;
prose completeness remains invisible to CI. Safely close remaining owners and
prepare a fresh independent lineage. Do not claim eventual release for this path.

Human adoption is subsequently recorded in the linked decision; integration
remains pending, and CI cannot grant either decision.

- Entry scan: direct Go/Python, pytest, fixture, Live, owned E2E, handoff and D1
  remain covered. No unlisted required entry omission found.
- Usage scan: current Go/Python guides and unreleased notes now point to the new
  matrix; README discloses default waiting, nested acquisition, root exclusion
  and hidden-cgroup limits. Published0.6.0 notes/version remain unchanged.
- Generated ownership: the WASI fd_write prerequisite remains included, with the
  checked regeneration adapter, provenance/license continuity and both-platform
  guards. No new guest input or translated MariaDB behavior is claimed by the
  review corrections. The original review documents the prerequisite mechanism.
- Existing error oracles remain: both core logs preserve47 actual runtime tests,
  33 snapshot checks and the exact accepted-exception comparator PASS while
  retaining Python functional FAIL. No new exception or silent cleanup bypass.
- No resource/latency/RSS/CPU-optimal claim, cold-host setup claim, prewarming or
  #84 requirement is added. Non-cooperative cleanup may retain occupied leases.
- Historical receipts are unchanged. The new matrix is independently assessed
  from new artifacts; only the fixed detector descriptions are carried forward.

This is a targeted contract/evidence and correction review, not an independent
line-by-line audit of the entire implementation. No new runtime campaign was
launched. At review time, the next action was the Human's adoption decision for the named
candidate and prerequisite; that decision is now recorded above. Main integration
remains separate; protected PR checks still apply to this docs record.
Release qualification/publication requires its separate decision.
