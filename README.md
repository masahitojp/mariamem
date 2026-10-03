# mariamem

**Make a real MariaDB as disposable as a test double.**

mariamem starts an isolated MariaDB for a test, lets an ordinary MySQL client
connect, and disposes of the database afterward. It runs a modified MariaDB
guest translated to generated Go; it does not reimplement MariaDB SQL or InnoDB.
Go hosts run in the test process; Python starts the packaged Go host process.
Both languages have public lifecycle APIs.

**Direct-linked generated Go is the default v0.4.0 runtime.** Ordinary Go
`Start(ctx, Options{})` and Python `mariamem.start()` need no Wasmer bundle,
NativeDir or runtime download. Explicit legacy bundle overrides remain supported.
See [architecture](docs/v04-generated-go-architecture.md) and
[canonical measurements](benchmarks/v04-integrated-candidate.md).
[v0.4.0 is published](https://github.com/masahitojp/mariamem/releases/tag/v0.4.0).
See [release notes](release/NOTES-v0.4.0.md) and
[current product direction / roadmap](docs/project-status.md).

The testing workflow is Docker-free: each disposable database has its own server
state. Prepare migrations/fixtures once with Snapshot, then Fork independent
databases without adding rollback, schema-reset or data-cleanup logic to each
test. Close client connections and owned database/snapshot handles normally.

The canonical Python distribution version is `0.4.0`; the Go module uses
the exact `v0.4.0` tag. Python wheels are available from the matching GitHub Release.
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

The v0.4.0 host-only wheel contains a Go host executable with generated-Go
MariaDB linked in; no Wasmer/native bundle or Docker is needed. Use a virtual environment:

```sh
python3 -m venv .venv
source .venv/bin/activate
```

**macOS 15+ / arm64:**

```sh
python -m pip install https://github.com/masahitojp/mariamem/releases/download/v0.4.0/mariamem-0.4.0-py3-none-macosx_15_0_arm64.whl
```

**Ubuntu 24.04 LTS / x86_64:**

```sh
python -m pip install https://github.com/masahitojp/mariamem/releases/download/v0.4.0/mariamem-0.4.0-py3-none-linux_x86_64.whl
```

For the SQL example below and pytest fixtures, install the `test` extra using a
PEP 508 direct reference instead of the plain command above:

```sh
# macOS arm64
python -m pip install 'mariamem[test] @ https://github.com/masahitojp/mariamem/releases/download/v0.4.0/mariamem-0.4.0-py3-none-macosx_15_0_arm64.whl'
# Ubuntu x86_64
python -m pip install 'mariamem[test] @ https://github.com/masahitojp/mariamem/releases/download/v0.4.0/mariamem-0.4.0-py3-none-linux_x86_64.whl'
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
go get github.com/masahitojp/mariamem@v0.4.0
```

The normal API needs no native path:

```go
db, err := mariamem.Start(ctx, mariamem.Options{})
```

Generated Go is ordinary module source compiled by the consumer's `go build`.
Each DB runs directly in the caller with fresh runtime/thread/TLS/FD and private
writable filesystem state. Normal startup does not provision an executable,
spawn a guest subprocess or resolve/download a Wasmer bundle. Explicit
`Options.NativeDir` and `MARIAMEM_NATIVE_DIR` select the legacy compatibility
path; see the [Go guide](docs/go.md).

Source/provenance review assets can be downloaded separately;
they are not required for ordinary startup:

```sh
gh release download v0.4.0 --repo masahitojp/mariamem \
  --pattern 'SHA256SUMS' --pattern 'mariamem-0.4.0-provenance.json' \
  --pattern 'mariamem-0.4.0-corresponding-source.tar.gz'
```

## Performance and resource limits

Fixed Apple M1 / 16 GiB / macOS 27.0.1 arm64 / Go 1.26.8 measurements:

| Boundary | Wasmer reference p50 | v0.4 candidate p50 / p95 |
| --- | ---: | ---: |
| Start → first SQL | 308.5 ms | 38.4 / 593.7 ms |
| prepared Fork → COUNT | 288.7 ms | 104.6 / 251.6 ms |
| Snapshot | 404.6 ms | 399.9 / 570.8 ms |
| ×16 CPU | 9.463 CPU-sec | 2.814 / 2.954 CPU-sec |
| SQLAlchemy100 Fork | 43.142 s | 20.430 / 20.705 s |

Thirty Start/Snapshot/Fork trials, ten scaling trials and three ORM suites per
mode; no slow runs removed. These are reference-machine observations, not
hardware-independent guarantees or Python end-to-end startup timings.
Snapshot preallocation reduced diagnostic TotalAlloc by **69.6%**. Snapshot
median is approximately unchanged versus Wasmer; its p95 is slower. Start's p95
includes observable approximately one-second startup tails.

Prepared ×16 physical footprint was **3664.7 MiB p50**; incremental footprint
was **197.4 MiB per DB p50**. Immediate post-Close physical accounting remains
high and is distinct from reachable Go heap. It is not claimed harmless or
immediately reclaimable. See [canonical boundaries and identities](benchmarks/v04-integrated-candidate.md)
and [memory-lifetime attribution](benchmarks/v04-snapshot-memory-lifetime.md).

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
