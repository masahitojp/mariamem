# Seven fixture-scope review gaps — disposition and next gate

Historical review disposition at39f9757. The subsequent Human decision approved
G1 first with D1 nonblocking for v0.6.0; see the current
[scope and exception](v06x-dogfood-scope-draft.md#named-target-entries--approved-with-django-nonblocking).
The original review below is preserved; its mandatory-D1 concern and pending
approval statements describe that earlier proposal, not the current gate.

2026-10-28. Review corrections plus next Go API design, not implementation or
runtime acceptance. Source baseline is adopted main cc00ccd; exact SHA and
source hashes are in the [structured contract](v06x-fixture-acceptance.json).

| Review gap | Concrete correction | Detection and unfinished evidence |
| --- | --- | --- |
| 1. Unnamed entries | Scope draft names P1/G1/D1/EP1/EG1, fixed initial profiles, supported-host/minor matrix and G1-first delivery. D1 is a prepared-state obligation, not the already-adopted native-flush recipe relabelled. | Contract lint rejects missing/duplicate entries or whole-scope omission. Human review still must approve this exact five-entry scope. No current runtime PASS is claimed for these new entries. |
| 2. Missing time/resources | Three-time outcomes, edit counts, resource counters, fixed64-table input, caps1/2, four cases, Go -parallel1/4/-p1, xdist1/2, pool budgets, retention1/2/3, warmup/observed batches and finite guard ceilings are explicit. Count transient old/new Live children and process multiplication. | Lint rejects missing budgets/time/counters or changed input. Proposed default2/limits need API/measurement review; memory/FD and actual acquisition blocking remain future runtime obligations. No adaptive memory cap or16-slot change is authorized. |
| 3. Diagnostic inconsistency | Parent table and six exit criteria now evaluate the declared milestone profile. readable-owned targets entry-owned operations; basic-first is a scoped G1/EP1/EG1 milestone, never whole ideal completion. | Entry/profile mismatch and loss of core error/cleanup fields fail lint. Actual rendered error behavior needs component/runtime tests. The fallback is authorized conditionally but not activated. |
| 4. Capture consumption | Go acceptance/API table requires preserved rejection, accepted consumed failure, consumed success, partial backing unwind, combined errors and actual exactly-once disposal counts. Add invalid-but-not-disposed source control. | Root TestSnapshotOwnership/TestSnapshotFailures already cover source consume/error propagation. New helper tests must distinguish its owner actions, backend calls and temporary/backing cleanup; those tests cannot run before the helper exists. Closed alone cannot suppress public idempotent Close. |
| 5. Post-hoc stopping point | Commit the selected diagnostic profile and feasibility rationale before the first helper implementation commit; any downgrade needs a new prior decision. Pin the reviewed ancestor in implementation acceptance. | Lint rejects after-code timing, unrecorded fallback, false approval, or helper Go source in the current design-only tree. It does not itself prove future approval chronology: the approved-design ancestor/history check must be installed when authorizing implementation. The present artifact remains PROPOSED. |
| 6. E2E hook contract | Separate EP1/EG1 contract specifies StartReady, QuiesceAndRetire (including held admission and physical retirement), optional Resume and StopReap, partial startup, no-case-on-error, browser contexts and sequential-owner/concurrent-worker policy. | Lint checks required hook/retirement/admission/budget declarations. Actual hook order and failure controls remain future tests. Unregistered future background work cannot be detected from zero current sessions; do not promise it. |
| 7. Stale wire basis | New active inventory pins main cc00ccd and actual source/capabilities. Prepared, text multi-results and SET_OPTION are adopted; RESET_CONNECTION/FETCH/TLS/LOCAL INFILE and other open paths remain distinct. Old inventory is explicitly historical and redirects to the current one. | Lint compares current dispatch/capabilities and four source hashes to the actual pinned Git objects, rejecting stale/mutated source reconciliation. Existing runtime oracles are named; no new complete wire census is claimed. |

New tooling is [check_fixture_design.py](../../scripts/check_fixture_design.py)
with [negative-contract tests](../../tests/test_fixture_design_contract.py).
DESIGN_LINT_PASS only means the proposed contract is internally checked. It
explicitly reports runtime NOT_RUN and implementation_authorized=false.

The next work is now concrete: review the
[Go minimal API/ownership proposal](v06x-go-fixture-api-design.md) together with
the [named-entry scope](v06x-dogfood-scope-draft.md) and
[E2E hook contract](v06x-e2e-entry-contract.md). The principal material concern
is D1: ordinary Django flush is not prepared-seed restoration, so naming D1 as
mandatory commits future design/acceptance work. Do not quietly close v0.6 after
G1 or quietly omit D1. Recommended sequence is approve the target set and
G1's first implementation boundary, then implement G1 with its consume/cap/error
oracles and bounded resource observations. Other entry designs can progress
without implying their implementation or broad framework support.
