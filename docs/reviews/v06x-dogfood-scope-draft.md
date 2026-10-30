# Dogfood and fixture ergonomics — scope discussion draft

> Current scope correction — Human approved 2026-10-30:
> [P1 fixed exit / v0.7.x resource placement](../decisions/p1-fixed-exit-v060.md)
> supersedes the resource completion gates below. Detailed retention/resource
> characterization is deferred to v0.7.x; entry lifecycle correctness remains
> required. Earlier proposal/checkpoint text and source-bound receipts below are
> historical evidence, not the current list of P1 blockers. P1 is not yet accepted.

2026-10-28. This consolidates the Human's scope discussion. Agreed outcomes below
are product direction, not claims that all existing entries implement them.
Open choices remain explicit; no runtime or experiment is authorized here.

## Agreed outcome

Let Go/Python users establish and grow DB tests through supplied entries without
assembling preparation, test isolation and cleanup lifecycles themselves. Users
provide application-specific preparation and test intent; the entry manages the
owned resources and execution order. Existing functionality is the foundation.
Framework count is not the completion measure, and new adapters/APIs are chosen
only when necessary to satisfy the agreed experience. Wire sufficiency must be
verified, including paths that representative examples do not exercise.

## Agreed responsibility and completion requirements

| Area | User supplies | Entry responsibility / evidence required |
| --- | --- | --- |
| Preparation | Migration/seed command or callback | Execute, assess success, reuse successful preparation, dispose failed preparation; never admit a test after setup failure |
| Reuse | Application's preparation inputs | Default reuse within one test execution; independent preparation/baselines per parallel worker |
| Isolation | Test operations and assertions | Each admitted prepared-entry test begins with the declared schema/seed, including after previous commits/failure |
| Cleanup | Application-specific resource knowledge/configuration | Own the provided lifecycle; attempt cleanup on test failure, exception and normal interruption; report unresolved cleanup |
| Failure explanation | Original application/driver failure as available | Evaluate against the entry's declared diagnostic milestone below; original failures and honest admission/cleanup outcomes are mandatory at every level |
| Wire sufficiency | Intended connection/use requirements | Inventory current support, compare reachable behavior with native MariaDB, preserve discrepancies and decide reach/defer explicitly |

No silent retries or masking original failures. If cleanup fails too, retain both
errors. Unknown causes stay unknown; advice must not assert an unproven diagnosis.
Hard-kill/machine-stop recovery, cross-run persistence and cross-worker baseline
sharing are separate boundaries, not promises implied by normal cleanup/reuse.

## What counts as finishing this scope

For each selected entry and declared configuration:

1. Follow user-facing instructions to supply connection configuration and
   preparation, then execute a first meaningful application test.
2. Add a second test without duplicating DB preparation/isolation/cleanup code;
   changing test order must not introduce another test's mutations.
3. Verify successful preparation reuse at its declared worker/execution scope,
   and the selected initial-state contract for every admitted test.
4. Exercise preparation failure, test failure, normal interruption and cleanup
   failure; retain original outcomes, prevent invalid admission and show useful
   human-readable explanations and honest cleanup status.
5. Cover the necessary wire behavior and classify all inventoried unresolved
   paths. An unused capability is not automatically unnecessary. Native/guest
   differences need attribution before choosing an implementation change.
6. State tested combinations, user obligations, unsupported behavior and explicit
   decisions on remaining gaps. Do not claim broad framework/client coverage
   from one app, or call a recipe complete merely because its component APIs work.

These are acceptance requirements, not a report of completed acceptance. Apply
them to the named target set below and its declared diagnostic milestone; a
first-milestone PASS does not imply ideal-diagnostic or whole-scope completion.
Oscar is an investigated candidate input, not the definition of this scope.

## Named target entries — approved with Django nonblocking

The Human approved the proposal reviewed at39f9757, with G1 first and one
qualification: D1 is a dogfood target but difficult Django-specific implementation
must not block v0.6.0. P1/G1/EP1/EG1 remain required. D1 cannot silently vanish:
report the obstacle, user impact and remaining work when deferring it; deferred
is not PASS or supported. Shared defects are judged against the required entries,
not waived because Django exposed them. This records implementation direction,
not runtime acceptance, main adoption or release approval.

| ID | Entry and fixed initial profile | Preparation/isolation and owner | Completion boundary |
| --- | --- | --- | --- |
| P1 | Python pytest prepared fixture + shadow_maria; PyMySQL1.2.3, SQLAlchemy2.0.54 integration | Callback/command preparation; one baseline per xdist worker; independent child per test | Actual command/callback success/failure, routing/pool ownership, schema/seed and error/cleanup evidence; existing fixture is the foundation |
| G1 | Go testing helper; database/sql + go-sql-driver/mysql1.9.3 | One preparation per fixture/test-package process; bounded children and helper-owned SQL pools | Thin prepared helper first milestone plus declared diagnostic profile and timing/resource evidence |
| D1 | Django5.2.8/mysqlclient2.2.7; manage.py and pytest-django4.12.0 | Explicit preparation and starting-data policy for both ordinary TestCase and transactional tests | Demonstrate the declared schema/seed at each prepared-entry test; the existing standard-runner recipe alone does not close this row; mechanism needs design; nonblocking for v0.6.0 if difficult, with an explicit deferred-work record |
| EP1 | Python sequential browser E2E; existing Django/Playwright fixed profile | One application/Live per worker; reset before each case; new browser context per case | Supplied entry owns hook/Reset/admission/cleanup sequence in the E2E contract; if Django obstructs this, pin a non-Django application instead of dropping browser E2E |
| EG1 | Go sequential HTTP E2E; existing Go orders application | One application/Live per test-package fixture owner; reset before each case | Same hook/Reset/admission/cleanup contract, explicitly HTTP rather than browser evidence |

Acceptance environments are macOS15 arm64 and Ubuntu24.04 x86_64; Python entries
use3.11/3.14 and Go uses1.26.10. Reuse existing fixed package locks for existing
workloads; a changed/external workload needs its own fixed lock and native input
gates. Native references remain exact MariaDB12.3.3. Existing Connector/Python
and MariaDB-driver wire regressions stay anchors under their recorded exceptions,
not an implicit expansion of P1's routing profile. Selecting/defering other
drivers or workloads requires an explicit recorded disposition.

### Diagnostic levels and evaluation

- `readable-owned`: the entry explains its own setup/acquisition/reset/cleanup
  failures with operation/stage, original error/code, admission and cleanup
  state, and a supported next action or explicit unknown. Test assertions and
  SQL called directly through a returned handle keep ordinary framework output;
  this level does not invent an application root cause or intercept arbitrary SQL.
- `basic-first`: stage + preserved original error + honest admission/cleanup
  status, with ordinary framework assertion output. Extended causal explanations
  and recommended remedies remain unfinished. Only G1/EP1/EG1 may use the already
  authorized pragmatic first milestone, after the pre-implementation decision
  below. They are assessed at that milestone, not failed against an unselected
  ideal formatter or reported as full ideal completion.

The concrete design targets `readable-owned` for all rows. The fallback is
authorized but **not activated**. Before the first helper implementation commit,
record the selected level for each implemented row and evidence-based feasibility
rationale in a committed design decision. If ordinary Go error wrapping/testing
output suffices, keep readable-owned; no global diagnostic framework is required.
If a lower level is needed, record the concrete obstacle, effect on users,
unfinished fields and finite stopping point **before** helper implementation.
A change of level after implementation starts requires stopping for a new
decision, not an end-of-task justification. Implementation acceptance must pin
the reviewed design commit as an ancestor and reject missing/stale decisions.

## Original time/resource campaign (resource gates superseded 2026-10-30)

Record three distinct outcomes per entry: first-test setup (commands, edits and
phase wall times including declared acquisition/preparation); adding the second
test (authored diff/steps, no repeated lifecycle wiring); repeated execution
(whole batch elapsed plus preparation, admission, SQL/case and cleanup phases).
Human authoring minutes are reported only if directly observed; an automated
run may use edit/step counts but cannot invent a human-time number. Mark cold,
warm and unmeasured acquisition explicitly. A fresh venv is not a clean-machine
cold-install claim. Do not sum overlapping parallel operation times.

The initial diagnostic campaign is explicitly bounded: child limits1 and2,
four cases per batch, Go -parallel1 and4 with -p1, pytest/xdist workers1 and2.
Test that limit2 blocks a third acquisition until a child is released. Preparation
pool max-open1, helper-owned child pool max-open2/max-idle1; each DB's existing
wire capacity16 remains unchanged. Default-helper proposal is MaxForks=2
(zero selects2, negative rejects), not an unbounded or inferred memory heuristic.
It needs measurement/approval with the concrete API. Total concurrency is the
sum over fixtures and worker/package processes, not just one fixture's limit;
record active children and physical connections so those counts cannot be
conflated. E2E has one active case per owner and two independent owners in its
parallel-worker control; do not run parallel cases through one Live.

Observe process-tree RSS/available memory, owned DB/baseline/connection peaks,
FD baseline/peak/final, temporary bytes and post-cleanup state. Keep RSS, heap,
and physical footprint labels distinct. Include an owned retention diagnostic
with1,2,3 retained baselines using the
[fixed64-table diagnostic](../../tests/fixture_entry_acceptance/retained_baselines.sql) before
claiming the FD-pressure obligation assessed. This new diagnostic follows the
historical table-count shape, not its exact bytes or performance cohort. It is not an unlimited stress
test. Candidate ceilings:2GiB incremental process-tree RSS,8GiB owned disk,
16GiB minimum free disk, and FD headroom of at least64 under the observed process
soft limit. Stop further admission on a guard breach, preserve STOP evidence and
attempt cleanup; missing host counters are UNVERIFIED, not zero/PASS. Record
whether the observations justify a static default/guidance or require a separate
cap/resource-model decision; they do not automatically approve changing16 slots.

Use one explicit warmup and three separately labelled observed batches per
selected serial/parallel mode. This is a bounded resource/workflow observation,
not a speedup claim or release benchmark. Preparation and ordinary cleanup have
cooperative deadlines; Snapshot sealing/noncooperative guest exits retain their
existing limitations. Do not fabricate a hard timeout guarantee.

## E2E hook boundary

The shared [E2E entry contract](v06x-e2e-entry-contract.md) names exactly what
StartReady, QuiesceAndRetire, optional Resume and StopReap must provide and what
the entry owns. It applies to both EP1 and EG1. A missing required hook or failed
hook/Reset never admits the case body. Preparation/bootstrapping must be complete
before the baseline; post-start baseline capture is a separate unselected design.

## Current foundations and gaps

| Existing boundary | Confirmed foundation | Gap relative to the agreed experience |
| --- | --- | --- |
| Python pytest | `mariamem_prepare` callback, session Snapshot and function Fork already compose preparation/reuse/cleanup | Review command entry, success/error presentation, combined-failure handling and exposed user configuration; do not rebuild this foundation unnecessarily |
| Go public API/guides | Start/Snapshot/Fork and sequential/parallel ownership examples | Test authors still compose source/pool/capture/child cleanup manually; decide the supplied test entry before claiming ergonomics complete |
| Public Live examples | Reused application, stable endpoint, sequential reset and application-before-DB shutdown | E2E contract below fixes responsibilities; concrete adapter/API and actual hook/failure acceptance remain unfinished |
| Django standard runner | Parent owns the server/invocation; Django owns test DB, transactions/flush/fixtures; native/guest lifecycle evidence exists | D1 still needs a prepared-state design; ordinary flush must not be counted as automatic prepared-Snapshot restoration |

Sources: [pytest fixtures](../../python/mariamem/pytest_plugin.py),
[Go prepared-baseline guide](../go.md#prepare-once-fork-independent-databases),
[Live examples](../examples/live/README.md),
[Django lifecycle](../django-testing.md), and
[preparation recipe](../preparing-test-data.md).
This was a source/doc inspection, not a new runtime campaign.

## Initial state at each test — decision recorded 2026-10-28

Two different promises must not be conflated:

- A previous test's changes do not leak, while each framework's normal lifecycle
  still determines starting data.
- Every test using the prepared-data entry begins with the declared prepared
  schema/data, regardless of the previous test's writes or failure.

The Human selected the second promise for the prepared-data entry. Independence should
include the reusable seed users explicitly asked the entry to prepare. How a
framework achieves that promise is a design choice, not a reason to silently
weaken it. The existing ordinary Django runner can remain a clearly labelled
framework-lifecycle route without being advertised as automatic baseline reset.
That separate existing route must not be labelled as satisfying the new
prepared-entry guarantee without evidence. The selected promise is not an
adapter implementation approval.

Concrete reason: Django TransactionTestCase default flush does not replay data
migrations. This is native framework behavior, already documented/tested, not a
mariamem wire bug. Fixtures or an explicit restoration mechanism can supply the
initial-state policy. Do not infer that adopting the existing runner recipe
already closes this stronger ergonomics requirement.

## Pragmatic first milestone — agreed 2026-10-28

The ideal includes useful human-readable failure explanations. The Human permits
a pgmem-style helper as the first stopping point if richer diagnostics become
disproportionately difficult. Keep preparation-once, per-test prepared state,
owned cleanup and visible failures; report why richer diagnostics are unfinished.
This fallback does not make pgmem's ignored Close return values our policy:
simple error wrapping/joining or test cleanup errors can preserve both failures
without requiring a diagnostic framework. Do not label the ideal experience
complete just because the basic helper milestone passes.

## Boundaries to settle in the ensuing design

The named entries, diagnostic levels, budgets and E2E responsibilities above are
now concrete review inputs. [Go API/ownership proposal](v06x-go-fixture-api-design.md)
and [current wire inventory](v06x-wire-current-inventory.md) continue the work.
The Human approved G1 first against design commit39f9757, with readable-owned
diagnostics and the proposed API/defaults. P1/G1/EP1/EG1 are the required completion
set; D1 is nonblocking under the exception above. These decisions are not runtime
acceptance. D1's mechanism and wider wire reach/defer remain explicit work.

Broader frameworks, async, extra wire features, resource caps and persistence
remain visible capability-map candidates. No deferral or implementation is
silently approved here. Resource observations inform finite parallel-use bounds;
they do not automatically authorize a scheduler or runtime redesign.
