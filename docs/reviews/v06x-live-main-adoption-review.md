# Live main adoption review after CI40417099015

Decision under review: adopt the selected bounded Live candidate on main.
Recommend **holding integration until the correction candidate's fresh CI passes
and the Live required check is activated at adoption**. The tested runtime is
unchanged and both-platform usage evidence is sound; the new mandatory-check
wiring itself has not yet run on GitHub. The strongest objection to another run
is cost for unchanged product code. One bounded run is justified because the
changed dependency/skip/aggregate path now controls whether incomplete acceptance
can be merged. No independent guest regeneration, benchmark or release qualification campaign
is added to this review task.

## Fixed review inputs

The Human requested continuing adoption review and correcting three gaps. The
object and decision are reconstructed from that instruction and repository state:

- Reviewed report: docs/reviews/v06x-live-main-candidate.md at source_commit
  `ef4ff798ac677b7649f8a4c5a7b2ce53a66c888a`.
- CI candidate: `6edcd29e65d3a669d5be6520abf6be2e61fa3445`.
- Stable base: `bf3a29c292064ddbbd4c7b9a9c6e712504d0f4e4`.
- Correction candidate: `1699c9ec73d7e9a6bcf5ede540db1ffd585fa7b6`,
  experiment/live-review-fixes. This review/status follow-up only changes docs.
- Prior F1/F2/F3 conditions: [adoption review at c718344](https://github.com/masahitojp/mariamem/blob/c71834493ad2742100e1ee96da853b237c5b4abe/docs/reviews/v06x-live-host-adoption-review.md).
- Evidence: [CI receipt and validator](v06x-live-main-evidence/ci-40417099015/README.md),
  [correction evidence and policy readback](v06x-live-review-fixes/README.md).

A single authenticated run metadata read reconfirms
[CI40417099015](https://github.com/masahitojp/mariamem/actions/runs/40417099015)
completed successfully on exact6edcd29. Saved source/job/artifact binding, all four
original ZIP digests and raw observation predicates were revalidated. No CI was
rerun or supervised during review. The subsequent authorized correction is a
new candidate and needs its own receipt; the old receipt is not relabelled.

## Conditions and detection net

| Condition | Conclusion | Evidence / detection |
| --- | --- | --- |
| F1 maintained main/PR Live acceptance | Trigger coverage satisfied on6ed; correction aggregate requires fresh CI | live-host.yml now always emits Live required gate; scripts/live_ci.py:17 selects unknown inputs; :21 rejects incomplete dependencies. tests/test_live_ci_workflow.py covers prior dependency paths,9 workflow mutations and24 result-state combinations |
| F2 actual-adapter disposal retries | Satisfied for reviewed bounded cases | CI live-race.txt includes internal/live, internal/control and public Go; prior local old-adapter/old-endpoint overlays fail. No runtime delta from6ed |
| F3 selected production diff / current-source guides | Satisfied | selection manifest pins base/source paths; no exploratory history merge; public docs retain published v0.5.3 boundary |
| OpenSSL4 contributor guidance | Addressed | docs/development.md:87 and docs/python.md:243 explain standalone import failure, versions, reporting and fixed-profile checks; OpenSSL3 CI cannot detect this environment |
| Repository enforcement | Applied for existing checks; Live activation outstanding until adoption | protection-readback.json verifies check/integration, strict=true, app15368 and enforce_admins. protection-with-live.json is an unapplied payload. Ordinary CI does not audit external policy drift |
| Interrupted existing request operations | Addressed at Python framed-control boundary | tests/test_owned_snapshot_unit.py:272 covers6 operations ×2 reply phases, exact close counts, retained sibling/baseline handles, pending/ref settlement and final reap. Both Python versions pass99 focused cases. Missing-cleanup and duplicate-close mutations each fail6 cases per interpreter |

The local test harness initially interrupted background disposal too; corrected
fault injection targets only the caller. Strict reruns treat unhandled thread
warnings as errors and pass without warnings. Original diagnostic outputs remain
in the archive. These are actual subprocess protocol/SDK ownership tests with a
fake host; they do not establish interruption safety at every native SQL/engine
execution point. Product Python/Go, guest and generated runtime remain byte
identical to6ed; no runtime fix was required by these tests.

The aggregate runs for every main push/PR. Only six explicitly named guides may
skip expensive jobs. Unknown inputs, empty/unavailable diffs, workflow/manual
runs with no base and relevant code/test inputs select the full matrix. Unit
coverage checks expected skips and failure/cancellation paths; a guide-only
GitHub skip has not been observed in this task. This is narrower than claiming
all workflow branches have live CI evidence.

Repository protection is a separate administrative observation, not a CI
conclusion. GitHub documents that [filtered-out workflows can leave required
checks pending](https://docs.github.com/en/pull-requests/how-tos/merge-and-close-pull-requests/troubleshooting-required-status-checks).
The always-reported aggregate avoids requiring the old path-filtered matrix
contexts. At adoption, re-read protection, preserve intervening settings and add
Live required gate with the saved payload; read it back before declaring the
policy condition closed. Admin enforcement is already active for existing checks.

## Missing-things scan

No additional usage/version contradiction was found: README, Go/Python guides
and Live guide distinguish current-source candidate from published v0.5.3.
No guest patch, generated file/ownership, dependency, release baseline, version
or release-ledger delta was found. No corresponding regeneration work is claimed.
No stale product comment requiring a runtime change was identified in this diff.

The authored Go/Python E2E, fresh Ubuntu MariaDB12.3.3 reference, both guest host
platforms, Python3.11/3.14 and installed default-Python/external-Go boundaries have
exact6ed evidence. Local OpenSSL4 retains its original integration FAIL; CI does
not repair or qualify it. Cold/setup cost and performance were not measured.
Broader Django adapter compatibility and independent example studies remain
separate work. Caller quiescence, retiring physical connections, sequential reset
and parent lifetime remain required; SQL session continuity and delayed-job
fencing are not claimed. No mixed release/adoption decision is introduced.

## Next bounded action and stopping point

Submit the correction candidate's exact final source to the existing native +
both-host Live matrix, now including scope/required jobs. Preserve its own receipt
and verify the new aggregate as well as existing gates. After PASS, the Human can
decide main adoption; activate/read back the Live required context as part of that
approved integration. Do not bypass the now-active check/integration protection.
Qualification and release remain later Human decisions.
