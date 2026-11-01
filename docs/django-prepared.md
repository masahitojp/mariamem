# Prepared Django tests (candidate, Issue #43)

This entry is under development for consideration in v0.6.1. It is not in the
published v0.6.0 wheel and is not yet accepted on both supported platforms.
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

Install the candidate wheel with the `django` extra, or `django-pytest` for
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

`prepared_database()` explicitly starts an owned server when called, before
Django can connect. Importing `mariamem.django` alone starts nothing. The runner
or plugin closes it even after setup failure; process-exit cleanup is a fallback.
There is no fallback to the original application database. Do not perform SQL in
settings or `AppConfig.ready()`: test database creation has not happened yet.

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

Initial scope is Django5.2 (locally checked with5.2.8), mysqlclient2.2.7,
pytest9.0.2/pytest-django4.12.0, one `default` MySQL alias and serial execution.
Multiple aliases, test mirrors, disabled migrations, `available_apps`,
`serialized_rollback`, `reset_sequences`, `--keepdb`, `--reuse-db`, xdist and
Django parallel execution are rejected. Function-style pytest DB tests, async,
custom class teardown SQL, arbitrary projects and performance guarantees are
outside this candidate's acceptance. Custom `tearDownClass()` is rejected;
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
orders controls, then runs this public entry from the installed wheel on both
supported OSes and Python3.11/3.14. No new workflow, guest build or daily Live
campaign is added. Local source-entry checks with a reused published host are
recorded separately; they do not substitute for those installed-wheel cells.
