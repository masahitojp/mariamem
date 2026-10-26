# v0.6.x dogfood plan — framework tests and long-lived E2E

## Purpose and planning state

Replanned on2026-10-26 at the Human's request: include browser E2E explicitly,
then review the whole schedule before proceeding with Django adapter work.
Source basis is main `bf3a29c292064ddbbd4c7b9a9c6e712504d0f4e4`.
This is a proposed work sequence, not implementation or execution approval for
new live/reset behavior. Django investigation remains the next workstream; its
scope now includes discovering E2E requirements before choosing an adapter.

Evaluate two user journeys: adding database tests to a new application, and
adding them to an existing application with migrations, settings and connections.
Observe installation, first test, second independent test, failure recovery,
parallel execution and cleanup separately. Compatibility, effort and execution
cost are distinct results. Preserve the whole
[capability map](v06x-capability-map.md); chosen examples prioritize gaps rather
than silently remove uncovered capabilities.

## Starting point and evidence reuse

Prepared commands, scoped routing/marker/preparation, the migration recipe and
bounded dump reader are adopted on main. Existing SQLAlchemy/GORM consumers and
stable migration/dump acceptance are regression anchors, not evidence of Django,
E2E, arbitrary framework support or live reset. Reuse their source-bound results;
repeat only for a changed boundary or new combined workload. Preserve exact
[prepared consumer exceptions](../decisions/prepared-consumer-exceptions.md)
and environment SKIPs rather than relabeling them PASS or forcing a different
client path. Current status supersedes older P6-pending text in historical records.

The [live task](v06x-shadow-maria-entry-design.md#human-decision--live-is-a-separate-task)
already requires a separate resource/lifecycle design and a decision on0.6.0
inclusion. E2E is now an explicit dogfood target, not an appendix that can disappear
when ORM tests pass. That does not decide which live implementation is feasible.

## Workload register

| ID | Workload and real entry | Questions and minimum result | Position |
| --- | --- | --- | --- |
| W1 | Python SQLAlchemy plus Alembic application | Existing migration/seed, normal pool/session, commits/rollback/constraint recovery, next-test independence and teardown; observe first/second-test edits | Existing regression/preparation anchor; reuse, extend only for uncovered combined use |
| W2 | Go GORM and go-sql-driver application | Child-owned configuration/pool, normal prepared path, transactions, cleanup and independent next test; retain interpolation distinctions | Existing Go anchor; reuse, connect to parallel/resource observations |
| W3 | Django ORM and in-process HTTP tests | Real project/settings/models, two actual schema revisions and surviving seed; test DB creation/destruction, TestCase class/transaction setup, TransactionTestCase flush/commit and connections. Inspect manage.py test and pytest-django separately | Next discovery target; neither runner is advertised as supported by routing alone |
| W4 | Django plus a separate Web-server process and actual browser | Browser A changes data and commits through the app; browser B begins from the same baseline, while the same Web process remains alive. Record endpoint, reconnect and application-state policy | Explicit E2E target; native control/requirements discovery precedes live design and live runtime claims |
| W5 | Web plus separate background worker | A job commits through another connection/process; drain active work before changing baseline; late/retried jobs cannot write into the next test | Explicit long-lived multi-process extension; depends on W4 contract. Worker/queue implementation must be selected at the manifest gate |
| W6 | Application prepared from the bounded MariaDB dump | Installed helper, supported producer profile, ordinary application entry, preparation failure and independent children | Existing native/import anchor; broader inputs require their own decision |
| W7 | Metadata-heavy schema and a real dbt-like workflow | Introspection/migrations with many objects; identify tool SQL, catalog, DDL, transaction and cleanup assumptions | Retained target. Select one concrete tool/version/project; SQL-only imitation does not establish tool compatibility |
| W8 | Parallel and larger-fixture variants of selected Go/Python applications | Distinguish active DB count, connections per DB, worker baselines and retained snapshots; observe memory, FD and end-to-end time plus cleanup | Depends on an identified workload/topology, not on successful live implementation. Start with W1/W2, extend to W3/W4 where justified |

W3/W4 should share one repository-authored Django application and preparation
inputs so differences reflect topology/lifetime rather than unrelated corpora.
Use its real Django migration and application/browser entry points. If an existing
external project is selected instead, pin its revision/license/setup and record
the reason; do not claim the authored app proves arbitrary legacy compatibility.
No browser automation, worker, Django runtime or dbt version has been newly
selected or installed by this planning task. Existing Django5.2.7/mysqlclient2.2.7
source references are starting evidence, not a current-version/support promise.

## Dependency schedule and review points

This is an ordered schedule with parallel work, not unmeasured calendar estimates.
At each execution gate, pin the inputs and resource/time budget before running.

| Stage | Work | Depends on | Deliverable / exit and next decision |
| --- | --- | --- | --- |
| P0 | Review this register; create per-workload manifests | Current main and prior decisions | Fix app/tool/client versions, commit identities, OS/interpreter/browser matrix, data, topology, executable commands, limits and expected observations. Start with W3/W4; later rows remain visible with named selection work |
| P1 | Django lifecycle source investigation and native controls, including the browser topology | P0 for W3/W4 | Map settings/test DB/migrate/class/test/flush/teardown ownership; native browser A/B controls establish the intended app scenario; list missing inputs or incompatibilities. Source investigation can proceed before any runtime experiment |
| P2a | Compare explicit Django settings recipe, framework lifecycle adapter and existing routing | P1 W3 evidence | Recommend the smallest entry that preserves the selected runner's semantics and mariamem isolation. Return for design/spike review before implementation; no automatic assumption that a new public adapter is needed |
| P2b | Design live/resource boundaries for the long-lived E2E case | P1 W4 requirements; P2a only where connection hooks are shared | Compare application-only reuse, application+endpoint reuse and existing-session reuse. Recommend a finite live contract, required host/guest/framework changes and bounded spike. Decide0.6.0 inclusion separately |
| P3 | Execute approved bounded experiments, then review results | Exact P2a/P2b approvals and manifests | PASS/FAIL/SKIP, native comparison, failure/cleanup observations and route recommendation. If infeasible, report the exact blocker and alternatives; do not substitute restart for live and call the live target complete |
| P4 | Implement approved minimum changes; verify combined ORM/E2E use | P3 plus implementation decision | Installed user entry, maintained tests/docs, exact-source native CI on both supported OSes. W5 follows its own selected worker contract; no arbitrary queue support claim |
| P5 | Remaining workload/resource pass and capability reconciliation | P0 manifests for W7/W8 and stable workload code | Record W7, observed resource/connection demand, first/second-test friction and each capability's reach/limits/remaining decision. Revisit only demonstrated wire/adapter/resource gaps |
| P6 | Human review of version scope and completion | Evidence or explicit disposition for every register row and capability axis | Decide what ships in0.6.0 versus later0.6.x/deferred. Main adoption, target version, Qualification and release follow their own approved gates |

W1/W2 evidence inventory, diagnostic design and the already approved serial/
parallel guide can proceed alongside P1/P2. W7 input selection and W8 resource
manifest design can also proceed independently. W8 observations need not wait for
P4 live; fixed-endpoint behavior is not a prerequisite for ordinary Fork workloads.
Do not execute an entire Cartesian product of every tool, runner, browser and
resource size: define mandatory cells, diagnostic cells and explicitly unverified
cells in each reviewed manifest. Supported functional boundaries still require
macOS arm64/Ubuntu x86_64 and the appropriate Python3.11/3.14 checks.

## E2E baseline and live contract to investigate

The target scenario is user-visible state, not an empty-database assumption:
prepare migrations/common data, complete startup preparation, fix baseline;
A creates data through the browser/app and commits; finish A's work;
B starts from the same baseline and cannot see A's changes. Pin when startup
migrations/seed have finished and how preparation connections are closed before
a consuming Snapshot. If startup itself requires retaining an active application
connection across capture, record that conflict instead of assuming it is solved.

Compare these separately:

| Level | Resources retained | Must be decided/proven |
| --- | --- | --- |
| L1 | Same application process; DB settings/pool may be replaced | Can the app stop DB activity, close old handles and bind a new child? Existing in-process routing does not automatically reach a separate server process |
| L2 | Same application process and DB endpoint; sessions may reconnect | How does the stable endpoint change backend, reject old sessions and recover without stale writes? This is a proposed live boundary, not existing support |
| L3 | Existing physical SQL sessions also remain usable | Transaction, temporary-table, session-variable and prepared-handle semantics. Do not infer this from L2. Keep as a separate decision; investigate only if required |

First evaluate L1 and L2 against the actual application. Do not preselect L3,
a relay, COM_RESET_CONNECTION or a guest patch. Record the smallest level that
meets the app's real constraints. An application restart per test is a useful
control/cost comparison, but never a PASS for the same-process live scenario.

Use an explicit safe boundary: stop new requests/jobs, finish or reject in-flight
work according to the selected contract, close/retire the declared DB resources,
restore/rebind, verify readiness, then admit B. Draining/reset failure must block
B and retain the original error plus cleanup outcome. Pausing work is not a
mechanism for preserving arbitrary active transactions across reset.

Browser/session/cache state needs its own policy. Specify separate browser
contexts/cookies per independent test, authentication seed, app caches and ORM
identity caches; DB reset alone must not be advertised as whole-app reset.
W5 adds queue/job identity, retry/drain and late-writer policy. Preserve audit
observations before cleanup: process identity/start count, HTTP endpoint, DB
endpoint, backend generation, commit markers and job/result identities.

In-process django.test.Client is W3 evidence. Real-browser/separate-process W4
remains its own row. LiveServerTestCase or any browser fixture's actual thread/
process topology must be recorded; its name alone does not prove W4's topology.
A same-process substitution cannot satisfy the separate-process oracle.

## Common evidence and failure oracles

For each workload, run the same application/input on native MariaDB12.3.3 as the
semantic control and on the pinned mariamem source; retain app, driver and tool
identities. Native DB reset between tests may differ as a control mechanism and
must be recorded. Match observable application results, row/constraint state,
commits/rollback, framework lifecycle and subsequent SQL. Distinguish application/
engine/client incompatibilities from mariamem routing/wire/lifecycle gaps using
source and concrete errors; do not diagnose from a generic SQLSTATE alone.

Required observations, made machine-checkable where possible:

- Migration/seed/import failure: original cause/code/stage/location where known,
  no partial baseline/test admission and source cleanup.
- A's committed mutation is absent from B, while common seed remains; test order
  permutations and two independent children/process generations catch hidden reuse.
- Original application endpoint is protected where routing is promised; outside
  process boundaries use explicit settings and independent connection auditing.
- Declared ownership of pools/sessions/transactions and teardown; no hidden global
  disposal, original-target fallback, swallowed error or transaction replay.
- Live/E2E: same required app process/endpoint, no old-generation writes after
  transition, pending work or held-transaction failure, reconnect and a subsequent
  successful request, then full shutdown. Include mutations for process restart,
  skipped reset, stale connection/job, original-target fallback and failed drain
  followed by B admission. Each detector must reject its specific defect.
- W5: one deliberately delayed/retried job must be rejected or drained before B
  under the chosen contract. Merely waiting a fixed sleep is not proof of quiescence.

A failed native control is a finding to classify, not permission to weaken the
same oracle on mariamem. Exact existing consumer exceptions remain explicit
exceptions. Unsupported environments/inputs are SKIP or missing-input results,
not compatibility PASS. Inconclusive investigations return the concrete missing
input, cost/budget to obtain it and a continue/defer recommendation.

## Effort, performance and resource observations

Record first-test instructions/edits, second-test edits, manual lifecycle steps,
error recovery steps and unresolved user actions. Mechanical step counts can be
reproduced; a maintainer-authored walkthrough is not independent proof of learning
time or coding-assistant token savings. Separate source build/install/browser
acquisition from ordinary fixture preparation and test execution. Claim cold
setup only after a clean-machine run; label warm runs and reuse explicitly.

Measure preparation, first child/request, subsequent tests, end-to-end elapsed
time and teardown. Compare ordinary reset/restart and reuse on the same app,
host and workload, without assuming mariamem is faster than native/container
setups. Browser/server/queue overhead is reported separately where observable.
Use Docker/native tooling as reference controls if needed; a Docker-free product
path does not prohibit containers in verification.

For W8 record DB count, sessions/DB, pool sizes, worker count, retained baselines,
RSS/physical footprint/heap as distinct measures, FD peaks and post-close values.
Specify a finite workload-size/concurrency ladder and stop budget in its manifest;
no universal memory ceiling or tuning recommendation exists yet. Fixed16
connections/DB stays current until evidence justifies a decision. Many retained
baselines/FD pressure and total DB-count limits are separate questions.
Large-fixture observation is v0.6 evidence; guest-initialization/100MiB tuning
remains the separately assigned v0.7 work.

## Capability closure and separate decisions

| Capability map axes | Evidence / decision owner |
| --- | --- |
| A installation/environment; N first/second-test burden | Walkthrough and environment records for selected Go/Python and W3/W4 |
| B routing; C ownership/cleanup; D framework/driver | W1–W5, exact runner/driver boundaries and negative cases |
| E migration/seed; F imports | Stable W1/W6 evidence plus actual W3/W4 preparation |
| G parallel reuse; L resource limits | W8 and per-worker/session records; cap/tuning/guidance decision follows observation |
| H compatibility; I actionable failures | Common native comparison/error inventory and user-facing compatibility/diagnostic guide |
| J stable endpoint/live | P2b/P3 and W4/W5; explicit version-scope decision, never implicitly dropped |
| K cross-run cache | Observe repeated preparation burden; no persistence/cache API reopened automatically |
| M fault/time/scheduler control | Controlled failures test our contract; new public fault/time/scheduler APIs remain a separate demand/scope decision |

Other drivers, language SDKs, TLS/auth expansion, LOAD DATA and binlog/CDC remain
visible capability candidates, not automatic implementation tasks. When a real
workload requires one, record the demand and return a bounded design decision.
Preparation-time automatic routing remains excluded from0.6.0 and retained for
later reconsideration; discovery uses explicit preparation settings. Broader
Django aliases/routers, multiple DBs, async, externally held resources and real
queues each need explicit manifest coverage or a visible unverified/deferred
entry, not an assumption that single-DB tests prove them.

## Completion and next review

This planning task completes with a pinned plan and review. New runtime dogfood,
adapter/live implementation and release work are not completed by writing it.
At P6 every W1–W8 row and capability A–N must have evidence plus reach/constraints,
or a Human-agreed continuation/deferral. Existing green tests cannot close
untested E2E, worker or metadata-tool rows. A proposed smaller version scope must
be explicit and reviewed; it cannot be inferred from which samples passed.

The immediate decision is whether this register/order represents the intended
v0.6.x investigation. Once agreed, P0/P1 starts with a concrete Django application,
runner and separate-process/browser topology; return the requirements and bounded
adapter/live experiment proposals before expensive implementation. Other rows
remain scheduled through their explicit dependencies rather than being forgotten.

## First milestone refinement — user-provided Python/Go E2E guides

After approving investigation, the Human proposed the pgmem Python/Go E2E guides
as a useful first reach. The [guide-target/source investigation](v06x-e2e-guide-target.md)
now fixes that first behavioral target: Python worker-local app reuse with stable
endpoint reset, and Go child launch with explicit settings/per-test Fork first.
It records the different lifecycles and the optional startup-capture/session-reuse
extensions separately. This refines P0/P1 priority: plain browser E2E does not
wait for general Django TestCase/pytest-django adapter implementation. W3's full
runner coverage, W5 workers and W7/W8 remain in the whole plan. Execution manifests
and native controls remain unfinished; source inspection is not a runtime PASS.
