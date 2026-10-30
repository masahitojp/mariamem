# Usage-scope reconciliation before the versioned 0.6.0 candidate

Recommendation: adopt these usage-document corrections. They describe adopted
entries as supported, name accepted consumer exceptions, and keep excluded paths
outside the promise. This is a documentation decision, not release approval.
The strongest limitation is that there is no final versioned 0.6.0 candidate:
installation examples still target published v0.5.3. The exact versioned source
must receive the final wording/version/notes check described in
[releasing](../releasing.md#final-usage-scope-reconciliation-for-060).

## Fixed reviewed object

- Base: `1312055b904a67a5271e2c4daa54a51ac16f2f56`.
- Guide candidate: `873e8a1dd8d8f38eabc41ff7cd660e3b20143161`.
- The report-only descendant does not change those inspected guide bytes.
- Inputs reconstructed from the user's usage-alignment request: the
  [release scope](../decisions/v060-release-scope.md),
  [wire decision](../decisions/v060-wire-contract.md),
  [D1 decision](../decisions/d1-v060-deferral.md), and the adoption records linked
  below. This review checks documentation against existing evidence; it does
  not claim new execution or revalidate historical run results.

## Prior conditions and corrections

| Condition | Finding and correction | Evidence / detection |
| --- | --- | --- |
| Adopted entries are supported | Satisfied in the candidate. README names P1, routing, G1, owned E2E, bounded dump and ordinary Django. Python/Go guide intros distinguish the published baseline from adopted source additions. G1's stale first-checkpoint/pending-acceptance ending is removed. | [G1 adoption](v06x-go-fixture-acceptance-review.md), [P1 integration](v06x-p1-head-integration.md), [E2E conditions](../decisions/e2e-integration-conditions.md). Semantic staleness was invisible to existing docs CI. |
| Consumer exceptions are named | Satisfied. README/Python/Go name the native-matched macOS C-extension syntax-error presentation separately from CALL traversal and NUL projection. Ubuntu explicit-C unavailability is an additional-mode SKIP, not compatibility PASS. | [CALL/NUL decision](../decisions/prepared-consumer-exceptions.md), [syntax-error acceptance](v06x-prepared-product-design.md#c-extension-syntax-error). Existing execution evidence has narrower claims than blanket driver support; docs CI does not check the prose. |
| Wire exclusions imply no support | Satisfied in the inspected guides. TLS/compression, alternate auth, LOCAL INFILE, administrative commands, binlog/replication, server cursors, COM_RESET_CONNECTION and multi-packet continuation remain outside the declared profile. No new per-entry capture or capacity claim is made. | [Canonical wire decision](../decisions/v060-wire-contract.md#exact-set-and-evidence-interpretation). Documentation checks cannot establish runtime rejection or packet coverage. |
| Preparation and routing retain their boundary | Satisfied. Routing guide now includes PrepareCommand alongside None/callback, preserving ignored callback returns and rejection of other values. Preparation-time automatic routing remains excluded. | [Python command contract](../python.md#prepared-command-entry), [routing guide](../connection-routing.md). Runtime semantics are unchanged; no runtime test is claimed for this prose change. |
| Live/E2E are usable without implied automatic hooks | Satisfied. Routing no longer calls Live a future design task; guides link the supplied BrowserEntry/NewHTTP entries. Application readiness, quiescence, physical SQL/job retirement and stop/reap remain user hooks. Shared-Live parallel cases and session continuity are not promised. | [Owned examples and contract](../examples/e2e_owned/README.md), [Live](../live.md). Semantic alignment is manual; this task adds no hook execution evidence. |
| Django recipe does not imply D1 | Satisfied. Standard-runner support is explicit; prepared Snapshot restoration is deferred from 0.6.0 for consideration in 0.6.1, not promised for that version. | [D1 decision](../decisions/d1-v060-deferral.md), [Django guide](../django-testing.md). Existing standard-runner PASS is not D1 acceptance. |
| Dump/routines do not imply arbitrary import | Satisfied. DELIMITER is distinguished from server SQL and linked to the explicit Python-only bounded reader. The dump guide retains producer/size/definer limits and excludes views/triggers/events, arbitrary MySQL/legacy input and a Go dump API. Routine account metadata is not privilege enforcement. | [Dump format](../importing-dump.md), [routine scope](../decisions/routine-support-scope.md). No producer, parser or import was run. |
| Environment/resource limits remain bounded | No additional gap found in this audit. Python's Homebrew Python3.14/OpenSSL4 import constraint remains explicit, fixed driver versions are not universal compatibility, and helper budgets are not cold-setup or peak-resource guarantees. Resource work stays separate from the 0.6.0 wire objective. | [Python environment limits](../python.md), [G1 limits](../go-prepared-fixture.md), [scope correction](../decisions/v060-release-scope.md#subsequent-scope-correction-2026-10-30). OpenSSL3 CI cannot prove OpenSSL4 support. |

## Verification and remaining boundary

`python3 scripts/verify.py check --scope docs` passed: version consistency
(Python0.5.3 / Git v0.5.3), public-source boundary (6391 files), and diff whitespace.
A local target-file check covered 112 relative Markdown links in the 13 touched
guides; it did not validate anchors or remote URLs. These checks do not detect
incorrect support prose. The semantic reconciliation above supplies that review.

No runtime/API, guest, generated-source bookkeeping, baseline, release ledger,
workflow, test or installation command changed. No new adoption condition or
runtime defect was identified within the inspected guide set. Historical receipts
and decisions retain their source identities; no receipt was relabelled.

Outstanding: when the Human selects the final versioned candidate, reconcile its
metadata, install examples and versioned release notes with these same adopted
boundaries. The current source audit closes stale usage wording, not that future
candidate check, Qualification, publication, or new wire coverage. No new build,
benchmark or opposite-platform campaign is requested by these documentation edits.
