# Run standard Django tests against a disposable MariaDB

This source example starts one mariamem server, passes its endpoint to ordinary
Django settings, runs `manage.py test` or pytest-django, and closes the server.
Django creates/migrates its own test database and owns per-test transactions and
flush. A failed test process keeps its original exit code. If migration fails
partway through DDL, leaving the parent owner's context also discards that whole
server. The example has no Django backend replacement or test lifecycle adapter.

Use adopted unreleased main, Go1.26.10 and Python3.11 or3.14.
This is not a published-package Django support claim. The repository example
uses the same authored orders app/migrations as the earlier browser scenario.

```sh
python3 scripts/git_identity.py inspect HEAD
mkdir -p build/django-example
export GOCACHE="$PWD/build/django-example/go-build"
export GOPATH="$PWD/build/django-example/gopath"
export GOMODCACHE="$PWD/build/django-example/modcache"
go build -p 1 -trimpath -o build/django-example/mariamem-host ./cmd/mariamem-host
python3 -m venv build/django-example/venv
build/django-example/venv/bin/python -m pip install -r tests/django_lifecycle/requirements.txt
PYTHONPATH="$PWD/python:$PWD/tests/django_lifecycle" \
  build/django-example/venv/bin/python docs/examples/django/run_tests.py \
  --host build/django-example/mariamem-host \
  --project tests/e2e_native_control/pythonapp --settings example_settings \
  --runner manage -- mixed_cases --shuffle=137
```

mysqlclient needs native headers/pkg-config: Ubuntu uses `pkg-config` and
`default-libmysqlclient-dev`; macOS uses `pkgconf` and `mariadb-connector-c`
with its `lib/pkgconfig` directory in `PKG_CONFIG_PATH`. The
[workflow](../../../.github/workflows/django-lifecycle.yml) shows those steps.
For pytest, use the same command with the last line replaced by:

```sh
  --runner pytest -- "$PWD/tests/django_lifecycle/test_mixed_cases.py" -v
```

The repository's pytest module is opt-in: also set `W3_RUN=1` for that particular
sample command. Your application's ordinary test modules need no such switch.
No browser is installed or started by this recipe. Generated output and
task-owned caches live under `build/django-example`; remove
that directory and unset the three Go cache variables after all owned test
processes finish. Under supervised development, use a prepared bounded experiment
workspace and request the coordinator’s exclusive lease before this host build
or a functional campaign.

## Use your project

Keep your application's existing settings and add a test settings module that
reads the supplied `E2E_DB_HOST`, `E2E_DB_PORT` and `E2E_DB_NAME` environment values:

```python
from myproject.settings import *
import os
DATABASES = {'default': {
    'ENGINE': 'django.db.backends.mysql',
    'HOST': os.environ['E2E_DB_HOST'],
    'PORT': int(os.environ['E2E_DB_PORT']),
    'NAME': os.environ['E2E_DB_NAME'],
    'USER': 'root', 'PASSWORD': '',
    'TEST': {'NAME': 'test_myproject'},
}}
```

Point `--project` to the folder containing manage.py, `--settings` to that test
settings module, and pass your test labels/paths after `--`. Preserve any
application-specific charset, SQL-mode or other required options from your normal
configuration. Install pytest-django when selecting the pytest runner. The
repository's PYTHONPATH includes its source SDK and authored tests; an installed
application uses its own normal import paths.

## Seed data in a mixed suite

Default `TransactionTestCase` flush does not replay a data migration. For data
needed before every such test, use Django's standard `fixtures` attribute or an
explicit pytest fixture depending on `transactional_db`. The authored mixed suite
uses `orders_seed.json`; it describes the same SEED row as the original migration.
Serialized rollback is also exercised separately, using Django's normal
`serialized_rollback=True` / pytest-django marker. DB reset does not clear
application caches or external services.

This recipe uses one server per runner invocation. Django owns per-test
isolation; this entry does not prepare or reuse a Snapshot.
Supported-host and broader-project acceptance remain separate from historical
local observations.

The [Django guide](../../django-testing.md) records original receipt identities
and the successful native and Ubuntu/macOS/Python3.11/3.14 comparison matrix.
Historical local receipts retain their original sources; the later adopted
native/guest matrix supports only this bounded recipe. The additional D1 prepared
entry is deferred to consideration in0.6.1, not a delivery promise; see the
[D1 decision](../../decisions/d1-v060-deferral.md).
