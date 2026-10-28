# Dogfood and fixture ergonomics — scope discussion draft

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
| Isolation | Test operations and assertions | Independent mutable test state; actual initial-state guarantee still needs the decision below |
| Cleanup | Application-specific resource knowledge/configuration | Own the provided lifecycle; attempt cleanup on test failure, exception and normal interruption; report unresolved cleanup |
| Failure explanation | Original application/driver failure as available | Human-readable operation/stage, confirmed cause, original error/code, next useful action, test-admission and cleanup outcomes; details remain inspectable |
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

These are acceptance requirements to design into finite tests, not a report of
completed acceptance. Exact framework/driver/workload coverage is still open.
Oscar is an investigated candidate input, not the definition of this scope.

## Current foundations and gaps

| Existing boundary | Confirmed foundation | Gap relative to the agreed experience |
| --- | --- | --- |
| Python pytest | `mariamem_prepare` callback, session Snapshot and function Fork already compose preparation/reuse/cleanup | Review command entry, success/error presentation, combined-failure handling and exposed user configuration; do not rebuild this foundation unnecessarily |
| Go public API/guides | Start/Snapshot/Fork and sequential/parallel ownership examples | Test authors still compose source/pool/capture/child cleanup manually; decide the supplied test entry before claiming ergonomics complete |
| Public Live examples | Reused application, stable endpoint, sequential reset and application-before-DB shutdown | Examples contain application startup, quiescence and lifecycle assembly; a supplied entry and explicit application-hook boundary still need design |
| Django standard runner | Parent owns the server/invocation; Django owns test DB, transactions/flush/fixtures; native/guest lifecycle evidence exists | This is a distinct isolation mechanism, not automatic prepared-Snapshot restoration; resolve the initial-state promise before deciding whether the recipe suffices |

Sources: [pytest fixtures](../../python/mariamem/pytest_plugin.py),
[Go prepared-baseline guide](../go.md#prepare-once-fork-independent-databases),
[Live examples](../examples/live/README.md),
[Django lifecycle](../django-testing.md), and
[preparation recipe](../preparing-test-data.md).
This was a source/doc inspection, not a new runtime campaign.

## Next product choice: initial state at each test

Two different promises must not be conflated:

- A previous test's changes do not leak, while each framework's normal lifecycle
  still determines starting data.
- Every test using the prepared-data entry begins with the declared prepared
  schema/data, regardless of the previous test's writes or failure.

Recommend the second promise for the prepared-data entry. Independence should
include the reusable seed users explicitly asked the entry to prepare. How a
framework achieves that promise is a design choice, not a reason to silently
weaken it. The existing ordinary Django runner can remain a clearly labelled
framework-lifecycle route without being advertised as automatic baseline reset.
Whether such a route satisfies the selected v0.6 entry scope needs a Human
decision; this recommendation is not an adapter implementation approval.

Concrete reason: Django TransactionTestCase default flush does not replay data
migrations. This is native framework behavior, already documented/tested, not a
mariamem wire bug. Fixtures or an explicit restoration mechanism can supply the
initial-state policy. Do not infer that adopting the existing runner recipe
already closes this stronger ergonomics requirement.

## Boundaries to settle in the ensuing design

After the initial-state choice, map the requirements to selected entries and
finite success/failure/wire acceptance. Specify what application connection,
pool and E2E quiescence hooks users supply and which resources the entry owns.
An entry cannot infer arbitrary background-job completion or reset non-DB caches.
Set command/callback success signals, cancellation and cleanup reporting without
guessing application-specific business correctness.

Broader frameworks, async, extra wire features, resource caps and persistence
remain visible capability-map candidates. No deferral or implementation is
silently approved here. Resource observations inform finite parallel-use bounds;
they do not automatically authorize a scheduler or runtime redesign.
