# mariamem

**Disposable, in-memory MariaDB for tests.**

Make a real MariaDB as disposable as a test double.

mariamem runs MariaDB/InnoDB in a Wasm runtime and exposes a local MySQL endpoint
for Python tests. The Python API manages startup, shutdown, isolated databases,
and cold snapshots. A platform wheel bundles the Go host, Wasmer headless, and
MariaDB guest; users do not need Docker, a MariaDB installation, or a compiler.

**Status:** Python `0.1.0a2`, under release preparation. No PyPI release is
available yet. The initial native alpha targets macOS 15+ on Apple Silicon.
macOS 12 guest execution failed; macOS 12–14 are unsupported. Clean macOS 15
acceptance passed. See [the release checklist](docs/releasing.md) and
[the compatibility finding](docs/macos-compatibility.md).

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

## Installation

For a locally built wheel:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install './build/dist/mariamem-0.1.0a2-py3-none-macosx_15_0_arm64.whl[test]'
```

The `test` extra installs PyMySQL, pytest, and pytest-xdist. The wrapper itself
uses the Python standard library. See [development](docs/development.md) to
build the guest and wheel.

Go users can follow the [Go API guide](docs/go.md) to fetch the module and use
an existing native bundle through `Options.NativeDir`. Native runtime binaries
are not downloaded by `go get`.

## pytest

The installed package automatically registers its pytest plugin:

```python
def test_query(mariamem_connection_info):
    with pymysql.connect(**mariamem_connection_info) as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1")
            assert cursor.fetchone() == (1,)
```

Each test receives an independent database restored from a session snapshot.
See [Python usage](docs/python.md) for migration/seed templates and class fixtures.

## Scope

- Real MariaDB SQL and InnoDB transaction behavior; SQL is not reimplemented.
- One simultaneous SQL connection per database; independent forks can run in parallel.
- MySQL text protocol, tested with PyMySQL. Prepared statements and broad ORM/driver
  compatibility are not supported in this alpha.
- The running data directory is in Wasmer's memory filesystem. Logs, runtime
  settings, and cold snapshots use temporary host directories.
- Each database starts a Go host process and a Wasmer child. In-process Go
  embedding, a Go-owned VFS, and live/COW snapshots are future work.
- Snapshot creation stops its source database. Database startup and memory use
  are not yet optimized; this is not a promise of test-double performance.

## Architecture

```text
Python lifecycle API ────────────┐
                               ▼
PyMySQL ── MySQL/TCP ──► Go host process
                               │ internal session/query protocol
                               ▼
                        Wasmer process
                               │
                        MariaDB WASM
                               │
                        in-memory filesystem
```

## License and upstream

Project code is GPL-2.0-only, with third-party components retaining their own
licenses. See [LICENSE](LICENSE), [NOTICE](NOTICE), and
[THIRD_PARTY_LICENSES](THIRD_PARTY_LICENSES).

The guest is a modified derivative of
[shyim/lite4mariadb](https://github.com/shyim/lite4mariadb), itself based on MariaDB
Server. The disposable testing API is informed by
[shibukawa/pgmem](https://github.com/shibukawa/pgmem).
This project is independent of the upstream projects.
