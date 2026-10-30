# E2E v0.6.0 work sequencing after resource deferral

2026-10-30. Applies the existing [Human decision on fixed exit and resource
placement](https://github.com/masahitojp/mariamem/blob/4cc74f9a7f541afe96a958360eb60ac2fa77fb93/docs/decisions/p1-fixed-exit-v060.md) and the Human's request to reorganize this E2E work.
That decision explicitly moves detailed resource characterization out of P1,
other fixture entries and v0.6.0 prerequisites. This is alignment with that
decision, not a new waiver of lifecycle correctness or approval of adoption.

## v0.6.0 boundary

EP1 BrowserEntry and EG1 NewHTTP/Case remain required. Preserve preparation,
schema/seed isolation, stable application/Live identity, exclusive admission,
the supplied quiescence/physical-retirement hooks, original failure reporting,
cleanup-debt admission stop, partial-owner retention and confirmed owned cleanup.
Keep the declared independent-owner and connection budgets, supported-host/minor
installed consumers, fixed native inputs, user-facing first/second-test and
repeat usability/timing evidence, and documentation/adoption review.

Detailed retained-baseline1/2/3 characterization, aligned peak RSS/FD/session/temp
census, resource guard campaigns, continuous observation and tuning belong to
shared Snapshot/runtime work in v0.7.x. They are deferred, not PASS. They do not
block v0.6.0; observed leaks, failed cleanup or invalid admission still do.
Historical scope drafts and receipts retain their original context. This decision
supersedes their resource-campaign prerequisite for current completion tracking.

## Work ownership and execution order

[Issue #18](https://github.com/masahitojp/mariamem/issues/18) owns the checklist;
[the current evidence map](../reviews/e2e-entry-acceptance-map.md) maps its rows.

1. Repair publication of saved evidence and check wording, references, digests
   and the public-source boundary. Do not repeat runtime tests for this edit.
2. Reconcile functional evidence against the finite rows in the map. Reuse
   source-bound results within their actual scope. Name any missing oracle before
   adding a test; component evidence cannot silently become physical-fault proof.
3. Complete only the named functional/usability gaps, including independent
   owners and the remaining lifecycle-boundary checks. No peak-resource collector
   or new instrumentation is required for these tests.
4. Submit the final candidate to existing supported-host/minor checks, preserve
   its receipt and produce one adoption review. Main integration follows the
   Human's adoption decision; release approval is separate.

P1 PR #26 owns pytest/PrepareCommand compatibility and worker admission. E2E
PR #28 owns browser/HTTP application hooks and case lifecycles. Each retains its
entry-specific correctness evidence; detailed resource characterization is a
shared v0.7.x topic, not two parallel v0.6.0 campaigns. No other worker has been
contacted or assigned work by this reconciliation. D1 and dbt keep their existing
owners and dispositions.

## Preserved, unsubmitted resource prototype

The local prototype source_commit
`3e59bce087b7a4e88d4b07a0cd6dfe63500c31dd` adds the e2ecampaign observation tag,
host observation points and an EG1 runner. It is preserved locally under
`archive/e2e-resource-campaign-v07`, outside PR #28. The resource campaign was
not executed. Its instrumentation unit checks are not measurement results.
The promised macOS FD-enumeration change was only probed, not implemented.
No adoption/readiness is claimed for this prototype. Reuse in v0.7.x requires
review of its necessity and observer effects, not automatic integration.
