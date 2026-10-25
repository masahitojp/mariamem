# Bounded dump reader — adoption recommendation after CI handoff

Decision now: adopt the reviewed bounded Python dump helper on main, explicitly
including its separately assessed host status prerequisite. **Recommend adoption**:
the installed helper preserves the native comparison and preparation lifecycle
on both supported OS/Python boundaries, and the maintained-CI/source-binding
conditions from the previous review are now satisfied. The strongest objection
remains owning a second client parser. The finite producer profile, explicit
rejection rules and maintained native comparison make that acceptable for this
bounded helper; this recommendation does not extend support to arbitrary dumps.
If broader inputs require general client emulation, reconsider the external-client
recipe rather than silently widening the supported profile.

Host adoption must be explicitly included in the Human's decision; moving its
historical hash record did not adopt it. Main integration and later Qualification/
release have not been performed by this review. A release is not part of the
requested decision.

## Pinned review and saved receipt

Reconstructed from the Human's CI follow-up and handoff: candidate
`e3c55ca14acd2e6813e8815bb96e4307b6b1d625`, base
`82877a2fc1d87d0d7cfe130c5467d3625bb6e16a`, branch
`experiment/dump-reader-productization`. Reviewed artifacts are the
[product contract](v06x-dump-reader-product-contract.md),
[previous adoption review](v06x-dump-reader-adoption-review.md) and
[CI handoff](v06x-dump-reader-ci-handoff.md) at that candidate.
This review was prepared on the candidate branch; the later evidence/documentation
commit is not relabeled as the tested source.

[CI40211613827](https://github.com/masahitojp/mariamem/actions/runs/40211613827)
passes all five jobs at exacte3c55ca. The
[saved assessment](v06x-dump-reader-evidence/ci-40211613827/assessment.json),
[run](v06x-dump-reader-evidence/ci-40211613827/run.json),
[jobs](v06x-dump-reader-evidence/ci-40211613827/jobs.json) and
[checksums](v06x-dump-reader-evidence/ci-40211613827/SHA256SUMS.json)
retain original source identity and artifact digests. Three ZIPs are stored
losslessly as base64 text to satisfy the public-source policy. Decode before
checking their original GitHub ZIP digest; checksums also cover the encoded files.
All three digests, source/tree bindings and report results were independently
verified. Earlier receipts remain bound to their original SHAs.

| Gate | Job | Result |
| --- | --- | --- |
| Native producer/reference and same-app data variant | 121223845814 | PASS |
| Installed wheel, Ubuntu x86_64, Python3.11/3.14 | 121224021805 | PASS |
| Installed wheel, macOS arm64, Python3.11/3.14 | 121224021813 | PASS |
| Full development checks | 121223845720 | PASS |
| Development integration | 121223845529 | PASS |

Four interpreter reports contain32 accepted route/scenario runs:16 positive
child test passes and24 accepted negative scenarios, plus four passing data-variant
imports. Raw reader SQL-failure events on all four boundaries preserve1146/42S02,
record closed/reaped/removed source cleanup, and admit no Snapshot or test.
Every saved binding is schema2/BOUND, matches the exact candidate Git tree, and
records fresh candidate production of the unchanged canonical dump.

## Previous conditions and detection net

| Condition | Judgment and evidence |
| --- | --- |
| Main/PR differential trigger and dependency selection | Satisfied as configuration and deterministic coverage: workflow lines3–36 selects main pushes and PRs; test_dump_ci_workflow.py checks migration, SDK, runtime/generated, producer/build inputs and negative trigger/path mutations. The new push run proves workflow execution, not delivery of a future main/PR event. |
| Continuing identity independent of old experiment diff | Satisfied: bind_input.py:22/76 verifies current clean commit/tree before and after input collection. test_dump_product_binding.py accepts a genuinely committed future runtime file in a temporary repository while rejecting dirty files, old SHA, tag object, abbreviation and receipt mutation. |
| Keep canonical corpus and producer provenance | Satisfied: bind_input.py:29/58 retains dump/manifest/migration/producer hashes and exact fresh producer receipts. The producer pin is the same original byte hash, without requiring an unrelated experiment Git object on future clones. |
| Keep current host and installed consumer binding | Satisfied: campaign.py checks packaged-host manifest hash and verify_go_binary; run.py also verifies host/source. test_git_identity.py retains wrong-source/compiler/dirty/missing/duplicate identity negatives and runs in the focused CI steps. |
| Explicit bounded API, modes, resource and discard rules | Satisfied within the finite supported profile. Product code/tests are unchanged from07c9d7e; the same installed-helper and finite mutation gates run on the new source. Limits are not performance claims. |
| Native semantics, routines, two children, failures | Satisfied by the newly saved matrix and raw failure events above. Original migration owner, routine definitions, engine/collation, exact rows and SQLSTATE/no-admission gates remain unchanged. |
| Separately assessed host prerequisite | Technically ready; Human adoption remains required. guest.go:68 accepts unsigned32 then projects low16, status_test.go rejects invalid/nested input and preserves flags; status_decode_test.go checks text/prepared packets. New full checks/integration pass; historical before/after hashes remain in the host delta record. |

The source diff from07c9d7e changes CI selection, binding and their tests, plus
reports/evidence. It contains no SDK/runtime/guest/generated/release input change.
The old six-file experiment allowlist was replaced with current identity and
behavior verification, not removed without a substitute. No SQL failure or
cleanup oracle was weakened. The previous two-part maintained-CI blocker is
closed for candidate adoption.

## Remaining limits and missing-things scan

No additional unsatisfied technical adoption condition was found in the prior
review/contract. Human acceptance of the host prerequisite and main adoption
remain decisions, not tests that a green CI can replace.

Actual main/PR event delivery and repository branch-protection requirements are
unverified. Static trigger mutations detect configuration loss, but cannot prove
GitHub event delivery or organization settings. This is not a reason to merge
without approval or to claim those events already ran: after authorized landing,
hand off the newly triggered main run normally. No required-check setting was
changed or claimed. The current branch is a main-based product candidate, not
the old design branch; do not merge design history wholesale.

No conflict was found in version-gated README/Go/Python/releasing guides. The
usage guide still calls this an unreleased candidate; after authorized adoption,
update that label to unreleased main as decision bookkeeping. Go has no new dump
API. No stale test-only description of the public helper was found. Historical
reviews and pre-CI handoff paragraphs remain historical; current project status
owns the new evidence and recommendation.

No generated ownership, HANDWRITTEN_FILES, canonical guest, release baseline,
release-note or version changes were found. No missing regeneration is inferred
for this unchanged guest/generated boundary. No opposite-platform run is missing.
No performance remeasurement, setup-cost claim or release readiness is asserted.
Views/triggers, other producer versions, MySQL/legacy/Django inputs, arbitrary
schema/routine shapes, privilege equivalence and large-input performance remain
outside the established evidence. The finite resource rejection tests do not
prove throughput/memory at the maximum file size. Parser maintenance risk remains
an accepted-scope question, not a measured cost saving.

## Next action and review verification

On explicit Human approval, adopt the smallest reviewed product candidate and
record host-prerequisite acceptance plus the main decision. Keep the tested SHA
and old receipts unchanged; metadata-only integration records are not new runtime
Qualification. Final target version, Qualification and publication stay separate.

This task saved evidence and updated current status/recommendation only. It did
not change code/tests/workflow, run runtime suites, rerun/supervise CI, integrate
main or release anything. Verification covered metadata, original artifact and
saved-file digests, schema2 source/tree bindings, raw failure events, candidate
diffs, references, public-source policy and whitespace checks.
