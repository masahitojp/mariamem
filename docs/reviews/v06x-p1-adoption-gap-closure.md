# P1 adoption gaps — closure before protected integration

Human follow-up, 2026-10-30: close the five stated gaps, then proceed through
PR26 on the strict current main base. This is P1 adoption follow-up, not a
resource investigation or release. Keep the candidate frozen after marking ready
so its final receipt refers to the submitted head.

| Gap | Correction / evidence | Remaining before integration |
| --- | --- | --- |
| No head receipt | Incorporate main's approved investigation policy, complete these corrections while Draft, then trigger exactly one full Live matrix through ready_for_review. Save run/head/executed source and verify full tree equality if the PR executes a synthetic merge commit. Earlier b108abf1/7dde2266 results keep their original scope. Non-doc equality alone is not asserted to be full-tree equality. | Final head CI and receipt, then required PR contexts. |
| P1 contract status stale | entries[P1].status is FIXED_EXIT_ACCEPTED, bound to the existing b108abf1 receipt. Contract lint rejects stale status, missing/failed receipt or source mismatch. This records accepted functional evidence, not unmeasured current-head PASS. | No new status gap; final head evidence remains separately required. |
| Unconditional P1 CI cost | Add p1 to the existing family selector, gate both native P1 and installed-wheel P1 steps on it. P1/routing/shared/unknown inputs retain P1; unrelated Go-helper/Live-only PR inputs omit it; main/manual/unavailable diff remain full. Tests cover dependency selection, unions, conservative fallback, output export and both workflow conditions. | Observe the selected head run; real unrelated-PR skip has not yet been observed. Do not launch another heavy campaign merely to demonstrate skipping. |
| Controlled capture failure evidence | Review explicitly identifies Python context-manager failure injection and controlled source closed state. It proves readable stage/original error, admission and public finalization, not reproduced internal guest capture failure or its cleanup. | Preserve that limit in adoption/usage claims. |
| Unreleased notes handoff | docs/releasing.md now requires manual transfer and reconciliation of the P1 API/admission/output/limits into versioned release/NOTES-* at the first applicable release. Staging notes state that release_prepare.py does not consume this path automatically. | Perform at an explicitly requested release; no version or release operation selected here. |

## Observed cost, not a saving estimate

At source `b108abf11a623c18c45adfab2968d357bf40718b`, the saved CI40987752495
jobs metadata records the P1 installed-consumer step as 127s on macOS15 and 161s
on Ubuntu24.04, including both Python minors. Whole host-job durations were
2231s and 2397s respectively. These are historical observed durations, not a
promise of wall-clock or cache-adjusted savings. The new selector avoids the P1
step on unrelated selected PR families; shared/policy inputs and main/manual
still pay for it. Compare the new head's step/job durations from its receipt and
keep macOS runner pressure tracked with [#11](https://github.com/masahitojp/mariamem/issues/11).
No new timing threshold or resource-model gate is introduced.

## Verification and stopping point

Use focused selector/workflow/contract and P1 pytest controls for these changes.
Product runtime modules, guest and generated code are unchanged. Push while
Draft, then mark Ready once to obtain head-bound installed consumers/native
controls and the strict required check/integration/Live contexts. Record the
actual submitted head and executed source, rather than inventing a future hash
inside this commit. Do not move head for receipt-only updates while checking it;
preserve that evidence and perform adoption bookkeeping after the exact-head
integration. Failures remain FAIL and get a new candidate/receipt when corrected.
After required checks and these five conditions pass, proceed with the authorized
protected integration; no admin bypass or release operation.
