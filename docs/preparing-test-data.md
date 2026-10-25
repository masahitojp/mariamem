# Prepare once, test independently

This recipe targets unreleased source builds, not published v0.5.3. Use an
existing migration chain and seed to prepare one baseline per pytest worker;
each marked test starts an independent child from that baseline. A test's
committed changes do not become the next test's starting data.

`mariamem_prepare` is not tied to Alembic. It accepts a callback that receives
the preparation DB; that callback can invoke your own setup code. The concrete
recipe below uses synchronous Alembic with SQLAlchemy/PyMySQL. It does not
rewrite SQL or automatically redirect preparation SQL. The separate
[dump preparation recipe](importing-dump.md) describes the bounded reader candidate.

## An existing Alembic application

Install the source build with its `pytest` and `routing-sqlalchemy` extras,
plus your application's Alembic and seed dependencies. Routing currently uses
SQLAlchemy2.0.54/PyMySQL1.2.3; the acceptance fixture uses Alembic1.18.4. Keep
your application's migration configuration compatible with that tested driver
boundary; this is not a promise about arbitrary migration environments.

Declare the application's **original** endpoint and schema before application
imports. This profile has no password; it is the destination to intercept
during a test, not the temporary DB's address:

```toml
# pyproject.toml
[tool.pytest.ini_options]
mariamem_route_profiles = ["app = 127.0.0.1:3306/app"]
mariamem_route_drivers = ["pymysql"]
```

The following `conftest.py` assumes your Alembic `env.py` reads `sqlalchemy.url`
from its Config and closes/disposes its engine. The ordinary online pattern
is `engine_from_config(..., prefix="sqlalchemy.", poolclass=pool.NullPool)`;
see the [tested environment](../tests/preparation_migration_acceptance/migrations/env.py).
If your environment instead reads environment variables or an application
settings object, explicitly pass the temporary DB settings through that entry.
Changing a Config field that your environment ignores will not redirect it.

```python
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import URL, create_engine, text

ROOT = Path(__file__).resolve().parent


@pytest.fixture(scope="session")
def mariamem_prepare():
    def prepare(db):
        info = db.connection_info()
        source_url = URL.create(
            "mysql+pymysql",
            username=info["user"], password=info["password"],
            host=info["host"], port=info["port"], database=info["database"],
        )
        bootstrap = create_engine(source_url)
        try:
            with bootstrap.begin() as connection:
                connection.execute(text("CREATE DATABASE IF NOT EXISTS app"))
        finally:
            bootstrap.dispose()

        target_url = source_url.set(database="app")
        config = Config(str(ROOT / "alembic.ini"))
        # ConfigParser treats '%' specially; preserve URL-escaped credentials.
        config.set_main_option("sqlalchemy.url", target_url.render_as_string(
            hide_password=False).replace("%", "%%"))
        command.upgrade(config, "head")

        target = create_engine(target_url)
        try:
            with target.begin() as connection:
                # Replace this SQL with your seed using this explicit connection.
                # This example assumes migrations created users(id, name).
                connection.execute(text(
                    "INSERT INTO users(id, name) VALUES (1, 'baseline')"))
        finally:
            target.dispose()
        # Callback return is ignored; it is not a teardown callback.
    return prepare


@pytest.fixture(scope="session")
def mariamem_sqlalchemy_engines():
    from application.database import engine
    return (engine,)  # A quiescent, test-owned default QueuePool engine.
```

The seed uses the explicit connection above, rather than the application's
ordinary connection entry. Before a test binding exists, the registered
application profile refuses SQL with `missing_target`. Other endpoints are
outside that profile: inspect custom migration configuration before running it.
Do not log the preparation URL or credentials.

Now use the same marker for each test. These application functions stand for
your own code; their ordinary connection settings match the declared profile:

```python
import pytest
import application

pytestmark = pytest.mark.shadow_maria

def test_create_user():
    application.create_user()  # Normal application SQL and commit.
    # Assert through the application's API or mariamem_app_db.

def test_update_user():
    application.update_user()  # Begins with the baseline, not test_create_user's changes.
```

If direct SQL is needed alongside the application, request `mariamem_app_db`;
it is the same child used by the marker. See [connection routing](connection-routing.md)
for engine ownership, early guards and supported driver entries.

## Lifetime, parallel execution and failures

The default fixture chain runs preparation, waits for connections to close,
then captures the consuming Snapshot. Migration and seed code must finish its
transactions and close connections before returning. Do not call `snapshot()`
yourself inside the callback or return a cleanup function. Custom overrides of
`mariamem_snapshot` or `mariamem_fork` own their replacement lifecycle.

Normal `pytest` runs tests sequentially. With pytest-xdist installed,
`pytest -n 2` uses two workers. Each worker has its own preparation, host and
baseline, and its tests have independent mutable children. There is no shared
baseline across workers or saved baseline across runs. The acceptance harness
uses group scheduling to prove baseline reuse inside each worker; applications
do not need group markers merely to use `shadow_maria`.

If migration or seed raises, its original error is propagated and that
preparation chain produces no Snapshot or child. MariaDB DDL can persist before
a later migration error: failure does not mean all preceding DDL was rolled
back. The source is discarded through fixture cleanup; a new pytest run
prepares a fresh baseline. Another xdist worker has an independent chain and
may continue. The recipe adds no automatic retry or database repair policy.

The [candidate acceptance record](reviews/v06x-preparation-migration-productization.md)
records the completed Python3.11/pytest7, Python3.14/pytest9 and two-worker
native checks on macOS and Ubuntu. Arbitrary legacy applications,
Django/mysqlclient and dump import remain separate coverage decisions.
