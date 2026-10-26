# Review of the revised v0.6.x dogfood schedule

Decision now: use the revised framework-plus-E2E schedule to organize the next
investigations, beginning with Django/application/topology input selection and
lifecycle discovery. **Recommend this order.** Ordinary ORM tests cannot show
whether an independently running Web application can retain its process while
each browser test starts from the same committed baseline; the revised plan now
makes that a separate required investigation. The strongest objection is scope:
adding a browser, a live design and a worker could turn Django integration into
an unbounded platform project. The plan controls this through one shared app,
separate workload manifests, explicit L1/L2/L3 decisions and reviewed finite
experiments, while allowing existing-code guides and ordinary resource observations
to proceed independently. Worker/tool selection is still work, not established
support or permission to build every extension.

This recommends a planning direction. It does not approve a live implementation,
choose a public Django API, or authorize the full experiment matrix. Source-level
Django investigation was already requested; the next useful deliverable is its
concrete input/lifecycle manifest, not another implementation approval inferred
from this report.

## Reviewed object

The Human requested replanning with explicit E2E/live coverage, then review.
Reconstructed source base: `bf3a29c292064ddbbd4c7b9a9c6e712504d0f4e4` (main).
Reviewed plan: `8e283754f4df31635224160fa4bd194360da9e13`,
`docs/reviews/v06x-dogfood-replanned.md`, branch `design/v06x-dogfood-e2e-plan`.
This is a pinned plan review, not new runtime/candidate acceptance.

Cross-checks: project-status.md:693–735/1107–1165, the capability map A–N,
shadow-maria-entry-design.md:31–111, connection-routing-contract.md:19–81,
Snapshot lifecycle contract and existing consumer/preparation/import test owners.
References below use the plan SHA or the unchanged main source basis; later
review/status documentation does not replace that identity.

## Prior directions and current coverage

| Condition | Judgment / evidence |
| --- | --- |
| Preserve full capability space before selecting samples | Satisfied as a plan. Workload rows W1–W8 at plan:36–56 and A–N closure mapping at183–203 retain framework, import, resource, compatibility, diagnosis, live and cross-run/control decisions. Older capability-map claims about absent prepared/import/routing are historical; plan:22–29 uses current adopted foundations. |
| Include ordinary Django tests and real long-lived browser E2E | Satisfied as separate targets W3/W4 at42–43, with a separate Web process and actual browser, same app process across A/B and commit-visible isolation. Plan:119–122 explicitly prevents an in-process Django client from satisfying W4. |
| Keep worker/multiple-connection use visible | Satisfied as W5 at44, including delayed/retried jobs and drain/late-writer oracle at149–150. Implementation/queue selection is intentionally unresolved. |
| Live has an explicit resource contract and0.6.0 decision | Satisfied as planning. L1/L2/L3 at90–104 preserve the three distinctions from entry-design.md:98–111. P2b/P3 require a bounded design/experiment before implementation; stable endpoint alone does not imply session preservation. |
| Existing Snapshot and preparation boundaries remain | Satisfied. Plan:83–89 records startup preparation/capture conflicts;134–143 preserves no partial baseline/test admission and explicit preparation settings. pytest_plugin.py:117–129 waits for disconnection, consumes the source and forks children; this is not an already working live primitive. |
| Keep parallel/resource and guide work independent of live | Satisfied. Plan:74–81 allows ordinary W8 and guide work alongside P1/P2;164–181 separates effort/cold setup/resource observations from optimization promises. Existing16-connection limit and v0.7 tuning decisions are preserved. |
| Do not call record-writing or old green CI new dogfood PASS | Satisfied. Plan:20–34 and205–218 distinguish anchors, future manifests, experiments and completion. No new OS/browser/framework campaign is claimed. |

## Missing inputs and detection net

No blocker to adopting this planning direction was found. The following are
execution prerequisites, not satisfied runtime conditions:

| Remaining input / possible mistake | What detects it now | Required next artifact |
| --- | --- | --- |
| Concrete Django project/version/driver and chosen test runner; treating TestCase, TransactionTestCase and pytest-django as equivalent | Existing tests do not exercise those Django lifecycles. pytest_plugin.py:20–22 refuses live/shared marker arguments but cannot validate Django setup/flush semantics | P0/P1: pin app and runner, trace class/test/setup/teardown and alias/connection ownership; retain each unexecuted runner as unverified rather than claiming all work |
| Real separate Web process/browser topology and baseline-capture point | Current SQLAlchemy/GORM, migration and dump tests are not browser E2E detectors. A green current CI cannot detect a silently restarted Web process or prove fixed-endpoint reset | Manifest and independent PID/start-count, endpoint/backend-generation, browser state, seed and commit observations; planned restart/skipped-reset/stale-connection mutations must actually be detected in the later spike |
| Worker/queue choice and safe job boundary | Existing CI has no W5 job-generation/drain detector. Waiting for an arbitrary sleep would not establish quiescence | Separate W5 input/ownership/retry/drain manifest and delayed-job negative case; no generic queue promise |
| Metadata-heavy/dbt-like tool and project | Existing ORM introspection is useful evidence, not proof of an actual dbt-like tool | Pin one concrete tool/input/entry point at P0; keep W7 open until exercised or explicitly disposed |
| Platform/browser/interpreter cells and execution resource/time budget | Existing native CI covers its own exact sources/clients, not new browser binaries or all combinations | Per-execution mandatory/diagnostic/unverified cells, source/executable identities and finite timeout/storage/resource limits; no invented dates or universal resource ceiling |
| First/second-test usability or setup-cost benefit inferred from correctness | Existing pass/fail tests cannot measure learning burden, clean-machine install cost or maintenance savings | Reproducible walkthrough/step records and properly labeled warm/cold measurements where requested; no numerical benefit before evidence |

The distinction matters: source discovery and manifest authoring can start now;
new runtime experiments require their concrete inputs/budget and applicable design
review. The next manifest must separate runtime discovery from the native control
and from a later guest/live spike, so execution does not start by implication.

## Dependency judgment

P0/P1 feeds both the Django adapter choice and the live contract. P2a is not a
universal prerequisite for P2b; only shared framework hooks create that dependency.
W5 follows the selected W4 contract. Ordinary Go/Python W8 observations and the
serial/parallel guide do not wait for a new live API. W7 selection can proceed
independently. This avoids turning E2E's inclusion into a serial blocker for all
v0.6 work. These are proposed task dependencies, not measured completion dates.

The plan's P6 closure requires evidence/limits or a Human-agreed disposition for
every workload/axis. It therefore cannot quietly drop E2E or a worker because a
Django ORM adapter is easier. Nor does inclusion in this plan guarantee shipping
every capability in0.6.0; that scope decision remains explicit.

## Missing-things scan and next action

No changed runtime/API contract, version-gated README/Go/Python/releasing guide,
generated ownership/HANDWRITTEN_FILES, guest/provenance input or release ledger
was found: plan commit8e28375 changes only the new plan and project status.
No extra regeneration, benchmark or full runtime check is justified for this
documentation boundary. No stale in-code behavior comment was introduced.
Historical reviews/receipts remain unchanged.

Unverified OS/browser/worker/framework behavior is listed above rather than
called PASS. No implementation, opposite-platform execution, independent setup
measurement, main integration, Qualification or release is described as done.
No new deferral was accepted on the Human's behalf. Preserving existing physical
sessions, automatic preparation routing, new cache/control APIs and v0.7 tuning
remain distinct decisions.

Next: review the workload/order, then produce the W3/W4 input and Django lifecycle
manifest with a small source-investigation scope. Use it to propose the minimum
adapter experiment and the separate live/E2E experiment. The present task has
completed replanning and source-based review, not those future experiments.

Verification for this report: source/diff and local-reference inspection,
public-source policy and whitespace checks. No test/build/benchmark or CI run was
started or polled for this documentation-only task.
