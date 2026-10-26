# W3 mixed suites, failed migrations and the minimal entry recipe

## Conclusion and recommendation

For the selected single-database orders application, mixed Django TestCase/
TransactionTestCase and pytest-django function tests preserve native behavior
with explicit settings and standard seed fixtures. Recommend the
[runnable parent/settings recipe](../examples/django/README.md) as the first entry.
No new public lifecycle adapter is needed for the observed cases.

A concrete ownership requirement emerged: failed migration setup leaves partial
DDL/test schemas on both native MariaDB and the guest. The parent must discard
the failed guest server; relying solely on normal framework test teardown is
insufficient. The recipe does so while preserving the original process exit.
Users still supply test settings and manage seed policy. Arbitrary projects,
multiple aliases and Ubuntu remain outside these local observations, so this
is not a product-adoption/support decision.

## Source and fixed boundary

Observed source_commit: `903e68cc021d894e56afdf6fba0bb70030de972e`, extending the
original W3 experiment directly over stable main bf3a29c. The pending Live
candidate is not an input. The original 13 application files, two migrations,
package versions and MariaDB12.3.3 image/program pins are unchanged. An explicit
seed fixture describes the same SEED row; failure_migrations reuses the original
first two migrations and adds one intentionally failing third migration.

The [manifest](../../tests/django_lifecycle/input-manifest.json) fixes execution
orders, suites, partial-DDL failure and resource limits before running.
Django5.2.8, mysqlclient2.2.7, pytest9.0.2 and pytest-django4.12.0 run on local
macOS arm64/Python3.11.17+3.14.9 with Go1.26.10. The native Linux-amd64 server is
emulated by Docker Desktop; image binding, exact per-program version/hash and
TCP startup identity are checked. No native Mac server or Ubuntu-host acquisition
PASS is inferred. Product SDK/runtime, guest/generated inputs and release files
have no diff.

## Mixed-order comparison

Each route runs normal, reverse, shuffle137 and shuffle911+reverse for each runner.
The actual recorded orders are four distinct sequences for every runner and
interpreter; native and each guest route match the same sequence and row/
transaction/commit/recovery event projection. Django's own TestCase-first grouping
is preserved. The test-only pytest collection hook permutes contiguous class and
function-parameter groups after normal plugin ordering, without replacing its
DB fixtures or interleaving class-level transaction owners.

| Route | Python3.11 | Python3.14 |
| --- | --- | --- |
| Native standard lifecycle | PASS,8 suites | PASS,8 suites |
| Guest standard lifecycle | PASS,8 suites | PASS,8 suites |
| Independent Fork campaign1 | PASS,8 suites | PASS,8 suites |
| Independent Fork campaign2 | PASS,8 suites | PASS,8 suites |
| Ubuntu x86_64 | NOT RUN | NOT RUN |

Total:64 mixed suite assessments and576 passing test executions, zero unexpected
errors/skips. Each Django suite has6 tests; each pytest suite has12 tests,
combining Django classes with ordinary db, transactional_db and serialized
function tests. Standard fixtures explicitly provide seed where default flush
would remove it. Serialized rollback remains a separate normal framework option.
Class setUpTestData, HTTP operations, exact duplicate errno1062 recovery, actual
commits visible through an independent connection and next-test isolation remain
in the workload. Every test checks its test database and migration records; the
original-schema sentinel remains17.

Fork remains one fresh child per runner invocation with keepdb/reuse-db, not one
child per test. Parent source consumption and final host/temp cleanup pass.
Framework create/destroy versus child-local kept schemas remain explicit route
semantics; no cache/setup-cost improvement was measured.

## Migration failure before admission

The third migration has two fixed SQL operations: create w3_partial_ddl, then
insert into nonexistent w3_missing_migration_table. On both interpreters and
both native/guest endpoints, both runners stop with process exit1 and retain
Django ProgrammingError -> MySQLdb ProgrammingError, errno1146. Original messages,
tracebacks and operation identity are retained; SQLSTATE is not asserted here.

Observed before parent cleanup:

- The test schema and partial-DDL table exist.
- The first two migration records exist; the failing third is not applied.
- Zero test bodies are admitted. Django never enters test execution; pytest
  reports two setup errors, one for each blocked test, with no body execution.
- The original schema sentinel remains17. The failed guest owner is not captured
  in a Snapshot or reused for a subsequent test.

All8 migration-failure assessments pass. Native parent cleanup explicitly drops
only its unique test schema after recording partial state. Guest parent cleanup
closes each fresh server and verifies process reaping and temp-directory removal.
Final task-native schema census is zero. These are expected setup failures, not
raw test passes or errors disabled to make migration succeed.

Pinned installed source explains the observation: DiscoverRunner performs DB
setup before its ordinary run/teardown try-finally, while pytest-django's DB
fixture fails before its yield/teardown path. Source hashes/function locations
are retained with the observations. See
[Django5.2.8 runner](https://github.com/django/django/blob/5.2.8/django/test/runner.py)
and [pytest-django4.12.0 fixtures](https://github.com/pytest-dev/pytest-django/blob/v4.12.0/pytest_django/fixtures.py).
The caller-discard policy is required for this recipe; it is not a new intrinsic
SDK ban on capturing arbitrary partially prepared database contents.

## User recipe verification

The [small runner](../examples/django/run_tests.py) starts one ordinary public
mariamem owner, configures the child process through environment/settings, runs
an ordinary test command, then closes the owner. Django owns per-test DB behavior.
The [settings example](../examples/django/example_settings.py) extends the actual
orders settings; the guide shows how to adapt an existing project's settings.

Both interpreters run both runners in normal mixed and failed-migration modes:
8 recipe runs pass their expected outcomes. Successful processes return0; setup
failures return1 with the original error still visible. The real owner is only
observed by the test probe, not force-cleaned by it: source closure, host reaping
and temp removal must already be complete after the recipe returns.
Additionally, Python3.11 executes both public CLI forms without the owner probe
or W3_EVENTS: Django6 tests/OK with shuffle137 and pytest12 passes with ordinary
plugin autoload. Normal collection without opt-in does not run the experiment.

## Evidence and remaining scope

[Assessment](v06x-django-mixed-evidence/local-903e68c/assessment.json),
[checksums](v06x-django-mixed-evidence/local-903e68c/SHA256SUMS.json) and encoded raw
observations retain all suites, actual orders, exception chains, XML/stdout,
recipe owner receipts, CLI output, source/binary identities and exact scripts.
Original92dc7fa observations remain under their original source and limits.
Owned workspace cleanup removed1,130,020,864 bytes with no remaining cleanup debt.
Task-native schemas, container, anonymous volume and downloaded image were also
removed; pre-existing native images were untouched.

This closes the requested local mixed-class/fixture and migration-failure/entry
extension. Ubuntu exact-source CI, independent multiple-test-module projects,
multiple aliases/routers, parallel workers, async/external resources and arbitrary
migration/app compatibility remain unverified. Whole W3/dogfood completion,
product adapter design, main adoption, version scope, Qualification and release
remain separate decisions.
