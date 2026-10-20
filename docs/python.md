# Python usage

This guide describes Python `0.5.3`: in-memory Snapshots and one automatically
managed host per root lineage. Public save/load APIs are removed. See
[API changes and migration](changes-since-v050.md) and
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
Snapshot content stays in memory; no user-managed filesystem artifact is needed.

`baseline.fork(**options)` inherits the preparation DB's options with supplied
overrides. `mariamem.start(snapshot=baseline, ...)` also creates a child from the
owned baseline, using the supplied start options. These are alternative
creation routes, not successive steps.

## Snapshot ownership and host lifetime

`snapshot()` fixes a baseline with private immutable blocks in Go memory.
Ownership and immutability are enforced without rescanning every byte during
ordinary heap capture. Internal imports, transfers and copies from borrowed
file mappings retain their content checks.
It ends the source DB and retains the baseline in the automatically managed host.
Fork creates a
fresh MariaDB runtime and private changes; it does not copy running threads.
One independent `start()` owns one host lineage. Its baseline, children and
derived baselines share that host. Each DB has its own SQL endpoint and a limit
of 16 simultaneous connections. The Snapshot itself uses no SQL connection.
The host exits when the last owned handle and admitted operation finish.

SQL errors and an individual DB's normal Close do not close siblings. A host
process crash invalidates that lineage's DBs and baselines; prepare again.
Independent `start()` calls use independent hosts. Non-cooperative guest cleanup
can retain resources until the lineage ends; an individual request timeout does
not authorize killing a host with other live owners.

Snapshots are process-local. Saving/loading baselines, path-based acquisition,
path-taking capture such as `db.snapshot(path)`, `snapshot_to`, `load_snapshot`
and `Snapshot.open(path)` are unavailable in this version.
Re-run migrations/seed to prepare a baseline in each test session.
Old persisted artifacts are not inputs to this API. The library does not manage
an automatic cache. Internal handoff for an explicitly different development
host binary is temporary and is not a public save operation.

Creation checks inventory, layout, seal state and guest/source identity while
retaining the same backing. Ordinary heap acquisition does not perform a full
content reread. Fork reuses the fixed blocks and copies changes privately;
it does not fully hash content on every Fork. Internal import/transfer boundaries
and borrowed-mapping copies retain their content validation.

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
it does not share one mutable database. Use the function-scoped fixtures for per-test mutable state.

Each pytest-xdist worker has its own session fixtures and therefore prepares
its own baseline. There is no automatic run-wide baseline, cross-worker cache
or cross-run reuse policy. Prepare each worker's baseline from migrations/seed
with `snapshot()`; a saved Snapshot artifact is not an input in this version.

## Connections, timeouts and failures

Current session capacity is 16; this is not a permanent API limit or throughput
guarantee. Connections have separate transactions, temporary tables and session
variables. Extra connections receive recoverable MySQL error 1040. Disconnect
cleanup must finish before a slot is reusable.

`startup_timeout`, `query_timeout` and `shutdown_timeout` use positive finite
seconds and default to 120, 30 and 30. Snapshot `timeout` defaults to 120 seconds;
shutdown has a deadline, but freeze/content validation has no size-independent
interruptible deadline. `wait_disconnected(timeout=...)` bounds session waiting.

Ordinary SQL errors do not invalidate the DB. Query timeout or disconnect during
active SQL does: `closed` becomes true and `status()` raises
`HostError(code="unusable", closed=True)`. Close it and start/fork another.
Idle disconnect does not invalidate it. Forced cleanup of non-cooperative
execution is not guaranteed. Server-side prepared statements are unsupported.
Stored packages/package bodies are outside product support, with no compatibility
tests or guarantees; scheduled events are unsupported. See the
[routine scope decision](decisions/routine-support-scope.md).

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
