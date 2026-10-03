# Python API

**Generated Go is the default v0.4.0 runtime.** The `0.4.0` candidate is
prepared, not tagged or published. Normal Python startup uses a platform Go host
with generated-Go MariaDB linked in; no external Wasmer/native bundle is needed.
Public APIs and cold Snapshot/Fork semantics are preserved. See
[architecture](v04-generated-go-architecture.md) and
[canonical measurements](../benchmarks/v04-integrated-candidate.md).

PyPI publication remains unavailable pending account recovery. After publication,
use the [v0.4.0 GitHub Release wheels](https://github.com/masahitojp/mariamem/releases/tag/v0.4.0)
and [platform install commands / PEP 508 extras](../README.md#python), not a Git
source install. The wheel supplies the platform host executable. PyPI remains a
planned distribution channel.

The Ubuntu 24.04 LTS x86_64 host-only wheel is named
`mariamem-0.4.0-py3-none-linux_x86_64.whl`. This is deliberately not a manylinux
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

Function-scoped forks provide disposable server-level state, avoiding per-test
rollback/schema reset/data cleanup for isolation. Driver connections and owned
DB/snapshot handles still need context-manager or explicit cleanup. Snapshot
captures a prepared filesystem, not a live running server. Prepared-state value
depends on migration/fixture cost; Fork and fresh Start measure different
boundaries. See the [performance/resource limits](../README.md#performance-and-resource-limits)
for the fixed Go reference and substantial per-DB memory cost. Those Go timings
are not Python end-to-end or hardware-independent guarantees.

## Developer overrides

`start(host_binary=..., runtime=..., module=...)` allows explicit native artifacts.
`MARIAMEM_NATIVE_DIR` points to a directory containing the private bundle manifest.
Neither is needed with a complete platform wheel. Timeouts can be configured with
`startup_timeout`, `query_timeout`, and `shutdown_timeout` (seconds).
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

Legacy Ubuntu 24.04 x86_64 AOT bundles require a CPU with SSSE3. Compilation uses
a fixed SSE2+SSSE3 feature set and does not require AVX or AVX-512.

For startup failures, read the category/stage first, then the expected path,
platform or hash in the message. Reinstall the matching host-only Python wheel,
or, for explicit legacy execution, re-extract a complete matching native bundle;
do not mix files from different
bundles. Preserve executable permissions. An AOT/CPU compatibility error may
require a supported machine or VM exposing the required CPU features; the
Ubuntu 24.04 x86_64 bundle requires SSE2 and SSSE3. Startup failure does not
return a usable database; retry Start after correcting the reported input.
