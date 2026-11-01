# D1 v0.6.1: minimal boundary comparison

Design comparison,2026-11-01. Product source_commit b3b3b46a8807482ad3f96725af86e031fe369b01. This completes the first bounded comparison in Issue43, not D1 implementation or acceptance.

## Decision and recommendation

Continue with an explicitly opted-in prepared Django entry built on Snapshot/Fork ownership, not a blanket patch to the existing standard runner. Capture the baseline after Django test-DB creation/migrations and the user preparation callback. Keep the ordinary recipe unchanged. Before implementation, resolve one remaining design choice: how the prepared entry treats TestCase class-level transactions and setUpTestData.

Recommend a small lifecycle characterization of a new prepared test base/runner seam first, including TestCase class setup, rather than implementing the complete adapter now. The strongest objection is that this introduces another integration surface and may change class-fixture behavior. That is material: repeated class setup or disabled class atomics must not be slipped into a transparent compatibility claim. If the required lifecycle cannot be preserved simply, report that obstacle for the Human's scope decision; do not silently reduce Issue43 to transactional pytest only.

## What source inspection establishes

- Existing `docs/examples/django/run_tests.py` owns a server per invocation and delegates the test DB and isolation to Django. It does not capture a baseline.
- `tests/django_lifecycle/run.py:90` deliberately expects SEED then empty for ordinary flush. `SerializedCases` and the mixed fixture tests restore selected data, not arbitrary prepared database state.
- Django's serialization walks migratable models and writes JSON; it does not snapshot schema, unmanaged SQL objects or the whole database. [creation.py:120](https://github.com/django/django/blob/47fe39af56ecd0ad73b9c7562511015e96b91b80/django/db/backends/base/creation.py#L120)
- `TransactionTestCase.setUpClass` eagerly calls `_pre_setup` for the first test. Subsequent calls come through `_setup_and_call`. A per-test adapter that hooks only `setUp` or blindly runs `_pre_setup` twice is incorrect. [testcases.py:1120](https://github.com/django/django/blob/47fe39af56ecd0ad73b9c7562511015e96b91b80/django/test/testcases.py#L1120)
- `TestCase.setUpClass` opens class atomics, loads fixtures and invokes setUpTestData; per-method atomics nest inside that session until class teardown. Closing/rebinding that session between methods breaks those assumptions. [testcases.py:1407](https://github.com/django/django/blob/47fe39af56ecd0ad73b9c7562511015e96b91b80/django/test/testcases.py#L1407)
- pytest-django uses different routes: function tests get a generated TestCase/TransactionTestCase through `_django_db_helper`, whereas Django unittest classes bypass that helper and use `_django_setup_unittest`. One function fixture does not cover both. [fixtures.py:191](https://github.com/pytest-dev/pytest-django/blob/a2a94956cc24bb30030510710f0f27e61efb0cf0/pytest_django/fixtures.py#L191), [plugin.py:570](https://github.com/pytest-dev/pytest-django/blob/a2a94956cc24bb30030510710f0f27e61efb0cf0/pytest_django/plugin.py#L570)
- P1's source/command preparation, disconnect, capture, fork and cleanup-debt ownership are reusable foundations. P1's pytest entry does not hook Django's class lifecycle or mysqlclient routing. Existing driver-routing aliases must not be presumed to cover mysqlclient.

## Alternatives

| Approach | Benefit | Gap / disposition |
| --- | --- | --- |
| Native fixtures / serialized rollback | Existing standard Django semantics; no new helper | Not full schema/seed restoration. Retain as ordinary recipe, not D1 completion |
| P1 plus changing connection settings in a function fixture | Reuses preparation and ownership | Too late/incorrect for class atomics, eager setup and unittest route; not sufficient alone |
| Fresh Fork per test through explicit Django lifecycle entry | Whole prepared state, commits and ordinary failure cannot pollute the next child | Best D1 foundation; class fixture semantics and both runner hooks need characterization before implementation |
| Live Reset per method | Stable endpoint avoids address updates | Does not eliminate open-class-atomic/physical-connection retirement problems; no automatic benefit over Fork established |
| Existing TestCase rollback per class-child, fresh Fork for transactional cases | Least disturbance to ordinary TestCase; class setup retained | External committed writes/schema mutations escape rollback. This is a mixed isolation policy, not the uniform restore guarantee; requires an explicit scope decision |
| Separate process/suite per test on a Fork | Can bracket a complete Django lifecycle | Repeats class setup and process startup; changes semantics/cost. Keep only as fallback/control, not presumed product design |

A new database backend, guest change or wire feature is not justified by the evidence so far.

## Proposed common ownership contract (design, not implemented)

1. One serial runner, one default alias. Django creates the test DB and applies migrations on a disposable preparation server. Run an optional user callback against that migrated DB before admitting any test.
2. Close the framework connection and all registered preparation connections. Confirm disconnect; Snapshot consumes the source only after successful capture. On rejected capture retain/dispose the still-owned source; on partial failure use the SDK's actual owner state. Never recapture partially failed migration/seed state.
3. Acquire a fresh child before Django's applicable per-test setup, set the default alias endpoint and test database name to that child, and ensure prior connections are closed. Use the ordinary mysqlclient backend. Do not assume Python MySQL routing patches apply to it.
4. Django test-local fixtures/transactions run on the child according to the selected class policy. Prepared baseline contents and declared class/test-local setup additions are separate concepts.
5. After normal Django teardown, close physical connections, wait for disconnect and close the child. Preserve the original test/setup exception together with cleanup failure. Unconfirmed cleanup blocks the next admission; do not silently retry.
6. At run end restore settings and close baseline/remaining owners. Final Django DB teardown must target the correct current owner, not a consumed preparation endpoint or the original application database.

Illustrative public surfaces for comparison, not selected API names: `PreparedDiscoverRunner` for manage.py, an opted-in pytest plugin/setup fixture, and an explicit prepared Django test base if required by lifecycle semantics. The user supplies preparation once; library code owns capture, independent children and cleanup. No per-test manual ownership recipe is the proposed product experience.

## Unresolved class policy and next finite step

A fresh child per TestCase method cannot retain an open class-level atomic transaction. A possible adapter could materialize class data before a class snapshot, but capture timing, class-fixture Python objects, user overrides, transaction exit and teardown would all need proof. This report does not claim that adapter is solved or that setUpTestData can simply be moved outside its transaction.

Next characterization: Django5.2.8 and pytest-django4.12.0, authored orders classes, no broad external project. Trace the ordering of runner DB setup, subclass/super setUpClass, eager pre-setup, class atomics, setUpTestData, per-test hooks and teardown on both runner paths. Include class failure/skip and two methods. The framework-only ordering trace below now establishes these two normal class paths. Failure/skip paths and a safe adapter seam remain unproven. Next work would be a separate bounded lifecycle-adapter sketch, including user class overrides and setup failure/skip, before any MariaDB campaign. Its outcome must be a concrete safe API policy or an explicit changed-semantics decision; no full implementation is approved here.

## Acceptance outline if implementation is selected

- Both manage.py and pytest-django; ordinary TestCase and transactional cases named separately, never inferred from each other.
- One preparation per declared ownership unit; migration records, prepared seed and a non-model schema/SQL sentinel intact at each baseline. First/second/reverse/shuffled cases; committed writes and an expected failure do not affect the next admitted case.
- Explicitly preserve or document class-fixture/sequence/reset/serialized behavior chosen in the design. Non-default aliases/routers, parallel/xdist, async, live-server threads and unregistered external connections are separate limits, not silently covered.
- Migration/seed failure admits no test body, preserves original errno/traceback and discards partial owners. Rejected capture, failed fork, physical-connection leak and combined cleanup failure have their own controls.
- Cover stale endpoint/no-original-database fallback and cleanup debt; verify restoration of settings and balanced class/app hooks on failure.
- Use the current Release policy for eventual both-host/Python3.11/3.14 installed-entry acceptance. Existing standard-runner CI does not detect the absent D1 product boundary, so D1 needs dedicated state/admission/cleanup oracles. Resource tuning and Oscar/general-project campaigns are not prerequisites.

## Framework-only characterization

Python3.11.18, Django5.2.8, pytest9.0.2, pytest-django4.12.0; SQLite in-memory, no installed apps, no MariaDB driver or guest. The manage.py-equivalent DiscoverRunner command ran4 checks successfully; pytest-django ran6 successfully. Both record class transactions remaining active after each Atomic method, setUpTestData once, and the first Transactional pre-setup preceding completion of setUpClass. Pytest functions additionally show atomic versus transactional contexts. This confirms hook ordering, not database restore or an integration API.

[Probe source, raw events/logs, dependency versions and hashes](d1-v061-characterization/). Reproduce in that directory with a fresh Python3.11 venv and its requirements, then run:

```sh
PYTHONPATH=. DJANGO_SETTINGS_MODULE=d1_settings D1_EVENTS=/tmp/d1-manage-events.jsonl python -m django test test_trace --noinput -v 1
PYTHONPATH=. DJANGO_SETTINGS_MODULE=d1_settings PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 D1_EVENTS=/tmp/d1-pytest-events.jsonl python -m pytest -p pytest_django.plugin test_trace.py test_functions.py -q -p no:cacheprovider
```

Use fresh event-file paths because the recorder appends. The initial venv accidentally used the machine's Python3.9.6 and installation failed before execution; it was replaced with Python3.11. No version substitution was made. Class setup failure/skip and an actual prepared adapter were not executed.

## Evidence scope

Source inspection plus the framework-only SQLite probe; no MariaDB/guest execution, product build or CI submission. Django5.2.8 resolves to47fe39af56ecd0ad73b9c7562511015e96b91b80; pytest-django4.12.0 resolves toa2a94956cc24bb30030510710f0f27e61efb0cf0. Seven inspected upstream file hashes and URLs are in [the manifest](d1-v061-minimal-design-sources.json). Repo evidence: [D1 deferral](../decisions/d1-v060-deferral.md), [current recipe](../django-testing.md), `tests/django_lifecycle/cases.py`, `mixed_cases.py`, `run.py`, `python/mariamem/pytest_plugin.py`.

The comparison is complete; a minimal production adapter and the TestCase class policy are not yet fixed. Issue43 stays open. No implementation, support expansion, main adoption or release claim follows from this document.
