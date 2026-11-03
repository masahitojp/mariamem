# Prepared Django tests (adopted on main, unreleased)

This entry was adopted on main through [PR #67](https://github.com/masahitojp/mariamem/pull/67).
It is not in the published v0.6.0 wheel. Both supported OSes with Python3.11/3.14
passed installed-wheel acceptance on the reviewed candidate; see the
[receipt and exact source](reviews/d1-release-41320361521/README.md).
The [startup/routing follow-up receipt](reviews/d1-release-41327745652/README.md)
confirms fresh four-cell installed-wheel acceptance and READY for its own
reviewed source. Release version and publication remain separate.
The existing [standard-runner recipe](django-testing.md) remains available.

Use this entry when every test must start from the same migrated schema and
seed, including after committed writes, DDL or an ordinary test failure. A run
owns one mariamem lineage. Django creates and migrates its test database; the
optional preparation callback runs once, then the disconnected source becomes a
Snapshot. Each prepared class gets a child for class setup. Its prepared state
becomes a class Snapshot, and every test gets an independent Fork. Final cleanup
gives Django another disposable child for its normal database destruction,
then closes all remaining owners.

## Explicit test settings

Install a wheel built from the adopted main source with the `django` extra, or `django-pytest` for
pytest-django. These extras do not change ordinary mariamem imports and do not
register the Django plugin automatically. Use dedicated test settings:

```python
# myproject/test_settings.py
from .settings import *
from mariamem.django import prepared_database

DATABASES = {"default": prepared_database(test_name="test_mariamem")}
TEST_RUNNER = "mariamem.django.PreparedDiscoverRunner"
MARIAMEM_DJANGO_PREPARE = "myproject.test_seed.prepare"  # optional
```

`prepared_database()` only declares test settings. Settings import,
`manage.py check`, `manage.py shell`, test discovery and `pytest --collect-only`
do not start a server. The runner acquires one immediately before Django's
`setup_databases()` creates/migrates the test DB; pytest acquires it at its
corresponding database-setup fixture. Database-free suites acquire none.
The runner or plugin closes it even after setup failure; process-exit cleanup is
a fallback registered only after acquisition. SQL outside this lifecycle is
rejected with `ImproperlyConfigured` before the driver can connect, including SQL
from a shell, settings or `AppConfig.ready()`. There is no fallback to the
original application database. Keep the helper's guarded backend setting; it
delegates normal SQL to Django's MySQL backend after acquisition.

`test_name` must start with `test_` and contain only letters, digits or underscores.
The optional `options` mapping passes ordinary `mariamem.start()` options, such as
`host_binary`, to the SDK. Do not share this configuration with another active
runner. A completed run can acquire a fresh lineage on a subsequent invocation.

The seed callback receives the migrated Django `default` connection, executes
once per run, and must finish its transactions and close any separate physical
connections it opens. A callable may also be supplied directly. Its return value
is ignored. For example, if the application has a `Product` model:

```python
# myproject/test_seed.py
from myproject.catalog.models import Product


def prepare(connection):
    Product.objects.create(sku="SEED", quantity=2)
```

A callback failure or failure to disconnect prevents all test bodies. It never
captures a partly prepared baseline or quietly continues against another DB.

## Prepared classes

```python
from django.db import transaction
from mariamem.django import PreparedTestCase, PreparedTransactionTestCase
from myproject.catalog.models import Product


class ProductTests(PreparedTestCase):
    @classmethod
    def setUpTestData(cls):
        cls.product = Product.objects.create(sku="CLASS", quantity=7)

    def test_mutation(self):
        self.product.quantity = 99
        self.product.save()

    def test_original_class_state(self):
        self.assertEqual(self.product.quantity, 7)
        self.assertTrue(Product.objects.filter(sku="SEED").exists())


class CommitTests(PreparedTransactionTestCase):
    def test_commit(self):
        with transaction.atomic():
            Product.objects.create(sku="COMMITTED")

    def test_original_seed(self):
        self.assertFalse(Product.objects.filter(sku="COMMITTED").exists())
        self.assertTrue(Product.objects.filter(sku="SEED").exists())
```

These assertions must also hold in reverse order. If `test_commit` raises after
the transaction commits, the failure remains a failure and the next admitted
test still gets the prepared state. The maintained
[orders campaign](../tests/django_prepared/cases.py) checks those cases, non-model
SQL state, class data copies and commits visible to a separate connection.

Run Django with:

```sh
python manage.py test --settings=myproject.test_settings
```

For pytest, load both plugins explicitly and use the same prepared classes:

```sh
DJANGO_SETTINGS_MODULE=myproject.test_settings \
  python -m pytest -p pytest_django.plugin -p mariamem.django.pytest_plugin
```

When pytest-django already auto-loads, omit its explicit `-p` argument.
Function-style `django_db` tests and ordinary Django database classes cannot be
mixed into this prepared run. `SimpleTestCase` tests without database access may
coexist. The ordinary recipe still supports its independently tested policies.

## Local pytest-xdist workers

The local-worker extension is adopted on main and remains unreleased.
Its four installed-wheel cells passed; see the [adoption receipt](reviews/d1-xdist-adoption.md).
Serial remains default. The `django-pytest` extra supplies pytest-xdist3.8.0 / execnet2.1.2.
Keep the ordinary serial invocation, or opt in with an explicit worker count:

```sh
DJANGO_SETTINGS_MODULE=myproject.test_settings \
  python -m pytest -p mariamem.django.pytest_plugin -n 2 --dist=loadscope
```

### Configure worker count

Use a current-source wheel with the `django-pytest` extra; published 0.6.0 does
not include this prepared entry. First configure the dedicated settings and
plugin, for example in your project's `pytest.ini`:

```ini
[pytest]
DJANGO_SETTINGS_MODULE = myproject.test_settings
addopts = -p mariamem.django.pytest_plugin
```

Then choose an explicit count for each invocation:

```sh
python -m pytest                         # serial: default
python -m pytest -n 2 --dist=loadscope    # start with two local workers
python -m pytest -n 4 --dist=loadscope    # four workers when useful and affordable
```

For a project that deliberately chooses parallel as its own default, change
`addopts` to `-p mariamem.django.pytest_plugin -n 2 --dist=loadscope`.
Override that setting with `python -m pytest -n 0` for a serial diagnostic run.
This project setting does not change mariamem's serial default.

In CI, use the same fixed command rather than detecting all CPUs. Add
`--max-worker-restart=0` if you want to disable replacement of crashed workers;
the crashed test remains failed with or without replacement. The runner/job
owns scratch cleanup after forced termination. `manage.py test` remains a
serial alternative; its `--parallel` mode is not connected to this lifecycle.

pytest-django and xdist normally auto-load from the installed extras. With
`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`, explicitly load `-p pytest_django.plugin`
and `-p xdist.plugin` as well as the mariamem plugin. The supported schedulers are `load` and `loadscope`;2 and4 local workers
are the verification cells, not a capacity guarantee. `loadscope` keeps a class
on one worker. With `load`, class setup and `setUpTestData()` execute per worker/class
activation. Restart/rescheduling may revisit a class and execute setup again
even in the same worker. Do not use class setup as a globally-once hook.

Each DB-using worker acquires its own host, migrates/seeds once, and owns its own
run/class Snapshots. No SDK handles are passed between processes. Preparation is
per worker, not once globally: four DB-using workers mean four preparations and
four hosts. The controller, idle workers and database-free workers acquire none.
pytest-django's worker DB-name suffix remains in effect. Choose a worker count
for the suite and its memory budget; local observations below are not a general
performance or resource guarantee.

An ordinary assertion failure still allows the next independent Fork. Prepare
failure or cleanup debt blocks later dependent bodies in that worker and leaves
the overall test run failed; another worker has its own owners. A crashed test
remains failed. If xdist restarts its worker, the replacement creates a fresh
host and baseline rather than inheriting the crashed test's handles. With
`--max-worker-restart=0`, xdist stops distribution according to its normal policy.

On hard worker death, the existing host control-pipe EOF path closes the host.
Python finalizers cannot run after SIGKILL: SDK temporary logs/directories may
remain for the enclosing runner/job to clean. This is not a new arbitrary
process-tree kill or scratch-recovery guarantee. Normal worker shutdown closes
its owners and scratch through the SDK as before.

Use explicit `-n N`; automatic/logical CPU counts, manual `--tx`, remote/socket
workers and loop-on-fail are rejected before acquisition. Other schedulers and
Django `manage.py test --parallel` remain unsupported. Multi-alias, reuse-db,
no-migrations and routing/shadow_maria exclusions remain unchanged.

### Choose a worker count

- Keep serial for short suites, constrained memory or lifecycle diagnosis.
- Try 2 workers first when parallelizing. Compare complete test-run time,
  including migration/seed and cleanup, against serial.
- Try 4 only when enough independent classes/tests and memory headroom justify
  it. Four DB-using workers each prepare their own baseline; startup/seed work
  and memory consumption increase. `-n auto` / `-n logical` are unsupported.

A bounded M1/Python3.14/Django 6.1.2 measurement illustrates the tradeoff. Heavy
preparation added 20 indexed tables and 20,000 rows (~9.77MiB seed payload).
For 48 tests, 2 workers took 3.74s and 4 took 3.86s; at 120 tests, 4 workers took 5.64s
versus 6.39s for 2 workers (medians of 3 runs). There is no universal 120-test
threshold; the number and distribution of classes, preparation cost and data
footprint matter.

Observed maximum summed RSS over pytest/controller, Python workers and hosts:

| Preparation in that workload | Serial | 2 workers | 4 workers |
| --- | --- | --- | --- |
| Light | 203MiB | 468MiB | 868MiB |
| Heavy | 258MiB | 574MiB | 1080MiB |

These sampled RSS sums can double-count shared pages and miss brief peaks;
they are not unique physical memory or portable CI memory limits. The preparation
also enlarged the captured baseline, so this does not isolate only fixed startup
cost. Measure your own suite before increasing workers. See the
[pinned measurement and reproduction recipe](https://github.com/masahitojp/mariamem/blob/d779657732e6f773f568f0bcbce72644f130d567/benchmarks/d1-xdist-resources/README.md)
for the complete conditions, sampling overhead, timings and limits. Serial
remains the product default; this guidance introduces no auto-tuning.

## Routing and shadow_maria

The prepared Django entry and routing/`shadow_maria` are mutually exclusive
within one test invocation. Collection rejects `shadow_maria` markers (including
inherited class/module marks) and `mariamem_app_db`, and setup rejects an active
routing registry before acquiring a host. Do not combine this entry with routing profiles,
`shadow_maria`, a manual routing registry or SQLAlchemy engine enrollment. Choose
one connection owner for the run. Django prepared classes let the runner/plugin
switch Django's `default` connection between owned Forks; routing redirects
explicitly enrolled application connections and pools through its own fixture
lifecycle. Their combined switching, preparation and cleanup order is undefined
and unverified. These guards cover the declared entrypoints; they are not a
guarantee that every custom hook or later manual combination is detected. The ordinary mariamem pytest plugin may remain
loaded when its routing features are unused. Run routing tests separately with
separate settings, and retire their physical connections before starting another
owner. Combining the two into one entry requires a separate design comparison.

## Differences and initial limits

`PreparedTestCase` keeps Django's per-test atomic block, but **does not use a
class-wide atomic block**. Fixtures and `setUpTestData()` run once in autocommit
before class capture. In particular, `on_commit()` during class preparation can
run immediately. Class data uses Django's per-instance deep-copy descriptors.
A `setUpClass()` override must call `super()`; SQL after that call is included
when the class is captured immediately before its first test. This is explicit
opt-in behavior, not transparent replacement of existing `TestCase` classes.

`PreparedTransactionTestCase` allows real commits and retains Django's per-test
fixtures/flush hooks; the next test's Fork restores the declared full schema and
seed independently of flush. It has no `setUpTestData()` hook.

Supported Django series are5.2 LTS,6.0 and6.1; Django6 requires Python3.12+.
See the [version policy](django-testing.md#supported-django-versions). The fixed client profile is mysqlclient2.2.7,
pytest9.0.2/pytest-django4.12.0, one `default` MySQL alias. Serial remains the
default; the local-worker mode is described above.
Multiple aliases, test mirrors, disabled migrations, `available_apps`,
`serialized_rollback`, `reset_sequences`, `--keepdb`, `--reuse-db` and
Django parallel execution are rejected. Local xdist permits only the local
mode above. Function-style pytest DB tests, async,
custom class teardown SQL, arbitrary projects and performance guarantees are
outside this entry's accepted scope. Custom `tearDownClass()` is rejected;
`addClassCleanup()` is for non-database resources. Test hooks must cooperate with
their superclass. Independent connections must be closed by their owner before
capture or retirement; retained connections stop admission.

Failures preserve original exceptions. When cleanup also fails, both errors are
reported in an exception group. Any child retirement failure stops further test
admission in that run; finalization still attempts every remaining owner. A later
successful close does not silently resume the failed run. This does not promise
to recover a host crash or make an interrupted test pass.

## Verification placement

Daily checks use deterministic ownership/policy tests without starting hosts.
The existing Release Django job reuses its shared wheel/host and pinned native
orders controls, then runs the serial and local-worker entries from the installed wheel on both
supported OSes and Python3.11/3.14. No new workflow, guest build or daily Live
campaign is added. Local source-entry checks with a reused published host are
recorded separately; they do not substitute for those installed-wheel cells.
