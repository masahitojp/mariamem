# P1 adoption gaps — closure before protected integration

Human follow-up, 2026-10-30: close the five stated gaps, then proceed through
PR26 on the strict current main base. This is P1 adoption follow-up, not a
resource investigation or release. Keep the candidate frozen after marking ready
so its final receipt refers to the submitted head.

| Gap | Correction / evidence | Remaining before integration |
| --- | --- | --- |
| No head receipt | Incorporate main's approved investigation policy, complete these corrections while Draft, then trigger a full Live matrix through ready_for_review. That run passed at head8912224a; the subsequent main PR34 changed CI policy and conflicted, so a new merged head requires one explicit manual full run. Save run/head/executed source and verify full tree equality if the PR executes a synthetic merge commit. Earlier b108abf1/7dde2266 results keep their original scope. Non-doc equality alone is not asserted to be full-tree equality. | Final head CI and receipt, then required PR contexts. |
| P1 contract status stale | entries[P1].status is FIXED_EXIT_ACCEPTED, bound to the existing b108abf1 receipt. Contract lint rejects stale status, missing/failed receipt or source mismatch. This records accepted functional evidence, not unmeasured current-head PASS. | No new status gap; final head evidence remains separately required. |
| Unconditional P1 CI cost | The initial p1 family gate was verified on head8912224a. Subsequent main PR34 removes the family selector and makes full acceptance manual-only. Preserve that newer policy: P1 native/wheel/venv/runtime steps run in explicit full acceptance, never automatically for unrelated PR/main updates. Daily protected source smoke remains separate. Tests require the manual-only trigger and both P1 steps. | Record the new manual head step cost; no measured automatic-PR saving is claimed. Do not launch another heavy campaign merely to demonstrate skipping. |
| Controlled capture failure evidence | Review explicitly identifies Python context-manager failure injection and controlled source closed state. It proves readable stage/original error, admission and public finalization, not reproduced internal guest capture failure or its cleanup. | Preserve that limit in adoption/usage claims. |
| Unreleased notes handoff | docs/releasing.md now requires manual transfer and reconciliation of the P1 API/admission/output/limits into versioned release/NOTES-* at the first applicable release. Staging notes state that release_prepare.py does not consume this path automatically. | Perform at an explicitly requested release; no version or release operation selected here. |

## Observed cost, not a saving estimate

At source `b108abf11a623c18c45adfab2968d357bf40718b`, the saved CI40987752495
jobs metadata records the P1 installed-consumer step as 127s on macOS15 and 161s
on Ubuntu24.04, including both Python minors. Whole host-job durations were
2231s and 2397s respectively. These are historical observed durations, not a
promise of wall-clock or cache-adjusted savings. PR34 supersedes the family selector: automatic PR/main events no longer launch
full P1 acceptance; explicit manual full runs still pay for it. Compare the new head's step/job durations from its receipt and
keep macOS runner pressure tracked with [#11](https://github.com/masahitojp/mariamem/issues/11).
No new timing threshold or resource-model gate is introduced.

The first Ready head8912224a / executed6ccec794 (full tree1ebecb6e) also passed:
P1 steps were142s macOS and157s Ubuntu; whole jobs1879s and1545s. Both P1 steps
were selected, so these are not measured savings from skipping P1. Preserve
that observation under CI41063375697; the post-PR34 manual head is a new cohort.

## Verification and stopping point

Use focused workflow/daily-selection/contract and P1 pytest controls for these changes.
Product runtime modules, guest and generated code are unchanged. The first Ready head passed CI41063375697; preserve its source/tree-bound
receipt on evidence/p1-head-41063375697 (commit441032c5). Main PR34 landed before
integration and caused workflow/selector conflicts. Resolve with its manual-only
full policy, then submit one manual full run for the new merged head. Daily
check/integration/Live required contexts must pass too; daily smoke does not
substitute for full installed consumers/native controls. Record the
actual submitted head and executed source, rather than inventing a future hash
inside this commit. Do not move head for receipt-only updates while checking it;
preserve that evidence and perform adoption bookkeeping after the exact-head
integration. Failures remain FAIL and get a new candidate/receipt when corrected.
After required checks and these five conditions pass, proceed with the authorized
protected integration; no admin bypass or release operation.


## Intervening main CI policy — PR34

Main `a18b247d91ac709cba550c7d0c623236ed541a31` landed after the Ready matrix.
It removes automatic full Live selection and introduces daily source smoke.
P1 adopts its workflow/gate semantics and removes the obsolete family selector
rather than restoring the old automatic matrix. P1 product modules are unchanged;
the manual native and installed-consumer blocks are retained. The first head's
success is historical evidence, not proof of the new merged CI/test tree. This
base update is the reason for a second full run, not an expanded P1 exit or a
new resource campaign. No further head changes are planned after submission.

Focused verification of the PR34 conflict resolution:314 CI workflow/daily
selection/contract/P1 pytest/G1 collector unit checks passed on local Python3.11;
version/public-source/diff checks also passed. A stale assertion requiring P1
unit tests in the unrelated public-Live step was moved to the dedicated P1 step,
preserving its actual coverage while retaining main's duplicate-work removal.
