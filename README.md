# mariamem

**A real MariaDB for each test, without Docker.**

Connect with an ordinary MySQL driver, commit normally, and discard the database
when the test ends. For expensive migrations or fixtures, prepare once and give
each test an independent database from that initial state.

Current release: Python `0.6.2` / Go `v0.6.2` ([release notes](release/NOTES-v0.6.2.md)).

## Installation

Python **0.6.2** is available on PyPI for the following hosts (Python **3.11+**):

| Host | CPU | Minimum condition |
| --- | --- | --- |
| macOS | arm64 | macOS 15+ |
| Linux | x86_64 / aarch64 | glibc 2.28+ or musl 1.2+ |
| Windows | x86_64 / arm64 | Windows build 22000+ |

Public installation, wheel/hash checks, SELECT 1 and successful host exit passed
in seven representative environments: macOS, both Linux CPUs on both libc
families, and both Windows CPUs. These runs do not test every OS/Python version
above the minimum. Linux containers share the runner kernel, so no old-kernel
execution is claimed.

Go **v0.6.2** remains supported on **macOS 15+ arm64** and
**Ubuntu 24.04 x86_64**, with Go **1.26.0+**. The added Python wheels do not
expand the original Go tag's platform support. See [publication details](docs/releasing.md#additional-linuxwindows-wheels-for-published-062).

### Python

```sh
python3 -m venv .venv
source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\Activate.ps1
python -m pip install 'mariamem[test]==0.6.2'
```

For library use without pytest tools, use `python -m pip install mariamem==0.6.2`.

Save this as `test_database.py`:

```python
import pymysql


def test_query(mariamem_connection_info):
    with pymysql.connect(**mariamem_connection_info) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            assert cur.fetchone() == (1,)
```

Run `python -m pytest test_database.py`. The fixture owns an independent database
for the test; the `with` block closes its SQL connection before fixture cleanup.
Next: [prepare migrations and seed once](docs/python.md#pytest-fixtures).

### Go

In a new directory:

```sh
go mod init example.com/mariamem-test
go get github.com/masahitojp/mariamem@v0.6.2
go get github.com/go-sql-driver/mysql
```

Save this as `database_test.go`:

```go
package example_test

import (
	"database/sql"
	"testing"

	_ "github.com/go-sql-driver/mysql"
	"github.com/masahitojp/mariamem"
)

func TestQuery(t *testing.T) {
	db, err := mariamem.Start(t.Context(), mariamem.Options{})
	if err != nil {
		t.Fatal(err)
	}
	defer func() {
		if err := db.Close(); err != nil {
			t.Error(err)
		}
	}()

	pool, err := sql.Open("mysql", db.DSN())
	if err != nil {
		t.Fatal(err)
	}
	defer pool.Close()

	var value int
	if err := pool.QueryRowContext(t.Context(), "SELECT 1").Scan(&value); err != nil {
		t.Fatal(err)
	}
	if value != 1 {
		t.Fatalf("got %d, want 1", value)
	}
}
```

Run `go test ./...`. Deferred cleanup closes the SQL pool before the database.
Next: [prepare migrations and seed once](docs/go.md#prepare-once-fork-independent-databases).

## Choose your next step

| What you need | Guide |
| --- | --- |
| Python preparation and parallel tests | [Python](docs/python.md) |
| Go preparation and parallel tests | [Go](docs/go.md) |
| Existing Python application connections | [Opt-in routing](docs/connection-routing.md) |
| Django | [Ordinary runner](docs/django-testing.md) · [Prepared classes and xdist](docs/django-prepared.md) |
| Browser / HTTP E2E | [Owned entries](docs/examples/e2e_owned/README.md) |
| Prepare from a MariaDB dump | [Dump reader](docs/importing-dump.md) |
| Node ORMs | [Connection settings](docs/node-orm.md) |

## Before using it

Use mariamem for disposable test data. It runs MariaDB 12.3.3 with a bounded
MySQL protocol profile; it does not authenticate credentials or reproduce every
MySQL feature. Read [SQL and driver compatibility](docs/compatibility.md) when
choosing a client. Interrupted active SQL invalidates the database; close it and
start another. Forced reclamation of hung execution is not guaranteed.

Prepared baselines are process-local. Fork capacity is finite; release children
before acquiring more and choose worker counts for your memory budget. See
[Python limits](docs/python-reference.md) or [Go limits](docs/go-reference.md),
including failure paths that require a fresh lineage.

[All documentation](docs/README.md) · [Architecture](docs/v04-generated-go-architecture.md) ·
[Project status](docs/project-status.md) · [Migration from older APIs](docs/changes-since-v050.md).

<details>
<summary>Release audit files</summary>

```sh
gh release download v0.6.2 --repo masahitojp/mariamem \
  --pattern 'SHA256SUMS' --pattern 'mariamem-0.6.2-corresponding-source.tar.gz'
```

Build/forward-compatibility pins and historical results are in
[Go compatibility](docs/go-compatibility.md).

</details>

Project code is [GPL-2.0-only](LICENSE); see [NOTICE](NOTICE) and
[THIRD_PARTY_LICENSES](THIRD_PARTY_LICENSES). The guest derives from
[shyim/lite4mariadb](https://github.com/shyim/lite4mariadb) and MariaDB Server;
the original testing API was informed by [shibukawa/pgmem](https://github.com/shibukawa/pgmem).
