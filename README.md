# mariamem

**Make a real MariaDB as disposable as a test double.**

mariamem gives each test its own real MariaDB, without Docker or a separately
managed database server. Use an ordinary MySQL driver, let the application
commit and roll back normally, then discard the database when the test ends.
There is no SQL imitation and no automatic transaction wrapper around tests.

Start fresh for light setup. When migrations or fixtures are expensive, prepare
them once, fix that state as a Snapshot, and Fork independent databases for
individual tests. Share the baseline, not previous tests' mutations.

The Python package version is `0.4.6`; the Go module uses the `v0.4.6` tag.
See the [release](https://github.com/masahitojp/mariamem/releases/tag/v0.4.6)
and [release notes](release/NOTES-v0.4.6.md).

## Installation

Supported platforms are **macOS 15+ / Apple Silicon (arm64)** and
**Ubuntu 24.04 LTS / x86_64**. Other platforms are not supported.
Release validation uses Go 1.26.8 and Python 3.14. Package minimums are
Go 1.26.0 and Python 3.9; they are not a tested matrix of all later versions.
External Go consumers passed on macOS arm64 with Go 1.26.8 and
1.27.0/1.27.1/1.27.2. See [toolchain compatibility](docs/go-compatibility.md)
for the exact tested scope; the module minimum remains Go 1.26.0.

For the currently published Python release, create a virtual environment and
install the platform wheel. PyPI publication remains unavailable pending
account recovery; GitHub Release wheels are the supported installation path.

```sh
python3 -m venv .venv
source .venv/bin/activate

# macOS arm64
python -m pip install 'mariamem[test] @ https://github.com/masahitojp/mariamem/releases/download/v0.4.6/mariamem-0.4.6-py3-none-macosx_15_0_arm64.whl'

# Ubuntu x86_64: use this instead
python -m pip install 'mariamem[test] @ https://github.com/masahitojp/mariamem/releases/download/v0.4.6/mariamem-0.4.6-py3-none-linux_x86_64.whl'
```

The `test` extra supplies PyMySQL and pytest tools. Use the wheel rather than a
Git source install: it includes the required platform executable.

For the published Go module:

```sh
go mod init example.com/mariamem-test
go get github.com/masahitojp/mariamem@v0.4.6
go get github.com/go-sql-driver/mysql
```

Optional release audit assets can be downloaded separately; they are not needed
for ordinary startup:

```sh
gh release download v0.4.6 --repo masahitojp/mariamem \
  --pattern 'SHA256SUMS' --pattern 'mariamem-0.4.6-corresponding-source.tar.gz'
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

## Reuse expensive preparation across runs

Persistence is optional. Go uses `SnapshotOptions.Destination` to persist and
`LoadSnapshot(ctx, path, opts)` to load; see the [Go guide](docs/go.md#persist-expensive-preparation).
For Python, normally use `db.snapshot()` and let its context own the baseline.
`db.snapshot_to(path)` additionally saves the fixed baseline at that path:

```python
with mariamem.start() as setup_db:
    # Your migration/import/fixture code; commit and close all SQL connections.
    setup_db.wait_disconnected()
    with setup_db.snapshot_to("./prepared") as baseline:
        with baseline.fork() as db:
            pass

# A later run: acquire the baseline without starting a database.
with mariamem.load_snapshot("./prepared") as baseline:
    with baseline.fork() as db:
        pass
```

The destination must not already exist. Saved baselines are advanced reusable
artifacts tied to the compatible MariaDB build. Keep their migration, fixture
and source inputs reproducible. mariamem does not decide when to invalidate,
regenerate or delete them. Closing a loaded baseline does not delete its source.

Creation/loading completely validates the baseline and takes ownership of the
state used by children. Later changes to a saved source cannot affect that
owned baseline. Fork does not reread all contents for validation each time;
damage arising in owned storage after acquisition is not guaranteed to be
detected on every Fork.

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
- Server-side prepared statements are unsupported.
- Interrupted active SQL invalidates that database. Close it and start or fork
  another. Forced reclamation of hung execution is not guaranteed.
- This is a test database, not a production service or security boundary.
  Saved baselines contain your test data; treat sensitive data accordingly.
- Resource use and the Fresh/prepared crossover depend on the workload.
  Large scans remain query work even when preparation is reused.
- The 0.x API may change. See [release notes](release/NOTES-v0.4.6.md).

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
