# Python API

Python distribution `0.1.0a3` is a macOS 15+ arm64 wheel. Use a locally built
wheel or the published GitHub Release asset. The wheel includes the host and
native runtime. See the [README](../README.md#python)
for installation and a first query.

Use `with mariamem.start() as db:` to own a database and call
`db.connection_info()` for MySQL driver keyword arguments. Close driver
connections with their own context managers. Database `close()` is idempotent.
`closed` reports disposal or host termination; call `close()` to release wrapper
resources. `logs` retains the last 16 Ki characters after cleanup.
An explicitly supplied `log_path=` is preserved; default log directories are removed.

`wait_disconnected()` waits until the host has released all SQL sessions after
driver disconnects. Multiple clients may connect to one DB up to the guest's
session capacity (16 in the current native bundle). An extra connection gets
MySQL error 1040; disconnecting a client makes its slot available after guest
cleanup. Call `wait_disconnected()` before creating a template snapshot when
all clients have been closed.

## Snapshots

```python
import mariamem

with mariamem.start() as template:
    # Connect, run migration/seed, commit, and disconnect here.
    template.wait_disconnected()
    with template.snapshot() as saved:
        with saved.fork() as a, saved.fork() as b:
            # a and b have independent data and transactions.
            pass
```

Successful snapshot creation ends the source DB. Active query/handshake/cleanup
is rejected with `Busy`; an active transaction is rejected with
`TransactionActive` unless `rollback=True` is explicit. These precondition
rejections keep the source database available.

An automatic snapshot owns a temporary directory removed by `close()` or context
exit. An explicit `snapshot("path")` destination is retained and can be reopened
with `mariamem.Snapshot.open("path")`. Snapshot manifests verify file hashes and
guest build compatibility. Snapshots contain DB data: do not publish test data as
source or release assets.

## pytest fixtures

| Fixture | Scope | Purpose |
|---|---|---|
| `mariamem_options` | session | Start options; defaults to `{}` |
| `mariamem_server` | session | Template DB; consumed by successful snapshot creation |
| `mariamem_snapshot` | session | Empty DB snapshot by default |
| `mariamem_fork` | function | Independent DB for a test |
| `mariamem_connection_info` | function | Connection keyword arguments for that DB |
| `mariamem_class_fork` | class | Shared DB for one class |
| `mariamem_class_connection_info` | function | Connection arguments for the class DB |

To prepare migrations and seed data, override `mariamem_snapshot` in `conftest.py`:

```python
import pytest
import pymysql

@pytest.fixture(scope="session")
def mariamem_snapshot(mariamem_server):
    with pymysql.connect(**mariamem_server.connection_info()) as conn:
        with conn.cursor() as cur:
            cur.execute("CREATE TABLE seed(id INT PRIMARY KEY) ENGINE=InnoDB")
            cur.execute("INSERT INTO seed VALUES(42)")
        conn.commit()
    mariamem_server.wait_disconnected()
    with mariamem_server.snapshot() as saved:
        yield saved
```

Each xdist worker creates its own session template. Use
`pytest -n 2 --dist=loadscope` when class-scoped DBs must stay on the same worker.
Class fixtures deliberately share mutations between tests in that class.

## Developer overrides

`start(host_binary=..., runtime=..., module=...)` allows explicit native artifacts.
`MARIAMEM_NATIVE_DIR` points to a directory containing the private bundle manifest.
Neither is needed with a complete platform wheel. Timeouts can be configured with
`startup_timeout`, `query_timeout`, and `shutdown_timeout` (seconds).
Query timeout or client disconnect during a running query terminates the
database instance. `db.closed` then becomes true; `db.status()` raises
`HostError(code="unusable", closed=True)`. Call `db.close()` to release wrapper
resources, then start or fork another instance. An idle client disconnect does
not terminate the instance. Server-side prepared statements remain unsupported.
