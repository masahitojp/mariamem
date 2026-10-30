# Python usage

This guide describes Python `0.5.3` baseline APIs and explicitly labelled,
adopted additions on unreleased main. In-memory Snapshots use one automatically
managed host per root lineage. Public save/load APIs are removed. See
[API changes and migration](changes-since-v050.md) and
[installation](../README.md#installation).

Current unreleased source requires Python3.11 or newer; Python3.9/3.10 are no
longer supported. Published v0.5.3 retains its original package metadata.

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

## pytest fixtures

Install the `pytest` extra and PyMySQL for these examples; pytest-xdist is a
separate optional test-runner plugin. The package registers its fixtures through
the pytest plugin entry point.

| Fixture | Scope | Responsibility |
|---|---|---|
| `mariamem_options` | session | Start options; default `{}` |
| `mariamem_server` | session | Preparation DB; consumed by successful Snapshot |
| `mariamem_snapshot` | session | Fixed baseline; initial state by default |
| `mariamem_fork` | function | Independent mutable DB for one test |
| `mariamem_connection_info` | function | Driver arguments for that test's DB |

Use these fixtures as the primary test path. Override `mariamem_snapshot` in
`conftest.py` to run migrations/seed once per session. The preparation connection
closes before capture; successful capture consumes `mariamem_server`:

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
processes with the separately installed pytest-xdist plugin:

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

Unreleased source builds add `@pytest.mark.shadow_maria` for existing application
connections, `mariamem_prepare` for session preparation and optional
`mariamem_app_db`, `mariamem_router`, `mariamem_sqlalchemy_engines` fixtures.
Declare the original endpoint/schema before application imports, prepare that
schema using explicit preparation DB settings, and explicitly register quiescent pools. See the
[routing guide](connection-routing.md) for configuration, first/second-test
examples, ownership, supported entries and actionable failures. These fixtures
are not included in published v0.5.3; existing fixtures above retain their defaults.

## Prepared command entry

Adopted unreleased main supports the public class
`mariamem.PrepareCommand(argv, *, timeout=120, cwd=None, env=None)` as a third
`mariamem_prepare` input. None and callback behavior are unchanged, including
ignored callback return values. Unknown values are rejected with
`pytest.UsageError`; they are never silently ignored.

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

connection = json.loads(os.environ["MARIAMEM_PREPARE_CONNECTION_INFO"])
# connection contains host, port, user, password, database.
# Pass it to your existing migration/seed function, and retire its connections.
migrate_and_seed(connection)
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

## Prepared-entry cleanup failures

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
[unreleased change notes](release-notes/unreleased.md).

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

    with setup_db.snapshot() as baseline:
        with baseline.fork() as db:
            with pymysql.connect(**db.connection_info()) as conn:
                with conn.cursor() as cur:
                    cur.execute("INSERT INTO users VALUES(2)")
                conn.commit()
        with baseline.fork() as db:
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
process. Each task acquires its own child and SQL connection. This is separate
from pytest-xdist, whose workers prepare independent baselines.

```python
from concurrent.futures import ThreadPoolExecutor

import mariamem
import pymysql


def check_child(baseline, user_id):
    with baseline.fork() as db:
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
    with setup_db.snapshot() as baseline:
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

## Connections, timeouts and failures

Current session capacity is 16; this is not a permanent API limit or throughput
guarantee. Connections have separate transactions, temporary tables and session
variables. Extra connections receive recoverable MySQL error 1040. Disconnect
cleanup must finish before a slot is reusable.

`startup_timeout`, `query_timeout` and `shutdown_timeout` use positive finite
seconds and default to 120, 30 and 30. Snapshot `timeout` defaults to 120 seconds;
shutdown has a deadline, but freeze/content validation has no size-independent
interruptible deadline. `wait_disconnected(timeout=...)` bounds session waiting.

Unreleased main (not included in published v0.5.3): stored procedures
and functions are supported through ordinary SQL, including
CALL result chains and Snapshot/Fork retention. Packages/package bodies are
outside product support and compatibility testing; events remain unavailable
in the embedded build (1235). DEFINER clauses and SQL SECURITY metadata are
accepted and retained, but `--skip-grant-tables` means account existence and
privileges are not enforced. See the [approved scope](decisions/routine-support-scope.md).
Current source builds add real server-side execution for Go explicit/implicit
Prepare and Python prepared cursors. This is not in published v0.5.3.
`DELIMITER` is a client directive, not server SQL. Python source builds provide
an explicit [bounded dump reader](importing-dump.md); this is not a general
SQL-script importer or a Go dump API.

Oracle mysql-connector-python 26.7.0 has three named, accepted exceptions:

- In the native-matched macOS C-extension prepared syntax-error case, the
  client reports `2006/HY000` although raw wire returns `1064/42000` and subsequent
  SQL succeeds. This does not make other `2006` errors safe or recoverable.
- For the tested prepared CALL emitting two result sets via nextset, advancing
  after the first set can fail and leave that connection unusable. This affects
  pure mode on both supported guest platforms and macOS C/default in the fixed
  native-matched observations; it is not a claim about every CALL or driver.
- macOS C/default can shorten an untyped prepared character projection of
  A-NUL-B to A without a useful error. Typed binary columns preserve all bytes;
  pure mode preserves that projection. This is not evidence of file corruption.

See the [CALL/NUL boundaries](decisions/prepared-consumer-exceptions.md)
and [syntax-error presentation](reviews/v06x-prepared-product-design.md#c-extension-syntax-error).
MariaDB Connector/Python 1.1.14 passes the two CALL/NUL cases on both supported
guest platforms; this is not blanket driver compatibility or a repair to Oracle
Connector/Python. Ubuntu's additional explicit C-extension mode may be unavailable
and is an allowed SKIP, not C-mode compatibility PASS; required default/pure modes
have their own executed evidence. No driver mode is silently substituted.
Server-side cursors / COM_STMT_FETCH remain unsupported.

### Wire scope for current source builds

Use the supplied local root/empty-password endpoint profile. TLS/SSL, compression,
DEPRECATE_EOF and alternate authentication are not advertised/supported in this
profile. COM_RESET_CONNECTION, server-side cursors/COM_STMT_FETCH, LOCAL INFILE
transfer, CHANGE_USER, STATISTICS, PROCESS_INFO and binlog/replication streaming
are outside0.6.0 support. Multi-packet continuation is also outside this profile.
SQL-file import is not LOCAL INFILE; metadata SQL is not an administrative wire
command. Per-entry uncaptured paths remain unverified;
passing application/Release tests is not evidence of additional protocol coverage.
See the [bounded wire contract and reopening rule](decisions/v060-wire-contract.md).



Ordinary SQL errors do not invalidate the DB. Query timeout or disconnect during
active SQL does: `closed` becomes true and `status()` raises
`HostError(code="unusable", closed=True)`. Close it and start/fork another.
Idle disconnect does not invalidate it. In current source builds, a fatal guest
worker trap also invalidates the DB promptly and reports its cause without waiting
for the query timeout. Forced cleanup of non-cooperative execution is not guaranteed. Prepared boundaries for current source builds are described above.

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

## Dump preparation

The unreleased bounded `import_dump(db, path)` helper is described in the
[dump preparation guide](importing-dump.md), including the `dump` extra, supported
MariaDB producer profile and failure cleanup. It is not a general SQL-file runner.

Unreleased main supports stable Live endpoints across sequential browser E2E
cases. Use independent Forks for concurrent cases; Live does not promise a
parallel shared mutable endpoint. See the [Live guide](live.md) for connection
draining and reset ownership.

## Local OpenSSL4 and Connector/Python

Homebrew Python3.14 with OpenSSL4 can fail to import Oracle
mysql-connector-python 26.7.0 because `ssl.PROTOCOL_TLSv1` is absent. The observed
combination is Python3.14.9/OpenSSL4.0.3. CPython conditionally omits protocol
constants for methods unavailable in OpenSSL4; this connector accesses those
constants during import. This happens before connecting to mariamem. It is
separate from the native-matched prepared-result limitations above.

Record the Python/OpenSSL versions and original import error when reporting a
local integration failure. Use the CI-supported Python/OpenSSL profile for the
fixed consumer checks; retain FAIL for the affected local run. Do not add ssl
aliases, patch the connector or change drivers to label that run PASS. The
current OpenSSL3 CI environment does not cover this OpenSSL4 combination. See
[local verification](development.md#local-verification).

## Owned E2E entry — unreleased main

The source-build [owned E2E examples](examples/e2e_owned/README.md) demonstrate
application-specific preparation/start/quiescence/stop hooks over Live. This
entry was approved for bounded main adoption with the supplied hook obligations;
it is not part of published v0.5.3. Existing direct Live APIs remain the mechanism
underneath the entry. See the [integration receipt](reviews/e2e-integration-ci-41095184074/assessment.json)
for exact tested source/profiles. Arbitrary unregistered work and non-cooperative
shutdown remain outside the guarantee; detailed resource characterization is deferred.
