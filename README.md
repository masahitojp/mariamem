# mariamem

**Make a real MariaDB as disposable as a test double.**

mariamem starts an isolated MariaDB for a test, lets an ordinary MySQL client
connect and commit normally, and discards the database afterward. It runs real
MariaDB SQL/InnoDB rather than emulating them. No Docker is needed.

For light setup, create a new database for each test. For expensive migrations
and fixtures, prepare once, create a Snapshot, and Fork independent databases.
Successful Snapshot creation closes the setup database. Each child inherits the
fixed initial schema/data; its changes disappear when that child is closed.
Close application connections and database/Snapshot handles at their own scope.
Sharing initial state does not share mutations between tests.

**v0.4.3 is released.** See [release notes](release/NOTES-v0.4.3.md),
[current status](docs/project-status.md), [Go guide](docs/go.md) and
[Python/pytest guide](docs/python.md). Internal implementation and historical
runtime changes belong in [architecture](docs/v04-generated-go-architecture.md).
The [accepted product decisions](docs/decisions/README.md) record the next
contract direction; proposed API removals are not part of the released API.

The canonical Python distribution version is `0.4.3`; the Go module uses
the exact `v0.4.3` tag. Python wheels are available from the matching GitHub Release.
Supported platforms remain **macOS 15+ / Apple Silicon (arm64)** and
**Ubuntu 24.04 LTS / x86_64**.
PyPI publication is temporarily unavailable while account recovery is pending;
GitHub Release wheels are the supported Python installation path for now.
Other Linux distributions are not supported.
The 0.x public API may change.

Release CI tests Go 1.26.8 and Python 3.14 on macOS 15 arm64 and Ubuntu 24.04
x86_64. Package minimums (Go 1.26.0, Python >=3.9) do not imply a tested matrix
across all later language versions. Other platforms are neither supported nor
validated by these release jobs.

## Python

Install the platform wheel in a virtual environment:

```sh
python3 -m venv .venv
source .venv/bin/activate
```

**macOS 15+ / arm64:**

```sh
python -m pip install https://github.com/masahitojp/mariamem/releases/download/v0.4.3/mariamem-0.4.3-py3-none-macosx_15_0_arm64.whl
```

**Ubuntu 24.04 LTS / x86_64:**

```sh
python -m pip install https://github.com/masahitojp/mariamem/releases/download/v0.4.3/mariamem-0.4.3-py3-none-linux_x86_64.whl
```

For the SQL example below and pytest fixtures, install the `test` extra using a
PEP 508 direct reference instead of the plain command above:

```sh
# macOS arm64
python -m pip install 'mariamem[test] @ https://github.com/masahitojp/mariamem/releases/download/v0.4.3/mariamem-0.4.3-py3-none-macosx_15_0_arm64.whl'
# Ubuntu x86_64
python -m pip install 'mariamem[test] @ https://github.com/masahitojp/mariamem/releases/download/v0.4.3/mariamem-0.4.3-py3-none-linux_x86_64.whl'
```

The extra installs PyMySQL and pytest tools. Use the wheel rather than a Git
source install: it contains the required platform host executable. Once PyPI
publication becomes available, installation is expected to simplify to
`pip install mariamem`; PyPI distribution has not been abandoned.

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

## Go

The module requires Go **1.26.0+**; canonical validation uses **1.26.8**.
Go 1.27.0/1.27.1 arm64 are unsupported due to an upstream compiler regression
(see [known limitations](#current-limits)). Add the exact released module:

```sh
mkdir mariamem-example
cd mariamem-example
go mod init example.com/mariamem-example
go get github.com/masahitojp/mariamem@v0.4.3
```

The normal API needs no native path:

```go
db, err := mariamem.Start(ctx, mariamem.Options{})
```

Use the Go API to own the database lifecycle and your normal MySQL driver to
connect. The [Go guide](docs/go.md) describes connections, Snapshot/Fork,
cancellation and cleanup. Historical runtime overrides are retired; see its
[migration guidance](docs/go.md#retired-legacy-overrides).

Source/provenance review assets can be downloaded separately;
they are not required for ordinary startup:

```sh
gh release download v0.4.3 --repo masahitojp/mariamem \
  --pattern 'SHA256SUMS' --pattern 'mariamem-0.4.3-provenance.json' \
  --pattern 'mariamem-0.4.3-corresponding-source.tar.gz'
```

## Performance and resource limits

Preparation reuse is useful when migrations/fixture setup outweigh Snapshot
creation and repeated Fork costs. Light setup may favor a new DB each time.
Broad scans over large data still take time in each child. There is no universal
speedup, crossover or memory-sharing promise.

The [released v0.4.3 measurements](benchmarks/v043-release-baseline.md) and
[Snapshot/Fork characterization](benchmarks/v043-characterization.md) specify
exact inputs and measurement boundaries. Earlier
[v0.4.0 comparisons](benchmarks/v04-integrated-candidate.md) and
[memory investigations](benchmarks/v04-snapshot-memory-lifetime.md) are historical
and do not describe current allocator reclamation. These Go measurements are
not Python end-to-end or hardware-independent guarantees.

## Current limits

- The full generated guest is not Go `-race` clean: **GENERAL SHARED-MEMORY MODEL
  WORK REQUIRED**. No suppression is used; focused handwritten/runtime race
  tests remain enabled. See the [investigation](benchmarks/direct-link-race-scope.md).
- Go 1.27.0/1.27.1 arm64 are unsupported due to upstream issue
  [#81036](https://github.com/golang/go/issues/81036), `LDPSW: constant is not in pool`.
  An upstream-fixed toolchain has been verified; no mariamem workaround is used.
- Multiple SQL clients can use one database up to the guest's session capacity
  (16 in the current guest). An additional connection receives a
  recoverable MySQL 1040 error; slots are reusable after guest close acknowledgement.
  This capacity is not a permanent API guarantee. Session variables, temporary
  tables and transactions are independent; parallel queries do not imply a
  throughput-scaling guarantee. Normal pools need no one-connection workaround.
- A query timeout or client context cancellation during SQL execution invalidates
  that database instance. Forced reclamation of non-cooperative in-process guest
  execution and hard failure containment are not guaranteed. Close it and start or
  fork another; Go callers can
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
- Tested ORM coverage includes SQLAlchemy 2.x and GORM 1.x dogfood suites; this
  does not promise compatibility with every framework version or migration
  workload. Broader consumer coverage and resource work follow evidence of
  Disposable isolation's practical value; see the [roadmap](docs/project-status.md).

Project code is [GPL-2.0-only](LICENSE); bundled components keep their own
licenses and notices in [NOTICE](NOTICE) and
[THIRD_PARTY_LICENSES](THIRD_PARTY_LICENSES). The guest is derived from
[shyim/lite4mariadb](https://github.com/shyim/lite4mariadb) and MariaDB Server.
The testing API is informed by
[shibukawa/pgmem](https://github.com/shibukawa/pgmem). This is an independent
project.
