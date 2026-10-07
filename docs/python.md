# Python API

Use a real MariaDB for a test, commit normally, then close the database.
For expensive setup, create a Snapshot once and Fork independent databases.
Successful Snapshot creation ends the setup DB; each child starts with the
captured schema/data and owns its subsequent mutations.

This guide describes the released v0.4.3 API. The
[accepted product/integrity decisions](decisions/README.md) describe the next
contract direction; public API migrations remain under review.

PyPI publication remains unavailable pending account recovery;
use the released [v0.4.3 GitHub Release wheels](https://github.com/masahitojp/mariamem/releases/tag/v0.4.3)
and [platform install commands / PEP 508 extras](../README.md#python), not a Git
source install. The wheel supplies the platform host executable. PyPI remains a
planned distribution channel.

The Ubuntu 24.04 LTS x86_64 host-only wheel is named
`mariamem-0.4.3-py3-none-linux_x86_64.whl`. This is deliberately not a manylinux
compatibility claim; other Linux distributions are outside the supported scope.

Canonical clean release validation uses Python 3.14 on macOS 15 arm64 and
Ubuntu 24.04 x86_64. Metadata allows Python >=3.9; this is not a
broad tested-version matrix. macOS 15+ arm64 is supported; macOS Intel, Linux
arm64 and Windows are not supported. The 0.x public API may change.

Use `with mariamem.start() as db:` to own a database and call
`db.connection_info()` for MySQL driver keyword arguments. Close driver
connections with their own context managers. Database `close()` is idempotent.
`closed` reports disposal or host termination; call `close()` to release wrapper
resources. `logs` retains the last 16 Ki characters after cleanup.
An explicitly supplied `log_path=` is preserved; default log directories are removed.

`wait_disconnected()` waits until the host has released all SQL sessions after
driver disconnects. Multiple clients may connect to one DB up to the guest's
session capacity (16 in the current guest, not a permanent API guarantee).
Session variables, temporary tables and transactions are independent. Concurrent
queries do not establish a throughput-scaling guarantee. An extra connection gets
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
with `mariamem.Snapshot.open("path")`. In v0.4.3, open verifies the inventory
and file hashes;
actual guest-build compatibility is checked by the host when Fork starts.
The open handle still references the external directory, so external changes
can affect later Forks or cause their validation to fail.
Neither Fork writes nor child Close update the saved path. To capture changed
child state, take a new Snapshot from that child into a new destination.
Snapshots contain DB data: do not publish test data as
source or release assets.

## pytest fixtures

| Fixture | Scope (per worker) | Shared object and cleanup |
|---|---|---|
| `mariamem_options` | session | Start options; defaults to `{}` |
| `mariamem_server` | session | Mutable setup DB; consumed by successful Snapshot creation |
| `mariamem_snapshot` | session | Fixed initial state; empty by default; closed at session end |
| `mariamem_fork` | function | Independent mutable DB; discarded at test end |
| `mariamem_connection_info` | function | Connection keyword arguments for that DB |
| `mariamem_class_fork` | class | One mutable DB shared across methods; discarded at class end |
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
Class fixtures carry mutations between tests in that class; there is no
per-method rollback, truncate or reset. This differs from sharing a baseline
while creating a new DB for each method. Use function-scoped Forks for that
independent-test workflow. Direct use of the session setup DB likewise shares
mutable state until successful Snapshot creation consumes it.

Function-scoped forks provide disposable server-level state, avoiding per-test
rollback/schema reset/data cleanup for isolation. Driver connections and owned
DB/snapshot handles still need context-manager or explicit cleanup. Snapshot
captures fixed schema/data; child writes do not change that initial state.
Each successful child can continue after the Snapshot handle is closed.
Prepared-state value
depends on migration/fixture cost; Fork and fresh Start measure different
boundaries. See the [performance/resource limits](../README.md#performance-and-resource-limits)
for source-specific observations and resource limits. Those Go timings
are not Python end-to-end or hardware-independent guarantees.

## Developer overrides

`start(host_binary=...)` supports a local generated-Go host. A complete wheel
needs no override. Legacy `runtime`, `module`, `wasmer_dir` and
`MARIAMEM_NATIVE_DIR` are rejected in released v0.4.3. Use an older
tag for historical Wasmer comparisons. Timeouts use seconds:
`startup_timeout`, `query_timeout`, and `shutdown_timeout`.
Query timeout or client disconnect during a running query invalidates the
database instance. Forced reclamation of non-cooperative guest execution and
hard failure containment are not guaranteed. `db.closed` then becomes true;
`db.status()` raises
`HostError(code="unusable", closed=True)`. Call `db.close()` to release wrapper
resources, then start or fork another instance. An idle client disconnect does
not terminate the instance. Server-side prepared statements remain unsupported.

## Failure diagnostics

`HostError.code` identifies lifecycle/startup failures: `unsupported_platform`,
`native_unavailable`, `artifact_mismatch`, `host_start`, `guest_start`,
`guest_connection`, or `unusable`. `stage` identifies the failed startup boundary
when known; messages explain the concrete input or process failure. Underlying
Python causes are retained through `__cause__`. Startup errors may include a
short stderr tail; `db.logs` retains the longer bounded log after cleanup.

Ordinary SQL errors and capacity exhaustion remain MySQL driver errors (capacity
is error 1040), rather than wrapper startup failures. Interrupted active SQL
still invalidates the entire instance; `status()` reports `unusable` and disposes
wrapper resources. `close()` stays safe and idempotent.

For startup failures, read the category/stage, then check the reported platform
or hash. Reinstall the matching host-only Python wheel and preserve executable
permissions. Do not combine wheel files from different releases. Startup failure
does not return a usable database; retry after correcting the input.
