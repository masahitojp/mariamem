# P1 fixed-exit adoption review

2026-10-30. Decision needed: approve main adoption of the bounded Python
prepared-entry candidate. Recommendation: **approve**, followed by protected PR
integration. Users can declare preparation, obtain independent schema/seed per
test and understand preparation/cleanup failures; the fixed exit now has
source-bound both-host/minor evidence.

The strongest objection is that several capture/acquisition/combined-cleanup
failure controls use controlled owners rather than reproduced guest failures.
This limits what they prove. They exercise the new pytest/command boundary while
existing snapshot/session ownership controls cover the underlying operations;
actual installed consumers separately verify isolation, normal test failure,
connection retirement and final host/temp disposal. This matches the agreed
bounded contract, so it does not justify extending P1 into another resource or
fault-injection research project. Hard kill, escaped daemons and noncooperative
callbacks retain the documented limitations.

Specifically, the two new preserved/consumed capture cases inject an exception
at a Python context-manager boundary and control the source's closed flag. They
verify stage/original-error reporting, admission and public-owner finalization;
they do not reproduce an internal MariaDB/guest capture failure or prove that
failure's internal cleanup. The readable-owned claim is limited accordingly.

## Reviewed object and decision boundary

Reconstructed from the working branch, PR and prior Human decisions:

- Candidate/source_commit: `b108abf11a623c18c45adfab2968d357bf40718b`.
- Base/main: `80354f7b9e5c50e576fe9f040d4ee764200f6370`.
- Branch: `feature/p1-prepared-entry`; [PR26](https://github.com/masahitojp/mariamem/pull/26).
- [Pre-code public API/admission approval](../decisions/p1-prepared-entry-implementation.md),
  reviewed design `de860c4fc553907d237ad3a046ca6a6780ce0bb4`, decision commit
  `746ea5fb6306bb122659917681a2554a6a292e77`.
- [Fixed P1 exit and v0.7.x resource placement](../decisions/p1-fixed-exit-v060.md),
  and [condition/evidence reconciliation](v06x-p1-fixed-exit-reconciliation.md).

The product delta is four Python files, 471 additions / 18 deletions: public
PrepareCommand export, bounded command execution, worker-local owner bookkeeping
and supplied pytest fixtures. No guest/generated/internal runtime, wire or
release-ledger diff was found against the base. Source-bound evidence, tests,
guide and CI changes accompany the product. No new product dependency or Django
preparation routing is introduced.

This review recommends adoption; it does not record a Human adoption decision,
merge, Qualification, version selection or publication. Receipt/review/status-only
follow-up changes do not relabel the tested source above. Protected PR checks
must pass on the eventual integration head.

## Acceptance ledger

| Previously approved condition | Judgment and evidence / detector |
| --- | --- |
| None/callable/ignored return/overrides/no-marker; new declaration contract | SATISFIED. Both-minor P1 CI explicitly runs routing compatibility, PrepareCommand and pytest-entry controls. Env overlay/reserved actual endpoint, immutable copied declaration, invalid values and 16KiB output tails/truncation remain enforced. Notices in Python guide and unreleased notes are contract-checked. |
| Preparation once, exact starting schema/seed and independent children | SATISFIED. Four actual installed-wheel configurations per cell cover command/callback, reverse order, workers1/2 and ordinary failure; exact six-child JUnit and owner counts reject hidden skips or extra teardown errors. First/second/repeat time runs retain their own strict worker/batch oracles. |
| Readable failures, original + cleanup errors and worker-local admission stop | SATISFIED at the declared boundary. Real subprocess/pytest controls cover spawn/exit23/timeout/interrupt, invalid preparation, routing/disconnect, cleanup debt and other-worker continuation. New preserved/consumed capture rejection cases both pass. Unit/component owners are not presented as reproduced guest failure evidence. |
| Owned lifecycle cleanup, including partial/consumed owners | SATISFIED at lifecycle boundaries. Actual runtime checks require child/baseline/source close counts, disconnect, host reaped and scratch removed. Real-FD partial-owner controls verify closure; snapshot/session tests cover consumption, late/unreturned handles and interrupt reclamation. Full peak-resource census is not claimed. |
| Required-host/minor installed consumers, native input and usability/time | SATISFIED. macOS15 arm64 and Ubuntu24.04 x86_64, each Python3.11/3.14, have 220 unit PASS and 5 outer runtime PASS; four resource controls explicitly SKIP. Native command/callback references in both minors pass, schema_count_after=0. Exact module/host/input identity admission ran before use. Cold-machine and human-authoring time remain unmeasured. |
| Public documentation and one adoption review | Documentation/notice checks SATISFIED; this artifact completes the technical review. Human adoption and protected PR integration remain decisions/actions to perform. No broad framework/client coverage is inferred. |

## CI receipt and failure history

[CI40987752495](https://github.com/masahitojp/mariamem/actions/runs/40987752495)
attempt1 succeeded at the exact candidate. Scope, both native cells, both host
jobs and aggregate Live gate all succeeded. The [saved assessment](v06x-python-fixture-implementation-evidence/ci-40987752495/assessment.json)
contains job/artifact IDs, all four original GitHub ZIP digests, actual profile
results and the derived archive digest. The archive retains 898 original files
with inner checksums; outer SHA256SUMS.json protects the committed receipt.
Derived ZIP SHA256: `91a9d3245f6fbbdae5d86c1c9fb3ebbae7e00c28d6540bab3392bbf725f5ef12`.

The first candidate [CI40979625348](https://github.com/masahitojp/mariamem/actions/runs/40979625348)
failed three old tests requiring resource probe/guard/barrier suites in ordinary
P1 CI after the Human moved them to v0.7.x. Its original FAIL receipt remains
at source `4cc74f9a7f541afe96a958360eb60ac2fa77fb93`. The fix removes superseded
workflow obligations and centrally verifies the new exclusion/opt-in contract;
helper behavior tests and P1 lifecycle/failure controls remain. The passing run
is a new receipt, not a relabelled failure.

## Integration conditions and remaining boundaries

- At review time PR26 was Draft and MERGEABLE. Its PR-context Live gate was
  intentionally FAILURE under draft policy; the successful manual Live run is
  acceptance evidence, not a replacement for the required PR context.
- Main protection was reread: contexts `check`, `integration`, `Live required gate`;
  strict=true and enforce_admins=true. After adoption approval, use the ordinary
  ready PR path and satisfy all three contexts on the strict current base.
  No protection bypass or exploratory-history merge is recommended.
- Detailed resources/retention/continuous guards are DEFERRED to v0.7.x by Human
  decision, not missing P1 evidence and not PASS. No resource-model/capacity change
  is approved. Existing worker/connection budgets remain.
- Other dogfood entries, dbt, wire dispositions, Qualification and publication
  remain their separately tracked obligations. This review closes none of them.

No additional unmet P1 adoption condition was found. No new current-guide
contradiction, generated-source ownership change, release-ledger change or
unrecorded public API was found. Historic checkpoint text retains its original
scope, with current-status overrides. Review limits: bounded profile, selected
failure controls and existing CI evidence; no independent guest regeneration,
arbitrary framework, exhaustive fault census or performance claim was evaluated.
