# mariamem

**Make a real MariaDB as disposable as a test double.**

mariamem starts an isolated MariaDB for a test, lets an ordinary MySQL client
connect, and disposes of the database afterward. It runs a modified MariaDB
guest under Wasmer/WASIX; it does not reimplement MariaDB SQL or InnoDB.
Go hosts run in the test process; Python starts the packaged Go host process.
Both languages have public lifecycle APIs.

The testing workflow is Docker-free: each disposable database has its own server
state. Prepare migrations/fixtures once with Snapshot, then Fork independent
databases without adding rollback, schema-reset or data-cleanup logic to each
test. Close client connections and owned database/snapshot handles normally.

The Go module and GitHub Release are at `v0.2.0`; the Python
distribution version is `0.2.0`. Native support is **macOS 15+ / Apple
Silicon (arm64)** and **Ubuntu 24.04 LTS / x86_64** (SSE2 + SSSE3).
The instructions use GitHub Release or locally built artifacts and do not
depend on PyPI. Other Linux distributions are not supported.
The 0.x public API may change.

Release CI tests Go 1.26.8 and Python 3.14 on macOS 15 arm64 and Ubuntu 24.04
x86_64. Package minimums (Go 1.26.0, Python >=3.9) do not imply a tested matrix
across all later language versions. Other platforms are neither supported nor
validated by these release jobs.

## Go

Go **1.26 or newer** is required. Start in a fresh directory:

```sh
mkdir mariamem-example
cd mariamem-example
go mod init example.com/mariamem-example
go get github.com/masahitojp/mariamem@v0.2.0
```

Save the following as `main.go`:

```go
package main

import (
	"context"
	"database/sql"
	"fmt"
	"log"
	"os"

	_ "github.com/go-sql-driver/mysql"
	"github.com/masahitojp/mariamem"
)

func run(ctx context.Context) error {
	db, err := mariamem.Start(ctx, mariamem.Options{
		NativeDir: os.Getenv("MARIAMEM_NATIVE_DIR"),
	})
	if err != nil {
		return err
	}
	defer db.Close()

	sqlDB, err := sql.Open("mysql", db.DSN())
	if err != nil {
		return err
	}
	defer sqlDB.Close()

	var answer int
	if err := sqlDB.QueryRowContext(ctx, "SELECT 1").Scan(&answer); err != nil {
		return err
	}
	fmt.Println("SELECT 1 =", answer)
	return nil
}

func main() {
	if err := run(context.Background()); err != nil {
		log.Fatal(err)
	}
}
```

Resolve the MySQL driver imported by `main.go`, then download the native bundle
from the published GitHub Release and run the example:

```sh
go mod tidy
gh release download v0.2.0 --repo masahitojp/mariamem \
  --pattern 'mariamem-native-darwin-arm64.tar.gz'
tar -xzf mariamem-native-darwin-arm64.tar.gz
export MARIAMEM_NATIVE_DIR="$PWD/mariamem-native-darwin-arm64"
go run .
# SELECT 1 = 1
```

On Ubuntu 24.04 x86_64, download/extract
`mariamem-native-ubuntu24.04-x86_64.tar.gz` instead and set `MARIAMEM_NATIVE_DIR`
to `$PWD/mariamem-native-ubuntu24.04-x86_64`.

The Go module does not contain the native runtime. The example passes the
extracted directory to `Start`; `MARIAMEM_NATIVE_DIR` is read by this example,
not automatically by the Go package.

See the [Go guide](docs/go.md) for connection metadata, snapshots, forks, and
manual bundle verification.

## Python

Install the `0.2.0` platform wheel downloaded from a GitHub Release or built
locally with [the development instructions](docs/development.md). For a locally
built wheel:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install './build/dist/mariamem-0.2.0-py3-none-macosx_15_0_arm64.whl[test]'
```

On Ubuntu 24.04 x86_64, use
`mariamem-0.2.0-py3-none-linux_x86_64.whl` instead of the macOS wheel.

The wheel includes the Go host executable, Wasmer runtime, and MariaDB guest.
The `test` extra installs PyMySQL and pytest tools.

```python
import mariamem
import pymysql

with mariamem.start() as server:
    with pymysql.connect(**server.connection_info()) as conn:
        with conn.cursor() as cursor:
            cursor.execute("CREATE TABLE items(id INT PRIMARY KEY) ENGINE=InnoDB")
            cursor.execute("INSERT INTO items VALUES(1)")
            conn.commit()
            cursor.execute("SELECT id FROM items")
            assert cursor.fetchone() == (1,)
```

The installed package also provides pytest fixtures for independent databases;
see the [Python guide](docs/python.md).

## Performance and resource limits

FAST reference measurements use the public Go API, a prepared 1,000-row fixture
and Fork through the first successful SQL. On a fixed MacBook Air M1 / 16 GiB /
macOS 27.0 arm64, 30 independent trials measured **374.2 ms p50, 417.7 ms p95,
446.1 ms max**. These are reference observations, not hardware-independent
guarantees or a universal CI threshold. See the
[method, commit and artifact identities](benchmarks/final-v02-local-reference.md).
GitHub-hosted runner hardware varies substantially; CI monitors correctness and
regressions. Native verification uses two bounded workers without skipping any
required integrity checks.

Memory remains substantial: the ×16 probe measured about **259 MiB per isolated
DB on macOS** (incremental physical footprint) and **327 MiB on Ubuntu**
(incremental PSS). Memory efficiency is not solved. ×16 databases completed on
both platforms and left no runtime residue after teardown in measured scenarios;
see the [memory/session envelope](benchmarks/memory-session-envelope.md).

The [practical Testcontainers comparison](benchmarks/practical-suite-comparison.md)
found fresh server/container isolation much slower in measured suites, but a
shared container with schema reset much faster for repeated tests. Those have
different isolation guarantees. Snapshot/Fork did not materially outperform
fresh mariamem Start for the small fixture. Different MariaDB versions/defaults
and an unresolved fresh-container 100-test failure in that benchmark environment
limit interpretation; mariamem is not universally faster or more reliable.

## Current limits

- Go requires `Options.NativeDir` and has no automatic native download. The
  Python wheel bundles its runtime.
- Multiple SQL clients can use one database up to the guest's session capacity
  (16 in the current native bundle). An additional connection receives a
  recoverable MySQL 1040 error; slots are reusable after guest close acknowledgement.
  This capacity is not a permanent API guarantee. Session variables, temporary
  tables and transactions are independent; parallel queries do not imply a
  throughput-scaling guarantee. Normal pools need no one-connection workaround.
- A query timeout or client context cancellation during SQL execution terminates
  that database instance. Close it and start or fork another; Go callers can
  inspect `db.Err()` with `errors.Is(err, mariamem.ErrUnusable)` and, for a host
  deadline, `errors.Is(err, context.DeadlineExceeded)`. Server-side prepared
  statements are not supported.
- Snapshots are cold: close client connections first, then wait for disconnect.
  Unfinished transactions must be resolved before snapshotting. A successful
  snapshot ends its source database. Temporary snapshots are
  removed when closed; explicit destinations are retained.
- The 0.x API may change. Native support is macOS 15+ arm64 and
  Ubuntu 24.04 LTS / x86_64; other platforms are not supported.
- The prepared RSA keys are public, non-secret test material. Default grant
  bypass is unchanged; this is not production credential provisioning or a
  claim of full public account/grant authentication support.
- ORM/framework and dbt compatibility is not yet validated. Those workloads and
  larger memory/storage architecture work follow this FAST milestone; see the
  [roadmap](docs/project-status.md#remaining-roadmap).

Project code is [GPL-2.0-only](LICENSE); bundled components keep their own
licenses and notices in [NOTICE](NOTICE) and
[THIRD_PARTY_LICENSES](THIRD_PARTY_LICENSES). The guest is derived from
[shyim/lite4mariadb](https://github.com/shyim/lite4mariadb) and MariaDB Server.
The testing API is informed by
[shibukawa/pgmem](https://github.com/shibukawa/pgmem). This is an independent
project.
