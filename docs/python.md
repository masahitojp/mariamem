# Python usage

This guide describes Python `0.4.5`. For wheels and supported platforms, see
[installation](../README.md#installation).

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

`close()` is idempotent. `closed` reports disposal or host termination; call
`close()` to release wrapper resources after termination as well.

## Share preparation, isolate mutations

A Snapshot fixes the current schema/data as a baseline. It does not retain a
running server or read a SQL fixture file. Load SQL fixtures through your driver
before taking it.

```python
with mariamem.start() as setup_db:
    with pymysql.connect(**setup_db.connection_info()) as conn:
        with conn.cursor() as cur:
            cur.execute("CREATE TABLE users(id INT PRIMARY KEY) ENGINE=InnoDB")
            cur.execute("INSERT INTO users VALUES(1)")
        conn.commit()
    setup_db.wait_disconnected()

    with setup_db.snapshot() as baseline:
        with baseline.fork() as db:
            # Initial users: [1]. This test may commit arbitrary changes.
            pass
        with baseline.fork() as db:
            # Initial users: [1] again, independent of the previous test.
            pass
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
For an unnamed Snapshot, temporary capture files are implementation-owned and
cleaned up. No user-managed filesystem artifact is needed.

`baseline.fork(**options)` inherits the preparation DB's options with supplied
overrides. `mariamem.start(snapshot=baseline, ...)` also creates a child from the
owned baseline, using the supplied start options. These are alternative
creation routes, not successive steps.

## Save and load a baseline

For expensive setup that should be reused across runs:

```python
with mariamem.start() as setup_db:
    # Run your migrations/import/fixtures, commit and close connections.
    setup_db.wait_disconnected()
    with setup_db.snapshot_to("./prepared") as baseline:
        with baseline.fork() as db:
            pass
```

`snapshot()` fixes the state temporarily; `snapshot_to(path)` fixes it and
persists the baseline at creation time. The previous `snapshot(path)` form is
removed; migrate those calls to `snapshot_to(path)`. There is no later save or
persist operation on an existing baseline.
An explicit destination must not already exist and is retained after the handle
closes. It contains database files, not SQL statements, and is tied to the
compatible MariaDB build.

A later run acquires the saved baseline without starting a DB:

```python
with mariamem.load_snapshot("./prepared") as baseline:
    with baseline.fork() as db:
        pass
    with mariamem.start(snapshot=baseline) as another:
        pass
```

Loading validates the complete input and owns an independent baseline.
Changing or deleting the original path after successful loading cannot affect
its children. Closing the baseline releases owned resources and leaves the
original saved artifact alone.

`start(snapshot="./prepared")` remains available when only one DB is needed.
It imports and validates the path for that call, then starts a child. To create
many children, acquire one baseline and reuse its handle instead of repeatedly
importing the path. `load_snapshot(path, host_binary=...)` accepts an optional
development host override.

mariamem does not manage artifact freshness, cache invalidation, regeneration or
deletion. Keep the creating migrations/fixtures and source inputs reproducible.
The artifact is a derived input, not an undocumented replacement for fixture
source. Do not publish baselines containing sensitive test data.

Creation/import performs full validation; later Forks reuse that owned state.
Silent damage arising in owned storage is not guaranteed to be detected on
every Fork. This is a lifecycle/integrity contract, not a security boundary
against another process controlled by the same user.

## pytest fixtures

| Fixture | Scope | Responsibility |
|---|---|---|
| `mariamem_options` | session | Start options; default `{}` |
| `mariamem_server` | session | Preparation DB; consumed by successful Snapshot |
| `mariamem_snapshot` | session | Fixed baseline; initial state by default |
| `mariamem_fork` | function | Independent mutable DB for one test |
| `mariamem_connection_info` | function | Driver arguments for that test's DB |

Override `mariamem_snapshot` in `conftest.py` to prepare expensive setup once:

```python
import pytest
import pymysql

@pytest.fixture(scope="session")
def mariamem_snapshot(mariamem_server):
    with pymysql.connect(**mariamem_server.connection_info()) as conn:
        with conn.cursor() as cur:
            cur.execute("CREATE TABLE users(id INT PRIMARY KEY) ENGINE=InnoDB")
            cur.execute("INSERT INTO users VALUES(1)")
        conn.commit()
    mariamem_server.wait_disconnected()
    with mariamem_server.snapshot() as baseline:
        yield baseline
```

Every test receives an independent database:

```python
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
it does not share one mutable database. The previous
`mariamem_class_fork` and `mariamem_class_connection_info` fixtures are removed:
use the function-scoped equivalents.

Each pytest-xdist worker has its own session fixtures and therefore prepares
its own baseline. There is no automatic run-wide baseline, cross-worker cache
or cross-run reuse policy. Advanced projects may arrange saved artifacts and
override the session baseline with `load_snapshot()`; coordination, freshness
and cleanup remain the project's responsibility.

## Connections, timeouts and failures

Current session capacity is 16; this is not a permanent API limit or throughput
guarantee. Connections have separate transactions, temporary tables and session
variables. Extra connections receive recoverable MySQL error 1040. Disconnect
cleanup must finish before a slot is reusable.

`startup_timeout`, `query_timeout` and `shutdown_timeout` use positive finite
seconds and default to 120, 30 and 30. Snapshot `timeout` defaults to 120 seconds;
export has a deadline, but full copy/validation has no size-independent
interruptible deadline. `wait_disconnected(timeout=...)` bounds session waiting.

Ordinary SQL errors do not invalidate the DB. Query timeout or disconnect during
active SQL does: `closed` becomes true and `status()` raises
`HostError(code="unusable", closed=True)`. Close it and start/fork another.
Idle disconnect does not invalidate it. Forced cleanup of non-cooperative
execution is not guaranteed. Server-side prepared statements are unsupported.

`HostError.code` identifies startup/lifecycle categories; `stage` supplies
diagnostic context and `__cause__` retains a Python cause. Startup failure
returns no usable DB. `logs` retains a bounded diagnostic tail after cleanup.
Explicit `log_path=` files are preserved; default logs are cleaned up.
For a platform/artifact mismatch, reinstall the matching wheel rather than
combining files from releases. `start(host_binary=...)` is a development override.

Current internal architecture and technical limits belong in
[architecture](v04-generated-go-architecture.md); published historical
measurements are [evidence](../benchmarks/v043-characterization.md), not a
performance promise.
