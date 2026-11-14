# Python usage

Use Python `0.6.2` on a [supported platform](../README.md#installation).
Start with one database, then share preparation when setup becomes expensive.
For Django, use the [dedicated guide](django-prepared.md).

The initial PyPI distribution targets macOS 15+ arm64. Its first upload has
succeeded; public smoke is still pending. Use the GitHub wheel in the installation
guide until completion. After that check, macOS users can install
`python -m pip install "mariamem[test]==0.6.2"`. Ubuntu 24.04 x86_64 continues
to use its GitHub Release wheel. No Linux/Windows PyPI support is implied.

## A disposable database

Use `mariamem.start()` to acquire a database and `connection_info()` to connect
with an ordinary MySQL driver.

```python
import mariamem
import pymysql

with mariamem.start() as db:
    with pymysql.connect(**db.connection_info()) as conn:
        with conn.cursor() as cur:
            cur.execute("CREATE TABLE users(id INT PRIMARY KEY) ENGINE=InnoDB")
            cur.execute("INSERT INTO users VALUES(1)")
        conn.commit()
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM users")
            assert cur.fetchone() == (1,)
```

Use Fresh for small setup. Every fresh database begins from the initial state.
Application connections may commit and roll back normally; isolation comes from
discarding the entire database, not from a test transaction imposed by mariamem.
Close your driver connections before database cleanup.

The local endpoint accepts any username and password, including
test credentials such as `test/test` or `root/root`. Credentials are not
validated and do not select a guest account or change SQL privileges. The
returned connection information still defaults to `root` with an empty
password. Use a real server for authentication and per-user privilege tests.

`close()` is idempotent. `closed` reports disposal or host termination; call
`close()` to release wrapper resources after termination as well.

## pytest fixtures

Use the platform wheel with the `test` extra from [installation](../README.md#installation).
Save the preparation callback as `conftest.py`:

```python
# conftest.py
import pytest
import pymysql


@pytest.fixture(scope="session")
def mariamem_prepare():
    def prepare(db):
        with pymysql.connect(**db.connection_info()) as conn:
            with conn.cursor() as cur:
                cur.execute("CREATE TABLE users(id INT PRIMARY KEY) ENGINE=InnoDB")
                cur.execute("INSERT INTO users VALUES(1)")
            conn.commit()
    return prepare
```

Commit your preparation transactions and close all driver connections before
returning. Do not call `snapshot()` or return a teardown function from this
callback. `None` selects no preparation; a `PrepareCommand` is the alternative
[command entry](#prepared-command-entry). Override `mariamem_snapshot` only when
you deliberately own capture/disconnect and baseline cleanup yourself. That explicit override owns the preparation route.

Put the tests in `test_users.py`. Each request for `mariamem_connection_info`
depends on a function-scoped `mariamem_fork`; its fixture closes the child after
the test. The test closes its own SQL connection before that teardown:

```python
import pymysql


class TestUsers:
    def test_commit(self, mariamem_connection_info):
        with pymysql.connect(**mariamem_connection_info) as conn:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO users VALUES(2)")
            conn.commit()

    def test_initial_state(self, mariamem_connection_info):
        with pymysql.connect(**mariamem_connection_info) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id FROM users ORDER BY id")
                assert cur.fetchall() == ((1,),)
```

Either order, or either test alone, sees the same baseline. A class groups tests;
it does not share one mutable database. Use the function-scoped fixtures for per-test mutable state.

Run the same tests sequentially with ordinary pytest, or distribute them across
processes with pytest-xdist. The `test` extra used in the README includes it;
if you installed only `pytest` and PyMySQL, also run
`python -m pip install pytest-xdist`:

```sh
python -m pytest test_users.py          # Sequential: one session baseline.
python -m pytest -n 4 test_users.py     # Parallel: one session baseline per worker.
```

Each pytest-xdist worker has its own session fixtures and therefore prepares
its own baseline. A session fixture is worker-local, not shared across workers.
Tests assigned to that worker receive independent children from its baseline.
Fixture dependency teardown closes each child before the worker's baseline.
There is no automatic run-wide baseline, cross-worker cache
or cross-run reuse policy. Prepare each worker's baseline from migrations/seed
with `snapshot()`; a saved Snapshot artifact is not an input in this version.

For a migration/seed callback using explicit Alembic configuration, see
[prepare once, test independently](preparing-test-data.md).
For ordinary `manage.py test` or pytest-django ownership, see the
[Django standard-runner recipe](django-testing.md).

The pytest plugin provides `@pytest.mark.shadow_maria` for existing application
connections, `mariamem_prepare` for session preparation and optional
`mariamem_app_db`, `mariamem_router`, `mariamem_sqlalchemy_engines` fixtures.
Declare the original endpoint/schema before application imports, prepare that
schema using explicit preparation DB settings, and explicitly register quiescent pools. See the
[routing guide](connection-routing.md) for configuration, first/second-test
examples, ownership, supported entries and actionable failures. Existing fixtures above retain their defaults.

### Existing application connections: shadow_maria

Use the marker when application code creates its own driver connections. The
following is a separate, complete example: put these files in a new directory
instead of combining its `conftest.py` with the earlier direct-fixture example.
Install the published platform wheel with the `pytest` and `routing-pymysql` extras (the latter
pins the supported PyMySQL1.2.3 entry).

Declare the application's **original** host/port/schema in `pyproject.toml` so
the plugin installs its guard before application imports. These are matching
settings, not the temporary database's generated endpoint:

```toml
[tool.pytest.ini_options]
mariamem_route_profiles = ["app = 127.0.0.1:3306/app"]
mariamem_route_drivers = ["pymysql"]
```

Prepare the declared `app` schema using the explicit source connection. This
callback does not use application routing:

```python
# conftest.py
import pytest
import pymysql


@pytest.fixture(scope="session")
def mariamem_prepare():
    def prepare(db):
        with pymysql.connect(**db.connection_info()) as conn:
            with conn.cursor() as cur:
                cur.execute("CREATE DATABASE app")
                cur.execute("CREATE TABLE app.users(id INT PRIMARY KEY) ENGINE=InnoDB")
                cur.execute("INSERT INTO app.users VALUES(1)")
            conn.commit()
    return prepare
```

The application keeps ordinary connection calls and commits; it imports no
mariamem code and opens connections only when its functions are called:

```python
# app.py
import pymysql


def _connect():
    return pymysql.connect(
        host="127.0.0.1", port=3306, user="app", database="app"
    )


def create_user(user_id):
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute("INSERT INTO users VALUES(%s)", (user_id,))
        conn.commit()


def user_ids():
    with _connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM users ORDER BY id")
            return [row[0] for row in cur.fetchall()]
```

Apply the same marker to each test:

```python
# test_app.py
import pytest
import app


@pytest.mark.shadow_maria
def test_create_user():
    app.create_user(2)  # Ordinary application connection and commit.
    assert app.user_ids() == [1, 2]


@pytest.mark.shadow_maria
def test_initial_state():
    assert app.user_ids() == [1]  # A fresh child, even after the other test commits.
```

Run `python -m pytest test_app.py`. Each marked test routes the registered
profile to its own prepared child; no database server is needed at the original
address. The first test sees its committed insert and the second starts from
seed1 in either order. The marker adds no transaction rollback wrapper. A module
can instead use `pytestmark = pytest.mark.shadow_maria` for all its tests.

Keep SQL out of module import, finish work and close connections before test
teardown. A connection to the registered profile without an active test binding
is refused, rather than sent to the original database. Unregistered endpoints
are outside this guard. Existing pools need explicit enrollment; see the
[routing guide](connection-routing.md). For direct SQL assertions in a marked
test, `mariamem_app_db` is the same child as the marker. The marker does not
provide a stable Live endpoint for a session-scoped application.

### Prepared command entry

The package supports the public class
`mariamem.PrepareCommand(argv, *, timeout=120, cwd=None, env=None)` as a third
`mariamem_prepare` input. None and callback behavior are unchanged, including
ignored callback return values. Unknown values are rejected with
`pytest.UsageError`; they are never silently ignored.

This is an alternative to the callback example: replace `mariamem_prepare` in
that example, create the script below, and reuse `test_users.py`. Do not define
two preparation fixtures with the same name. Run pytest from the project root
containing `tools/` and `test_users.py`.

```python
# conftest.py
import sys
import pytest
from mariamem import PrepareCommand

@pytest.fixture(scope="session")
def mariamem_prepare():
    return PrepareCommand([sys.executable, "tools/migrate_and_seed.py"], timeout=60)
```

Your script explicitly supplies these settings to its migration/seed operation:

```python
# tools/migrate_and_seed.py
import json
import os

import pymysql

info = json.loads(os.environ["MARIAMEM_PREPARE_CONNECTION_INFO"])
with pymysql.connect(**info) as conn:
    with conn.cursor() as cur:
        cur.execute("CREATE TABLE users(id INT PRIMARY KEY) ENGINE=InnoDB")
        cur.execute("INSERT INTO users VALUES(1)")
    conn.commit()
```

The entry launches the argv sequence once without a shell. An exit code of zero
is success; exceptions/nonzero exit, timeout or interrupt admit no dependent
child. This does not validate application business correctness or automatically
route a framework's preparation connections. No Django or additional driver
profile is implied.

The descriptor copies argv/env at declaration. `env` overlays a copy of the
parent environment at execution; PATH is retained unless explicitly overridden.
The entry always supplies its actual connection JSON, replacing any inherited
MARIAMEM_PREPARE_CONNECTION_INFO. Supplying that reserved key in the descriptor
is rejected. Inherited environment is an explicit input, not hermetic execution:
record relevant application settings when reproducing a failure. The parent
environment and working directory are not mutated. `cwd` defaults to pytest's
rootpath; relative cwd is resolved against it. timeout is positive and finite,
not bool. Avoid credentials in argv and application output; the entry does not
print environment values or infer redaction of arbitrary application logs.

Output is drained concurrently but retains only the last 16 KiB of stdout and
last 16 KiB of stderr. On command exceptions, inspect `.stdout` / `.stderr`
(bytes), `.stdout_truncated` / `.stderr_truncated`, and
`.stdout_dropped_bytes` / `.stderr_dropped_bytes`. Exceptions retain their
CalledProcessError/TimeoutExpired type and original exit/timeout data; diagnostic
previews explicitly label application output and truncation. A full transcript
is not retained. Interrupt remains KeyboardInterrupt, including finalization.
If cleanup is interrupted after an ordinary operation failure, the interrupt
is raised with the original operation failure as its cause. Timeout/interrupt attempt
bounded termination and reaping of the owned process group; cleanup may be
unconfirmed. Noncooperative Python callbacks, escaped daemon processes, hard
kill and machine loss have no stronger guarantee.

### Prepared-entry cleanup failures

The adopted prepared entry changes admission after cleanup failure. A supplied
child or routing/pool finalizer failure stops later dependent tests in the
same worker and retains its original cause. Other workers are independent.
A normal test assertion failure with successful cleanup does **not** stop the
next independent child. This is not a global pytest fail-fast option.

The entry adds operation/state notes to its own failures and observes the named
preparation fixture, preserving pytest's original setup/call/teardown reports.
Its final summary distinguishes entry-owned finalizers completed from
unconfirmed cleanup. Completed helper finalization does not prove capture's
internal cleanup. Combined cleanup errors remain attached as `.cleanup_errors` where the exception
allows metadata, or retained through the cause chain for read-only exceptions;
source/baseline/test teardown still attempts remaining finalizers.
Explicitly overriding a supplied fixture transfers that boundary's ownership to
your implementation, including admission and cleanup. See the
[release notes](../release/NOTES-v0.6.2.md).

## Share preparation, isolate mutations

### Sequential Forks in one process

A Snapshot fixes the current schema/data as a baseline. It does not retain a
running server or read a SQL fixture file. Load SQL fixtures through your driver
before taking it. This manual example runs one child at a time:

```python
import mariamem
import pymysql


with mariamem.start() as setup_db:
    with pymysql.connect(**setup_db.connection_info()) as conn:
        with conn.cursor() as cur:
            cur.execute("CREATE TABLE users(id INT PRIMARY KEY) ENGINE=InnoDB")
            cur.execute("INSERT INTO users VALUES(1)")
        conn.commit()
    setup_db.wait_disconnected()

    with setup_db.snapshot(max_forks=1) as baseline:
        with baseline.fork(timeout=30) as db:
            with pymysql.connect(**db.connection_info()) as conn:
                with conn.cursor() as cur:
                    cur.execute("INSERT INTO users VALUES(2)")
                conn.commit()
        with baseline.fork(timeout=30) as db:
            with pymysql.connect(**db.connection_info()) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT id FROM users ORDER BY id")
                    assert cur.fetchall() == ((1,),)
```

Successful `snapshot()` ends the source DB. Close all SQL clients, then call
`wait_disconnected()` to wait for session cleanup. Active query/handshake/cleanup
is rejected with `Busy`; an active transaction is rejected with
`TransactionActive` unless `rollback=True` is explicit. These precondition
rejections keep the source available. A failure after capture was accepted
may consume it; `HostError.closed` identifies that outcome.

Each `fork()` starts an independent mutable DB with the baseline's schema/data.
Children do not inherit connections or active transactions. Child writes,
schema changes and file growth never update their siblings or the baseline.
A modified child may be snapshotted into a new baseline.

Concurrent Fork startups are supported. Closing the baseline prevents further
Forks; successfully started children remain usable. Close each child separately.
The baseline context releases its owned resources after admitted launches.
Snapshot content stays in memory; no user-managed filesystem artifact is needed.

`baseline.fork(**options)` inherits the preparation DB's options with supplied
overrides. `mariamem.start(snapshot=baseline, ...)` also creates a child from the
owned baseline, using the supplied start options. These are alternative
creation routes, not successive steps.

## Parallel Forks in one process

For manual concurrency, share one open Snapshot between threads in the same
process. This complete example uses two threads and an explicit two-child cap,
with a 30-second capacity wait per child. Each task acquires its own child and
SQL connection. This is separate from pytest-xdist, whose workers prepare independent baselines.

```python
from concurrent.futures import ThreadPoolExecutor

import mariamem
import pymysql


def check_child(baseline, user_id):
    with baseline.fork(timeout=30) as db:
        with pymysql.connect(**db.connection_info()) as conn:
            with conn.cursor() as cur:
                cur.execute("INSERT INTO users VALUES(%s)", (user_id,))
            conn.commit()
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM users")
                assert cur.fetchone() == (2,)  # Seed + this child's own insert.
    # SQL connection closes before the child, including on an exception.


with mariamem.start() as setup_db:
    with pymysql.connect(**setup_db.connection_info()) as conn:
        with conn.cursor() as cur:
            cur.execute("CREATE TABLE users(id INT PRIMARY KEY) ENGINE=InnoDB")
            cur.execute("INSERT INTO users VALUES(1)")
        conn.commit()
    setup_db.wait_disconnected()
    with setup_db.snapshot(max_forks=2) as baseline:
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(check_child, baseline, i) for i in range(2, 6)]
            for future in futures:
                future.result()  # Propagate startup, SQL, assertion or cleanup errors.
        # Executor exit joins every submitted task before baseline exit closes it.
```

If a result raises, executor teardown still waits for all submitted tasks,
including their connection/child cleanup, before the baseline closes. The first
observed exception propagates to the caller. Bound concurrency to your workload
and host resources; this example makes no throughput or timing promise.

For a timing comparison, measure wall elapsed time around the entire sequential
loop or the entire parallel batch, including its join. Summing overlapping child
operation durations does not give the parallel batch's elapsed time. State
separately whether preparation/capture is included.

## Dump preparation

The bounded `import_dump(db, path)` helper is described in the
[dump preparation guide](importing-dump.md), including the `dump` extra, supported
MariaDB producer profile and failure cleanup. It is not a general SQL-file runner.

Since 0.6.0, the package supports stable Live endpoints across sequential browser E2E
cases. Use independent Forks for concurrent cases; Live does not promise a
parallel shared mutable endpoint. See the [Live guide](live.md) for connection
draining and reset ownership.

## Owned E2E entry

The [owned E2E examples](examples/e2e_owned/README.md) demonstrate
application-specific preparation/start/quiescence/stop hooks over Live. This
entry was approved for bounded main adoption with the supplied hook obligations;
it is available since 0.6.0. Existing direct Live APIs remain the mechanism
underneath the entry. See the [integration receipt](reviews/e2e-integration-ci-41095184074/assessment.json)
for exact tested source/profiles. Arbitrary unregistered work and non-cooperative
shutdown remain outside the guarantee; detailed resource characterization is deferred.

<a id="snapshot-ownership-and-host-lifetime"></a>
<a id="connections-timeouts-and-failures"></a>
<a id="local-openssl4-and-connectorpython"></a>
<a id="wire-scope"></a>
<a id="wire-scope-for-current-source-builds"></a>

## Reference

- [Fixture options, Fork limits and cleanup failures](python-reference.md)
- [SQL, driver exceptions and wire limits](compatibility.md)

### Process-local initialization image (v0.7.0 candidate)

The implementation is adopted on main and unreleased. See the
[initialization-image ownership reference](python-reference.md#process-local-initialization-image-unreleased)
for lifetime, sharing and failure behavior.
