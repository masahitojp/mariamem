# P1 — protected main integration complete

Adopted 2026-10-31 JST. The Human authorized closing the five adoption gaps and
proceeding with protected integration. PR26 merged at2026-10-30T15:13:26Z:

- Main merge: `4a8a68350e8c43fc107843a6efe7781cad1a4e2a`.
- Approved head: `850ddcc2c70786dc310308d262b4f33d842fea3e`.
- Actual daily CI checkout: `0f59d660e5ca58a65818915602787fec5e7e57d3`.
- All three full repository trees: `e09c9c8f3300b5ca716e1776da4676ada01f3e94`.

A normal merge commit preserves the pre-code approval746ea5f required by the
contract's ancestor check. Required check/integration/Live required gate passed;
strict=true and admin enforcement stayed enabled. No protection bypass, version,
Release CI, Qualification or publication operation was performed.

## Two evidence scopes, kept separate

| Receipt | Source identity | What it proves |
| --- | --- | --- |
| [Full Ready acceptance41063375697](https://github.com/masahitojp/mariamem/actions/runs/41063375697) | Head8912224a / actual6ccec794; matching full tree1ebecb6e | macOS15/Ubuntu24.04 × Python3.11/3.14: each224 unit PASS,5 outer runtime PASS,4 deferred resource SKIP; both native P1 references PASS/schema_count_after0. Historical full P1 profile, not full PASS for the subsequent CI-policy tree. |
| [Final head daily41076760360](https://github.com/masahitojp/mariamem/actions/runs/41076760360) | Head850ddcc2 / actual0f59d660 / main4a8a6835; matching full treee09c9c8f | Current source/unit checks and Ubuntu Go/Python source smoke: actual DB/Snapshot/Fork and Live controls, including source consumption, busy/closed-parent refusals and Python host/directory cleanup. All3 protected contexts SUCCESS. No current-head macOS/native/browser/installed qualification claim. |

Full raw P1/native files, all4 original ZIP digests and inner/outer checksums:
[evidence441032c5](https://github.com/masahitojp/mariamem/tree/441032c53dd7ff9ff14642a8363e50ffb9768a9e/docs/reviews/v06x-python-fixture-implementation-evidence/ci-41063375697).
Final daily raw logs, metadata, smoke payloads and checksums:
[evidence9069e790](https://github.com/masahitojp/mariamem/tree/9069e7904d3e2f756833976691d1ba298f3ab77e/docs/reviews/v06x-python-fixture-implementation-evidence/ci-41076760360).
Keep the pushed evidence/p1-head-41063375697 and evidence/p1-daily-41076760360
refs: they preserve compact unique evidence and the actual CI source commits.
They were kept outside the frozen PR head, avoiding a receipt-only head change.

P1 product modules, root Go/runtime/generated/guest/release inputs and authored
P1 migration/application inputs are byte-identical to the successful Ready head.
CI/test/documentation trees changed, so no full-tree reuse across those updates
is asserted. Main PR34/35/36 explicitly moved heavy verification to Release CI
only and consolidated daily source checks/smoke. The final head follows that
approved cost tradeoff. New-head both-host/native/browser/installed verification
remains NOT_RUN until an explicitly requested Release transaction; no independent
adoption-time full ceremony or Release request is introduced here.

## Five-gap disposition

1. **Head receipt:** successful Ready full receipt retained at its exact head;
   final daily head/actual checkout/main tree equality and successful protected
   checks separately recorded under the intervening approved CI policy.
2. **Contract state:** P1 is FIXED_EXIT_ACCEPTED, bound to the original successful
   b108abf1 receipt. Lint rejects stale status and absent/failed/source-mismatched
   evidence; it does not grant fresh runtime qualification.
3. **CI cost:** P1 native/wheel/two-venv/runtime campaigns now exist only in the
   reusable Release Live workflow. Ordinary PR/main events cannot invoke them.
   Observed old P1 step durations127/161s and Ready-head142/157s remain historical
   macOS/Ubuntu observations, not a measured saving or resource-model claim.
4. **Capture failures:** preserved/consumed cases inject Python context-manager
   errors and source closed state. They verify entry diagnostics/admission/public
   finalization, not reproduced guest-internal capture harm or internal cleanup.
5. **Notes:** docs/releasing.md requires manually carrying staged P1 notes into
   versioned release/NOTES-* and reconciling against adopted code. The staging
   path is not automatically consumed. This handoff occurs at a requested release.

The source-only failed run41073464491 (one stale GITHUB_SHA expectation,
1497 passed/60 skipped; source smoke PASS) remains in main's checksummed evidence.
The guard was corrected to resolved SOURCE_COMMIT plus input-bound checkout.
An intermediate run41076021533 was superseded when PR36 changed the strict base;
no successful receipt is inferred from its cancellation. Historical successes
and failures are not relabelled.

P1's main-adoption work is complete. Other named dogfood entries, independent dbt,
wire dispositions and later version/Qualification/publication remain separate.
Detailed resources remain v0.7.x; entry-owned cleanup guarantees remain in force.
