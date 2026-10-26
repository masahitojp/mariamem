# W3 Django standard runner lifecycle — local investigation

## Conclusion and recommendation

For the selected single-database orders application, ordinary Django MySQL
settings work with both manage.py test and pytest-django on mariamem. Recommend
an explicit settings/ownership recipe first: no new public Django adapter is
needed to make these selected tests connect and preserve framework semantics.
The observed native and guest event projections match on both local interpreters.

The main limitation is user wiring: an owner must start mariamem and pass the
endpoint before Django initializes settings. The experiment's parent process
provides that wiring; this is not zero-configuration Django integration. Fork
reuse is at runner-invocation granularity, while Django still provides isolation
between tests. A per-test Fork adapter would change another lifecycle boundary
and needs a separate design. No setup-cost or speed benefit was measured.

## Fixed source, inputs and execution boundary

Experiment source_commit: `92dc7faddd16ad330a080b52a0a01614600eed66`, based directly
on stable main `bf3a29c292064ddbbd4c7b9a9c6e712504d0f4e4`. The pending Live
candidate is not an input. Product SDK, runtime, guest, generated inputs and
release files have no diff. Only test owners, an unchanged copy of the W4 Python
application and this investigation's documents are added.

[Manifest](../../tests/django_lifecycle/input-manifest.json) pins the exact 13
application files from original a759cf8, two actual migrations and SEED data.
Django5.2.8, mysqlclient2.2.7, pytest9.0.2 and pytest-django4.12.0 are fixed
reproduction inputs, not a latest-version claim. The
[execution owner](../../tests/django_lifecycle/README.md) records commands, budget,
case selection and route semantics before execution.

Observed application/guest host: macOS arm64, Python3.11.17/3.14.9 and
Go1.26.10. Native MariaDB12.3.3 runs as Linux amd64 under Docker Desktop
emulation, using the exact existing digest. Image/container binding, per-program
version/hash and TCP startup identity match the fixed native input. This is not
an Ubuntu host observation or native Mac server acquisition evidence.

The first wrapper stopped before comparison because invoking a program by its
full path changes the version display's argv[0] prefix. Original bytes already
matched. Version queries were changed to use the same basename invocation as the
existing pin; full paths remain used for hashing. The original STOP and exact
reason are retained, not relabeled PASS.

## Confirmed comparisons

Each cell assesses ten two-test suites: ordinary/reversed Django atomic cases,
ordinary/reversed serialized transactional cases, default flush, exact failure
after commit, and four equivalent pytest-django modes.

| Route | Python3.11.17 | Python3.14.9 | Test DB lifecycle |
| --- | --- | --- | --- |
| Native MariaDB | PASS,10 suites | PASS,10 suites | Standard create/migrate/destroy |
| Guest with ordinary settings | PASS,10 suites | PASS,10 suites | Same framework create/migrate/destroy |
| Independent Fork campaign1 | PASS,10 suites | PASS,10 suites | Fresh Fork per suite; standard keepdb/reuse-db |
| Independent Fork campaign2 | PASS,10 suites | PASS,10 suites | Separate fresh Forks from the same immutable baseline |
| Ubuntu x86_64 | NOT RUN | NOT RUN | Required before supported-host adoption claims |

All 80 suite assessments pass. Raw tests contain **144 passes and16 deliberately
failed tests**, with zero unexpected errors or skips. The expected failures are
specific post-commit assertion failures; the parent requires the exact count and
marker. A separate final assessment also requires the first-test failure identity
and successful second-test identity. These are not160 raw pytest/unittest passes.

A separate deterministic comparison re-read all observations and matched each
guest route against its native counterpart: baseline rows, atomic/autocommit
state, on_commit callbacks, committed rows and exact duplicate errno1062.
Only the generated schema name is excluded from the event projection; explicit
create/destroy versus keepdb/reuse-db is a declared route difference.

Confirmed behavior:

- `TestCase` preserves migration SEED and class setUpTestData while rolling back
  each test; in-process HTTP POST/GET works. A nested savepoint recovers after
  duplicate errno1062. Explicit commit inside its outer atomic block is refused.
- Transactional cases can really commit: an independent physical mysqlclient
  connection sees the inserted row and on_commit executes.
- Default transactional flush leaves the next test's application table empty;
  the migration records remain. This matches native behavior and is not an
  isolation failure or an automatic migration-seed replay.
- `serialized_rollback=True` restores migration SEED before each transactional
  test, including after the deliberately failed committed mutation.
- The original schema sentinel remains17; every case queries its declared test
  DB and verifies both migration records. There is no original-target fallback.
- Standard runner test schemas are removed. Fork routes retain a test schema
  only inside the disposable child, then close that child. Both prepared-copy
  campaigns begin with the same SEED. Source consumption, shared-host reaping
  and temporary-directory removal all pass.

## Source investigation

Installed source hashes/function spans are preserved for six pinned modules,
independently in both interpreter environments. Inspected ownership agrees with
the runtime observations:

| Owner | Relevant boundary and implication |
| --- | --- |
| Django DiscoverRunner / test.utils | Choose used/serialized aliases, set up databases, run suite, then tear down |
| BaseDatabaseCreation / MySQL creation | Create a separate test schema, update the connection's NAME, apply migrations, optionally serialize, and destroy unless keepdb |
| TestCase | Class/per-test atomics and setUpTestData; a generic per-test backend swap would need to respect those owners |
| TransactionTestCase | Optional deserialization before tests; flush and connection reload after tests |
| pytest-django django_db_setup | Session database creation/serialization and optional reuse; original fixture is used unchanged |
| pytest-django _django_db_helper | Select TestCase or TransactionTestCase from fixtures/markers; its function-test class setup differs from direct Django TestCase |

Primary source references:
[Django5.2.8 testcases.py](https://github.com/django/django/blob/5.2.8/django/test/testcases.py),
[database creation](https://github.com/django/django/blob/5.2.8/django/db/backends/base/creation.py),
[pytest-django4.12.0 fixtures](https://github.com/pytest-dev/pytest-django/blob/v4.12.0/pytest_django/fixtures.py).
The framework's documented test DB and transactional-data policies are described
in [Django testing](https://docs.djangoproject.com/en/5.2/topics/testing/overview/)
and [pytest-django database access](https://pytest-django.readthedocs.io/en/latest/database.html);
installed pinned code and actual observations decide this result.

## Evidence and remaining conditions

[Assessment](v06x-django-lifecycle-evidence/local-92dc7fa/assessment.json),
[checksums](v06x-django-lifecycle-evidence/local-92dc7fa/SHA256SUMS.json) and encoded
raw observations preserve source/binary identities, all XML/JSON/events/stdout,
installed-source hashes, dependency installation, exact scripts and the initial
preflight STOP. Ordinary collection without opt-in does not run the workload.
Completed workspace cleanup removed1,128,808,448 bytes with no remaining cleanup
debt. The native schemas, container, anonymous volume and task-downloaded image
were removed; pre-existing images were untouched.

This closes the bounded local comparison, not the whole W3/dogfood register.
Before a supported-host adoption decision, run the same frozen cases on Ubuntu
x86_64 and retain exact-source CI receipts for both host OSes. A CI owner can
produce native receipts on Ubuntu and consume their source-bound events on Mac;
that split workflow has not been implemented here. Current local reproduction
requires the native control server to be reachable.

Migration failure before test admission, mixed-class/module order interactions,
multiple aliases/routers, xdist/Django parallel workers, async, retained external
connections and broader projects remain unverified. Add explicit cells before
claiming them. Product adapter/per-test Fork design, main integration, version
scope, Qualification and release remain separate decisions.
