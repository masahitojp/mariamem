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

## Adopted features in current source builds

The following supported paths are adopted on unreleased main and are intended
for the 0.6.0 scope; installing published v0.5.3 does not provide these additions.

| Test setup | Supported entry and boundary |
| --- | --- |
| Python prepared tests | [pytest preparation and PrepareCommand](docs/python.md#prepared-command-entry); a worker-local baseline and independent child per test |
| Existing Python application connections | [Opt-in shadow_maria routing](docs/connection-routing.md); pinned drivers, explicit profiles and pool enrollment |
| Go prepared tests | [mariamemtest](docs/go-prepared-fixture.md); prepare once and use a test-owned bounded child pool |
| Sequential browser / HTTP E2E | [BrowserEntry and NewHTTP](docs/examples/e2e_owned/README.md); supplied entries own sequencing, application hooks own readiness and physical SQL/job retirement |
| Python MariaDB dump input | [import_dump with the dump extra](docs/importing-dump.md); only the documented MariaDB12.3.3 producer profile |
| Ordinary Django tests | [Standard-runner recipe](docs/django-testing.md); Django owns rollback/flush/fixtures, not automatic prepared-Snapshot restoration |

These paths retain the exact driver, wire and lifecycle limits below. The extra
Django prepared entry is deferred from 0.6.0 for consideration in 0.6.1, not a
delivery promise. Procedures/functions and real server-side prepared execution
are supported on main within the named exceptions below.

## Prepare once, isolate each test

These fixture/helper examples use **current main**, not the published v0.5.3
packages installed above. For Go, select current source with
`go get github.com/masahitojp/mariamem@<version-or-commit>`, replacing the placeholder
with the main commit you are testing. For Python, build and install the
matching platform wheel using the [source-build instructions](docs/development.md#packaging--release-dry-runs),
with pytest and PyMySQL available. Versioned releases will carry these entries
in their documented release scope; these examples do not change the published version.

## pytest fixtures

Return your migrations and seed callback from `mariamem_prepare`:

```python
# conftest.py
import pytest
import pymysql


@pytest.fixture(scope="session")
def mariamem_prepare():
    def prepare(db):
        with pymysql.connect(**db.connection_info()) as conn:
            with conn.cursor() as cur:
                cur.execute("CREATE TABLE items(id INT PRIMARY KEY) ENGINE=InnoDB")
                cur.execute("INSERT INTO items VALUES(1)")
            conn.commit()
    return prepare
```

Request the test-owned connection settings in each test:

```python
# test_items.py
import pymysql


def test_commit(mariamem_connection_info):
    with pymysql.connect(**mariamem_connection_info) as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM items")
        conn.commit()


def test_seed(mariamem_connection_info):
    with pymysql.connect(**mariamem_connection_info) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM items")
            assert cur.fetchall() == ((1,),)
```

Run `python -m pytest test_items.py`. Preparation runs once per pytest worker;
each test receives an independent child. Either test order starts with the seed,
including after another test commits or fails. Close preparation connections
before the callback returns; the plugin owns disconnect waiting, Snapshot/Fork
and teardown. See the [Python guide](docs/python.md#pytest-fixtures) for
`PrepareCommand` and pytest-xdist. For existing application connections, use the
opt-in [shadow_maria routing](docs/connection-routing.md) profile.

## Go test helper

Save this as `items_test.go` in your Go module:

```go
package example_test

import (
	"context"
	"database/sql"
	"os"
	"testing"

	"github.com/masahitojp/mariamem/mariamemtest"
)

var fixture *mariamemtest.Fixture

func TestMain(m *testing.M) {
	os.Exit(mariamemtest.Run(m, mariamemtest.Options{
		Prepare: func(ctx context.Context, db *sql.DB, dsn string) error {
			// Migration commands can use ctx and dsn. Return their original
			// error, retain stderr and never log a DSN containing credentials.
			if _, err := db.ExecContext(ctx,
				"CREATE TABLE items (id INT PRIMARY KEY, label VARCHAR(32)) ENGINE=InnoDB"); err != nil {
				return err
			}
			_, err := db.ExecContext(ctx, "INSERT INTO items VALUES (1, 'seed')")
			return err
		},
		MaxForks: 2,
	}, func(f *mariamemtest.Fixture) { fixture = f }))
}

func TestCommit(t *testing.T) {
	db := fixture.DB(t)
	if _, err := db.ExecContext(t.Context(), "DELETE FROM items"); err != nil {
		t.Fatal(err)
	}
}

func TestSeed(t *testing.T) {
	db := fixture.DB(t)
	var label string
	if err := db.QueryRowContext(t.Context(),
		"SELECT label FROM items WHERE id=1").Scan(&label); err != nil {
		t.Fatal(err)
	}
	if label != "seed" {
		t.Fatalf("starting label: %q", label)
	}
}
```

Run `go test ./...`. `Run` prepares once per package test process and closes the
fixture after the suite; `DB(t)` acquires one independent child/pool per test and
registers pool-before-child cleanup. Tests use ordinary SQL and commits without
an automatic rollback wrapper. The helper provides its driver-owned pool; no
`sql.Open`, blank driver import or manual Snapshot/Fork is needed here.
See the [Go guide](docs/go.md#prepare-once-fork-independent-databases) for bounded
parallel subtests and the [helper guide](docs/go-prepared-fixture.md) for lifecycle
and failure behavior.

## Start fresh

Use `start()` when you want a new database without a prepared baseline, or need
to own its lifetime outside pytest. This API is also available in published v0.5.3:

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

Close SQL connections before disposing of the database. The corresponding Go
low-level API is `mariamem.Start`; ordinary Go tests can use the helper above
with `Prepare: nil` to share an empty baseline. See the
[Python](docs/python.md#share-preparation-isolate-mutations) and
[Go](docs/go.md#low-level-database-lifetimes) guides for custom ownership.
For ordinary `manage.py test` or pytest-django, see the
[Django standard-runner recipe](docs/django-testing.md).

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
`DELIMITER` is a client directive, not server SQL. Python source builds provide
an explicit [bounded dump reader](docs/importing-dump.md); this is not a general
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

See the [CALL/NUL boundaries](docs/decisions/prepared-consumer-exceptions.md)
and [syntax-error presentation](docs/reviews/v06x-prepared-product-design.md#c-extension-syntax-error).
MariaDB Connector/Python 1.1.14 passes the two CALL/NUL cases on both supported
guest platforms; this is not blanket driver compatibility or a repair to Oracle
Connector/Python. Ubuntu's additional explicit C-extension mode may be unavailable
and is an allowed SKIP, not C-mode compatibility PASS; required default/pure modes
have their own executed evidence. No driver mode is silently substituted.
Server-side cursors / COM_STMT_FETCH remain unsupported.

Current source builds retain a bounded local endpoint profile: TLS/compression,
LOCAL INFILE transfer, administrative wire commands and binlog/replication
streaming are outside0.6.0 support. See the [exact wire scope, exceptions and
bounded reopening rule](docs/decisions/v060-wire-contract.md). Application or
Release CI success does not imply additional protocol coverage.


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
