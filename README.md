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

The formal release candidate is `v0.3.0`; its Python distribution version is
`0.3.0`. It is not published yet. After publication, the Go module and native
bundles will use the exact `v0.3.0` tag, and Python wheels will be available from
the matching GitHub Release. Native support remains **macOS 15+ / Apple Silicon
(arm64)** and **Ubuntu 24.04 LTS / x86_64** (SSE2 + SSSE3).
PyPI publication is temporarily unavailable while account recovery is pending;
GitHub Release wheels are the supported Python installation path for now.
Other Linux distributions are not supported.
The 0.x public API may change.

Release CI tests Go 1.26.8 and Python 3.14 on macOS 15 arm64 and Ubuntu 24.04
x86_64. Package minimums (Go 1.26.0, Python >=3.9) do not imply a tested matrix
across all later language versions. Other platforms are neither supported nor
validated by these release jobs.

## Python

The v0.3.0 wheel includes the Go host executable, Wasmer runtime and MariaDB
guest; no separate native setup or Docker is needed. The candidate is not yet
published. Use a virtual environment:

```sh
python3 -m venv .venv
source .venv/bin/activate
```

**macOS 15+ / arm64:**

```sh
python -m pip install https://github.com/masahitojp/mariamem/releases/download/v0.3.0/mariamem-0.3.0-py3-none-macosx_15_0_arm64.whl
```

**Ubuntu 24.04 LTS / x86_64 (SSE2 + SSSE3):**

```sh
python -m pip install https://github.com/masahitojp/mariamem/releases/download/v0.3.0/mariamem-0.3.0-py3-none-linux_x86_64.whl
```

For the SQL example below and pytest fixtures, install the `test` extra using a
PEP 508 direct reference instead of the plain command above:

```sh
# macOS arm64
python -m pip install 'mariamem[test] @ https://github.com/masahitojp/mariamem/releases/download/v0.3.0/mariamem-0.3.0-py3-none-macosx_15_0_arm64.whl'
# Ubuntu x86_64
python -m pip install 'mariamem[test] @ https://github.com/masahitojp/mariamem/releases/download/v0.3.0/mariamem-0.3.0-py3-none-linux_x86_64.whl'
```

The extra installs PyMySQL and pytest tools. Use the wheel rather than a Git
source install: it contains the required bundled native artifacts. Once PyPI
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

Go **1.26 or newer** is required. The v0.3.0 candidate is not published yet.
After publication, add the exact released module to a fresh module:

```sh
mkdir mariamem-example
cd mariamem-example
go mod init example.com/mariamem-example
go get github.com/masahitojp/mariamem@v0.3.0
```

For a tagged v0.3.0 build, the normal API needs no native path:

```go
db, err := mariamem.Start(ctx, mariamem.Options{})
```

On first start mariamem downloads the bundle matching that exact module tag and
platform, verifies its checksums and metadata, and installs it in the user
cache. Later starts reuse and verify the cached bundle, including offline.
`Options.NativeDir` and `MARIAMEM_NATIVE_DIR` remain overrides. Development,
pseudo-version and local replacement builds require an explicitly matching
bundle; they never use an unrelated public release. See the
[Go guide](docs/go.md) for complete SQL, cache and recovery examples.

For offline use, CI and development, download the matching macOS arm64 or Ubuntu
24.04 x86_64 native archive from the GitHub Release and pass its extracted
directory in `Options.NativeDir`. The module does not embed the native runtime.
After publication, the exact platform commands will be:

```sh
# macOS 15+ arm64
gh release download v0.3.0 --repo masahitojp/mariamem \
  --pattern 'mariamem-native-darwin-arm64.tar.gz'
# Ubuntu 24.04 x86_64
gh release download v0.3.0 --repo masahitojp/mariamem \
  --pattern 'mariamem-native-ubuntu24.04-x86_64.tar.gz'
```

## Performance and resource limits

On a fixed MacBook Air M1 / 16 GiB / macOS 27.0 arm64, 30 independent Go trials
of Fork → first SQL with a prepared 1,000-row fixture measured **374.2 ms p50,
417.7 ms p95, 446.1 ms max**. These are reference-machine observations, not
hardware-independent guarantees or a universal CI threshold. See the
[method and exact identities](benchmarks/final-v02-local-reference.md).

Memory efficiency is not solved: the ×16 probe measured about **259 MiB per
isolated DB on macOS** (incremental physical footprint) and **327 MiB on Ubuntu**
(incremental PSS). Both platforms completed ×16 with no runtime residue after
teardown in measured scenarios; see the [resource envelope](benchmarks/memory-session-envelope.md).

mariamem is not universally faster than Testcontainers. Fresh server/container
isolation was much slower in measured suites, while shared-server schema reset
was much faster and has weaker isolation. Fork did not materially beat fresh
Start for the small fixture. Versions/defaults and observed benchmark-environment
failures limit interpretation; see the [practical comparison](benchmarks/practical-suite-comparison.md).

## Current limits

- The v0.3.0 release candidate is not published yet. Its Go auto-download and
  GitHub wheel installation commands become usable when those release assets
  exist. Development builds still need a matching explicit native bundle.
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
- Tested ORM coverage includes SQLAlchemy 2.x and GORM 1.x dogfood suites; this
  does not promise compatibility with every framework version or migration
  workload. dbt and larger memory/storage architecture work remain future
  validation; see the [roadmap](docs/project-status.md#remaining-roadmap).

Project code is [GPL-2.0-only](LICENSE); bundled components keep their own
licenses and notices in [NOTICE](NOTICE) and
[THIRD_PARTY_LICENSES](THIRD_PARTY_LICENSES). The guest is derived from
[shyim/lite4mariadb](https://github.com/shyim/lite4mariadb) and MariaDB Server.
The testing API is informed by
[shibukawa/pgmem](https://github.com/shibukawa/pgmem). This is an independent
project.
