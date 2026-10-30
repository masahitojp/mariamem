# P1 adoption gaps — closure under the current CI policy

Human follow-up, 2026-10-30: close the five stated gaps, then proceed through
PR26 on the strict current main base. Main subsequently adopted PR34 and PR35:
heavy feature acceptance is now Release CI only. Preserve that approved cost
tradeoff; do not restore automatic or standalone full acceptance to close P1.
This is integration work, not a resource investigation or a release request.

| Gap | Correction / evidence | Boundary still explicit |
| --- | --- | --- |
| No head receipt | Ready head8912224a passed CI41063375697, executed6ccec794, full tree1ebecb6e on both. Evidence is committed at441032c5 on evidence/p1-head-41063375697. PR34/PR35 then landed and changed CI/test inputs, so that is not relabelled as full PASS for the new merged head. Obtain fresh daily head checks/smoke; retain historical full evidence only for its actual unchanged P1 boundary. | New-head platform/native/browser full verification is deferred to Release CI by the subsequent Human-approved policy. No full-tree equivalence is claimed across the CI changes. |
| P1 contract status stale | entries[P1].status is FIXED_EXIT_ACCEPTED, bound to b108abf1's original successful receipt. Lint rejects stale status, missing/failed receipt and source mismatch. | Fixed-exit functional acceptance is distinct from new-head Release qualification. |
| Unconditional P1 CI cost | The initial p1 family selector was superseded by main's removal of all automatic full campaigns. P1 native/wheel/venv/runtime steps are retained in the reusable Release Live workflow only, using its source_commit checkout/SOURCE_COMMIT identity. They cannot run for ordinary unrelated PR/main events. | Historical observed costs below are not a measured saving. Daily success is source/smoke only; Release still pays for full P1. |
| Controlled capture evidence | Two capture cases inject Python context-manager errors and control source closed state. They prove stage/original-error reporting, admission and public-owner finalization. | They do not reproduce internal guest capture failures or prove internal cleanup. Readable-owned claims remain bounded accordingly. |
| Unreleased notes handoff | docs/releasing.md requires manually copying applicable P1 API/admission/output/limits into versioned release/NOTES-* and checking against adopted code; staging notes state their path is not automatically consumed. | Perform on the first explicitly requested applicable release; no version or Release operation is selected here. |

## Existing full receipt and observed cost

- CI40987752495 at b108abf1: P1 step127s macOS /161s Ubuntu; whole host jobs2231s
  /2397s. Each host/minor cell220 unit PASS,5 runtime PASS,4 deferred resource SKIP.
- Ready CI41063375697 at head `8912224a190c9d74d5059111a96da349b13b8ba1`, executed
  `6ccec79459665fd467263377217905cc3f01aae5`, full tree
  `1ebecb6ecc987f60fa093d3025066f0b1e47f909`: each cell224 unit PASS,5 runtime PASS,
 4 resource SKIP. Native3.11/3.14 PASS with schema_count_after0. P1 steps142s
  macOS /157s Ubuntu; whole jobs1879s /1545s. Both P1 steps ran, so these are not
  savings from skipping P1. Four ZIP digests,898 selected files and checksums are
  retained in [the evidence commit](https://github.com/masahitojp/mariamem/tree/441032c53dd7ff9ff14642a8363e50ffb9768a9e/docs/reviews/v06x-python-fixture-implementation-evidence/ci-41063375697).

Track macOS runner pressure with [#11](https://github.com/masahitojp/mariamem/issues/11).
No new performance threshold or resource-model gate is introduced.

## Intervening main updates and verification

PR34 main `a18b247d91ac709cba550c7d0c623236ed541a31` landed after the successful
Ready matrix and conflicted with the workflow/family selector. P1 incorporated
its manual-only policy at65d73405, retaining native and installed-consumer steps;
314 focused checks and version/public-source/diff checks passed. Push initially
received HTTP500, then succeeded; workflow dispatch attempts received HTTP500 and
created no new full run. Those attempts are not runtime FAIL or PASS receipts.

PR35 main `22383ecbd600b94ef33b29bf9991578dce8ca472` then reserved heavy acceptance
for reusable Release workflows. Incorporate it without restoring removed
triggers. Native P1 commands must use SOURCE_COMMIT, not the calling workflow's
GITHUB_SHA. Daily protected checks on the merged head are required before
integration. They do not replace or relabel historical full receipts.

Verify the P1 product modules, guest/generated/internal runtime and authored
P1 application/migration inputs remain unchanged from the successful Ready
head; record that limited reuse boundary explicitly. No full-tree equality
between the final merged head and the old Ready head is implied. Full validation
of the updated head is now owned by Release CI under the approved policy, not a
new adoption-time Release dispatch. Resource work remains v0.7.x.

Once source/smoke required checks pass and these bounded claims are recorded,
proceed with the authorized protected integration. Preserve pre-code approval
ancestry with a merge commit; no admin bypass, version, Qualification or publication.

The PR35 resolution passed277 focused CI publication/workflow/daily-selection,
contract/P1 pytest/G1 collector unit checks locally, plus YAML parse and
version/public-source/diff checks. `git diff --quiet 8912224a -- python internal
guest generated release tests/fixture_entry_acceptance
tests/preparation_migration_acceptance` confirmed the limited product/input
reuse boundary. The new reusable P1 native command binds SOURCE_COMMIT and both
candidate checkouts retain inputs.source_commit. No Release CI was dispatched.

Daily CI41073464491 at headaddef8e9 / executed14fcdad4 passed Ubuntu source smoke
but failed one source test (1497 passed,60 skipped): the P1 native workflow test
still expected caller GITHUB_SHA. The reusable workflow already correctly used
SOURCE_COMMIT. The test now requires the resolved SOURCE_COMMIT, forbids the
caller SHA and checks the input-bound checkout. The original failure/logs are
retained under ci-41073464491;158 related local checks passed after correction.
No runtime implementation or acceptance oracle was relaxed.
