# EP1 / EG1 bounded v0.6.0 adoption review

Decision requested: adopt the bounded Python BrowserEntry and Go NewHTTP/Case
candidate for main integration. Recommend adoption: the saved source-bound
assessment has been replayed, and the fixed applications, installed
consumers and the previously named lifecycle/isolation gaps passed both supported
hosts. This decision does not approve publication or complete other dogfood entries.

The strongest objection is that correct application hooks remain essential:
quiescence cannot discover arbitrary future jobs, lying routing hooks or unknown
pools. Some failure paths use controlled owners/backends rather than physical
engine fault injection. Accept the documented fixed profiles and explicit hook
responsibility, not universal application isolation. The actual Python/Go Busy
controls demonstrate that an existing physical session cannot be hidden by a nil
hook result. That combination is sufficient for the selected bounded contract;
a failing declared-profile control would reverse this recommendation.

## Pinned review object

- Executed candidate source_commit:
  `edfee47807cc7ad76aed798947ba70af0a7fb2c9`.
- Adopted-main comparison base inferred from the candidate history:
  `80354f7b9e5c50e576fe9f040d4ee764200f6370`. This is a pinned comparison,
  not an assertion about today's remote main.
- Candidate branch: `feature/e2e-owned-entry`, PR #28. The evidence/report commit
  is a documentation-only descendant; it is not relabelled as the executed SHA.
- [CI41058866706](https://github.com/masahitojp/mariamem/actions/runs/41058866706):
  manual event, both native minors, both Live hosts and required gate SUCCESS.
- [Saved source-bound evidence](e2e-ci-41058866706/assessment.json), including
  complete artifact ZIP digests and published-file hashes.

The review inputs and decision to request were reconstructed from #18,
[the pre-code authorization](../decisions/e2e-entry-implementation.md),
[current sequencing](../decisions/e2e-v060-work-sequencing.md) and
[the accepted E2E hook contract](v06x-e2e-entry-contract.md). This is the fixed
v0.6.0 exit after the Human's shared v0.7.x resource deferral, not the superseded
full resource campaign.

## Conditions and detection

| Retained condition | Evidence / current oracle | Judgment at executed source |
| --- | --- | --- |
| Probe result before implementation | Decision ancestor3ead1bc8; `tests/test_e2e_decision.py` checks source/result identities and absence of product files there | Satisfied; preserve this ancestry when integrating |
| Preparation, per-case reset and stable identities | `python/mariamem/e2e.py:110`, `mariamemtest/http.go:297`; fixed orders tests and installed consumers | Satisfied for declared profiles |
| Actual independent owners, reverse order and no cross-owner mutation | Python `test_independent.py:18`; Go `independent_test.go:14`; both owners have distinct app/endpoint identities, and a second Reset preserves the active first owner's mutation | Satisfied; interleaved simultaneously active owners, not a scheduler stress test |
| Ordinary assertion/Fatal continuation | Actual Python assertion then fresh seed in `test_independent.py:35`; Go Fatal subprocess and cleanup/next-case oracle in `mariamemtest/http_test.go` | Satisfied at the stated actual-Python / controlled-Go boundaries |
| Physical retirement and registered-job obligation | Actual Python `test_retirement.py:62` and `:78`; Go `TestHTTPPhysical*`, real registered transaction/join controls | Satisfied for the controlled hooks; negative cases keep Busy/generation/no-admission outcomes |
| Setup/cleanup debt, Reset/Resume/external-state failures and partial owners | `tests/test_e2e_entry.py`; `TestHTTPFailureLatches`, partial-start/Live and cleanup-panic controls | Satisfied at controlled error boundaries; not every real engine I/O fault |
| Case resource disposal, close wait and independent cleanup context | Python component tests at102/129/248; Go tracked HTTP body/Fatal/canceled-case controls; app stop before DB owners | Satisfied; cooperative shutdown and timeout uncertainty remain explicit |
| Supported source/installed profiles | macOS15 arm64 and Ubuntu24.04 x86_64; Python3.11/3.14; Go1.26.10; installed default host/external private module receipts | Satisfied for candidate source; no public package publication claimed |
| First/second/repeat usability evidence | `scripts/e2e_workflow_timing.py:28-65` pins minimal case-name edits and verifies case census; four Python cells plus Go on each host | Satisfied for bounded command wall times; no human-authoring/cold-machine/isolated Reset latency claims |
| Native/fixed application regression | Existing native3.11/3.14 references, fixed inputs and Live regression/defect steps in successful workflow | Satisfied as unchanged workload anchors, not automatic native equivalence of arbitrary hooks |

Expected negative subprocess failures remain in the raw Go physical logs. A
passing outer oracle does not turn those intentional child failures into success.
The case/client setup and cleanup checks are selected by the existing workflow;
new independent and retirement files are explicitly selected. The ordinary check
alone skips opt-in runtime tests, so that check alone could not certify them.

## Gaps, limits and non-gaps

No additional violated retained condition was found in this bounded review.
The unresolved scope limits below are not silently satisfied:

- Arbitrary delayed/unregistered work and wrong-target hooks can escape the
  supplied hook boundary. CI proves the fixed hooks and named mutants, not every
  user hook. The guide states this responsibility; the independent Live drain
  can detect current physical sessions but cannot infer future application work.
- Hard-kill/machine loss and non-cooperative shutdown are outside the contract.
  Cleanup errors/timeouts remain failures or uncertainty; no forced reclamation
  is inferred from a returned error. Controlled fault tests detect masking and
  invalid admission; they cannot prove termination of arbitrary user code.
- Peak-resource/retained-baseline/guard characterization is deferred to shared
  v0.7.x by the existing Human decision. Those results remain unmeasured and are
  not a missing v0.6.0 acceptance condition.
- Usage guides correctly call this a candidate before adoption. The old example
  README's resource-prerequisite sentence is corrected in this report-only
  descendant to match the already approved sequencing.
- No guest/generated/Live implementation, generation inventory, Go module inputs,
  release baseline/version or notes changes occur relative to the pinned base.
  Corresponding-source checks and canonical integration pass in this CI; there
  is no need for an independent regeneration for this entry change.
- Main integration, required PR contexts after readiness, other dogfood entries,
  final Qualification, Product Validation and publication remain outstanding.
  Manual CI evidence is not a bypass of branch protection or a release result.

## Integration recommendation and review limits

Ask the Human for the bounded candidate adoption decision. After approval, bring
the candidate into the current main context, retain pre-code decision ancestry
(a merge preserving history satisfies the existing checker), and pass required
candidate checks before integration. If integration changes product/test inputs,
bind new evidence to that actual source. Do not silently squash away the required
ancestor or reuse the old artifact as a new-SHA receipt.

Review covered the new ownership/admission code, focused failure tests, fixed
examples, installed/CI selection, current scope and saved results. It did not
perform a new experiment, resource characterization, arbitrary-framework audit,
release qualification or a review of separately owned P1/D1/dbt work.
