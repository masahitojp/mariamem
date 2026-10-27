# mariamem

**Make a real MariaDB as disposable as a test double.**

mariamem gives each test its own real MariaDB, without Docker or a separately
managed database server. Use an ordinary MySQL driver, let the application
commit and roll back normally, then discard the database when the test ends.
There is no SQL imitation and no automatic transaction wrapper around tests.

Start fresh for light setup. When migrations or fixtures are expensive, prepare
them once, fix that state as a Snapshot, and Fork independent databases for
individual tests. Share the baseline, not previous tests' mutations.

Python `0.5.3` / Go `v0.5.3` reuses successful macOS platform checks to reduce
repeated startup work. It retains in-memory Snapshots and one automatically
managed Python host per root lineage.
Public save/load APIs have been removed; prepare migrations and fixtures once
per test session and reuse the live baseline. See the
[release notes](release/NOTES-v0.5.3.md) and [API migration guide](docs/changes-since-v050.md).

## Installation

Supported platforms are **macOS 15+ / Apple Silicon (arm64)** and
**Ubuntu 24.04 LTS / x86_64**. Other platforms are not supported.
Release validation uses Go 1.26.10 and Python 3.14. Package minimums are
Go 1.26.0 and Python 3.11; they are not a tested matrix of all later versions.
The Python3.11 minimum applies to current source builds; published v0.5.3
retains its original Python3.9 metadata.
External Go consumers passed on macOS arm64 with Go 1.26.8 and
1.27.0/1.27.1/1.27.2 historically; the current forward-compat check uses
Go 1.27.3. GO-2026-6809 affects Go <1.26.10 and 1.27.0–1.27.2. See
[toolchain compatibility](docs/go-compatibility.md) for the exact tested scope;
the module minimum remains Go 1.26.0.

To install the published release, create a virtual environment and install its platform wheel.
PyPI publication remains unavailable pending account recovery; GitHub Release
wheels are the supported installation path.

```sh
python3 -m venv .venv
source .venv/bin/activate

# macOS arm64
python -m pip install 'mariamem[test] @ https://github.com/masahitojp/mariamem/releases/download/v0.5.3/mariamem-0.5.3-py3-none-macosx_15_0_arm64.whl'

# Ubuntu x86_64: use this instead
python -m pip install 'mariamem[test] @ https://github.com/masahitojp/mariamem/releases/download/v0.5.3/mariamem-0.5.3-py3-none-linux_x86_64.whl'
```

The `test` extra supplies PyMySQL and pytest tools. Use the wheel rather than a
Git source install: it includes the required platform executable.

For the published Go module:

```sh
go mod init example.com/mariamem-test
go get github.com/masahitojp/mariamem@v0.5.3
go get github.com/go-sql-driver/mysql
```

Optional release audit assets can be downloaded separately; they are not needed
for ordinary startup:

```sh
gh release download v0.5.3 --repo masahitojp/mariamem \
  --pattern 'SHA256SUMS' --pattern 'mariamem-0.5.3-corresponding-source.tar.gz'
```

## Start fresh

Fresh means a new database in its initial state. For small fixtures it is
usually the simplest choice.

```python
import mariamem
import pymysql

with mariamem.start() as db:
    with pymysql.connect(**db.connection_info()) as conn:
        with conn.cursor() as cur:
            cur.execute("CREATE TABLE items(id INT PRIMARY KEY) ENGINE=InnoDB")
            cur.execute("INSERT INTO items VALUES(1)")
        conn.commit()
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM items")
            assert cur.fetchone() == (1,)
```

The same disposable database in Go:

```go
package example

import (
    "context"
    "database/sql"
    "testing"

    _ "github.com/go-sql-driver/mysql"
    "github.com/masahitojp/mariamem"
)

func TestItems(t *testing.T) {
    ctx := context.Background()
    db, err := mariamem.Start(ctx, mariamem.Options{})
    if err != nil { t.Fatal(err) }
    defer func() { if err := db.Close(); err != nil { t.Error(err) } }()
    pool, err := sql.Open("mysql", db.DSN())
    if err != nil { t.Fatal(err) }
    defer pool.Close()
    if _, err = pool.ExecContext(ctx, "CREATE TABLE items(id INT PRIMARY KEY) ENGINE=InnoDB"); err != nil { t.Fatal(err) }
    if _, err = pool.ExecContext(ctx, "INSERT INTO items VALUES(1)"); err != nil { t.Fatal(err) }
    var id int
    if err = pool.QueryRowContext(ctx, "SELECT id FROM items").Scan(&id); err != nil { t.Fatal(err) }
    if id != 1 { t.Fatalf("id = %d", id) }
}
```

The application may use its own connections and commit normally. Close those
connections before disposing of the database.

## Prepare once, isolate each test

Run migrations and SQL fixtures through your normal driver, then create a
Snapshot. Successful Snapshot creation ends the source database.

```python
with mariamem.start() as setup_db:
    with pymysql.connect(**setup_db.connection_info()) as conn:
        with conn.cursor() as cur:
            cur.execute("CREATE TABLE items(id INT PRIMARY KEY) ENGINE=InnoDB")
            cur.execute("INSERT INTO items VALUES(1)")
        conn.commit()
    setup_db.wait_disconnected()

    with setup_db.snapshot() as baseline:
        with baseline.fork() as first:
            # Starts with items(1). This test may insert, delete or change schema.
            pass
        with baseline.fork() as second:
            # Still starts with items(1), regardless of first's changes.
            pass
```

A Snapshot is a fixed schema/data baseline, not a running database or SQL dump.
Each Fork starts a new mutable database. Closing a child leaves the baseline
available for later children. A modified child can create a new Snapshot; it
never updates the original baseline.

Both languages provide preparation and independent child acquisition. See the
[Go guide](docs/go.md#prepare-once-fork-independent-databases) and
[Python guide](docs/python.md#share-preparation-isolate-mutations). Python pytest
fixture integration is described in the Python guide.

Unreleased source builds also offer opt-in [application connection routing](docs/connection-routing.md):
keep ordinary Python connection calls while `@pytest.mark.shadow_maria` selects an independent
child. Configure before application imports and explicitly enroll existing pools.
This feature is not included in published v0.5.3.

## Reuse expensive preparation within a test session

Baselines are process-local and retain fixed, private immutable blocks in memory.
Heap-backed capture enforces ownership and immutability without rereading every
byte. Content checks remain at internal import/transfer boundaries and when
copying borrowed file mappings into owned memory.
Each Fork has private changes and an independent MariaDB runtime. Prepare once
per test session. Saving/loading baseline artifacts is no longer supported;
retain migrations and seed inputs to recreate preparation in another process.
See the [Python](docs/python.md#snapshot-ownership-and-host-lifetime) and
[Go](docs/go.md#in-memory-baseline-lifetime) guides for ownership and cleanup.


Unreleased main (not included in published v0.5.3): stored procedures
and functions are supported through ordinary SQL, including
CALL result chains and Snapshot/Fork retention. Packages/package bodies are
outside product support and compatibility testing; events remain unavailable
in the embedded build (1235). DEFINER clauses and SQL SECURITY metadata are
accepted and retained, but `--skip-grant-tables` means account existence and
privileges are not enforced. See the [approved scope](docs/decisions/routine-support-scope.md).
Current source builds add real server-side execution for Go explicit/implicit
Prepare and Python prepared cursors. This is not in published v0.5.3.
`DELIMITER` is a client directive; this does not add a general dump importer.

Oracle mysql-connector-python26.7.0 has two accepted, native-matched limits:
prepared CALL result traversal can fail and leave that connection unusable;
Mac C/default can shorten a NUL-containing untyped character projection.
Typed binary columns preserve these bytes. The two cases pass with MariaDB
Connector/Python1.1.14 on both supported guest platforms; this is not blanket
driver compatibility. See the [exact consumer boundaries](docs/decisions/prepared-consumer-exceptions.md).
Server-side cursors / COM_STMT_FETCH remain unsupported.


## Important limits

- Close driver connections and DB/baseline handles normally. Context managers
  and Go cleanup functions make those boundaries explicit.
- Close clients before Snapshot creation; active operations and unresolved
  transactions are rejected unless rollback is explicitly requested.
  Busy/transaction precondition rejection leaves the source available;
  successful capture ends it.
- Multiple connections and normal commit/rollback are supported. Current
  session capacity is 16; excess connections get recoverable MySQL error 1040.
  This is not a permanent capacity or parallel-throughput guarantee.
- Prepared support is available in current source builds; published v0.5.3 does not include it.
- Interrupted active SQL invalidates that database. Close it and start or fork
  another. Forced reclamation of hung execution is not guaranteed.
- This is a test database, not a production service or security boundary.
  DBs and baselines contain your test data; treat sensitive data accordingly.
- Resource use and the Fresh/prepared crossover depend on the workload.
  Large scans remain query work even when preparation is reused.
- The 0.x API may change. See [release changes](release/NOTES-v0.5.3.md)
  and [API migration](docs/changes-since-v050.md).

You do not need runtime implementation knowledge to use these APIs.
[Architecture](docs/v04-generated-go-architecture.md) explains the current
implementation and technical limitations;
[project status](docs/project-status.md) records current state and roadmap;
[historical measurements](benchmarks/v043-characterization.md) preserve evidence.

Project code is [GPL-2.0-only](LICENSE); components retain their own licenses in
[NOTICE](NOTICE) and [THIRD_PARTY_LICENSES](THIRD_PARTY_LICENSES). The guest derives
from [shyim/lite4mariadb](https://github.com/shyim/lite4mariadb) and MariaDB Server.
The original testing API was informed by [shibukawa/pgmem](https://github.com/shibukawa/pgmem);
mariamem's product contract is defined independently.

Unreleased main supports stable Live endpoints across sequential browser E2E
cases. See the [Live guide](docs/live.md) for connection draining and reset ownership.
