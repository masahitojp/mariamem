# Run standard Django tests against a disposable MariaDB

This source example starts one mariamem server, passes its endpoint to ordinary
Django settings, runs `manage.py test` or pytest-django, and closes the server.
Django creates/migrates its own test database and owns per-test transactions and
flush. A failed test process keeps its original exit code. If migration fails
partway through DDL, leaving the parent owner's context also discards that whole
server. The example has no Django backend replacement or test lifecycle adapter.

Use the current experiment source, Go1.26.10 and a supported Python interpreter.
This is not a published-package Django support claim. The repository example
uses the same authored orders app/migrations as the earlier browser scenario.

```sh
mkdir -p build/django-example
go build -p 1 -trimpath -o build/django-example/mariamem-host ./cmd/mariamem-host
python3 -m venv build/django-example/venv
build/django-example/venv/bin/python -m pip install -r tests/django_lifecycle/requirements.txt
PYTHONPATH="$PWD/python:$PWD/tests/django_lifecycle" \
  build/django-example/venv/bin/python docs/examples/django/run_tests.py \
  --host build/django-example/mariamem-host \
  --project tests/e2e_native_control/pythonapp --settings example_settings \
  --runner manage -- mixed_cases --shuffle=137
```

mysqlclient needs the usual native headers/pkg-config. Use the native package
setup already documented in [the lifecycle experiment](../../../tests/django_lifecycle/README.md).
For pytest, use the same command with the last line replaced by:

```sh
  --runner pytest -- "$PWD/tests/django_lifecycle/test_mixed_cases.py" -v
```

The repository's pytest module is opt-in: also set `W3_RUN=1` for that particular
sample command. Your application's ordinary test modules need no such switch.
No browser is installed or started by this recipe. Generated output lives under
`build/django-example` and can be removed after the test processes finish.

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

This recipe uses one server per runner invocation. The
[Snapshot/Fork experiment](../../../tests/django_lifecycle/README.md) explores
reuse between runner invocations; it does not replace Django's per-test isolation.
Supported-host and broader-project acceptance remain separate from the local
experiment observations.
