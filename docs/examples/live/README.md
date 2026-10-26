# Run an application once, restore the database for each test

These examples use the **Live candidate source**, based on df018fd, rather than
the published v0.5.3 package. Run commands from this repository root with
Go 1.26.10 and Python 3.11 or 3.14 on a supported host. They reuse the maintained
orders applications, Django migrations and seed data from the bounded E2E work.
The examples use public APIs and do not use the experimental owner/fault probe.

| Your test lifecycle | API |
| --- | --- |
| Start the application for each test with a fresh database address | `Snapshot.fork()` / `Snapshot.Fork` |
| Keep the application running and restore DB contents between sequential tests | `Snapshot.live()` / `Snapshot.Live`, then `reset()` / `Reset` |

Both examples migrate or create schema once, capture a Snapshot, create Live,
start one app, and run two tests. Each test starts with `SEED:2:ready` and inserts
the same unique SKU `NEW`. The second test checks that the previous insertion
has disappeared. The HTTP process and database address stay fixed. Teardown
stops the app before closing Live and the Snapshot. Reset failures fail test
setup; they must never allow the test body to continue against uncertain data.

## Python: Django + pytest + a real browser

The [complete pytest example](python/test_orders.py) has module-scoped application
and browser fixtures and a function-scoped page fixture. Each case gets a fresh
browser context; only the Django process is shared. It uses real migrations and
an HTTP form submission with Django's CSRF protection.

Install the fixed existing E2E requirements. mysqlclient needs its native client
build dependencies: on Ubuntu, pkg-config, default-libmysqlclient-dev and
build-essential; on macOS, pkgconf and mariadb-connector-c with its pkg-config
path available. Playwright's Linux browser dependencies are also needed; use
`playwright install --with-deps chromium --only-shell` there.

```sh
mkdir -p build/live-example
go build -p 1 -trimpath -o build/live-example/mariamem-host ./cmd/mariamem-host
python3 -m venv build/live-example/venv
build/live-example/venv/bin/python -m pip install -r tests/e2e_native_control/requirements.lock.txt
PLAYWRIGHT_BROWSERS_PATH="$PWD/build/live-example/browsers" \
  build/live-example/venv/bin/python -m playwright install chromium --only-shell
PYTHONPATH="$PWD/python" \
  MARIAMEM_HOST_BINARY="$PWD/build/live-example/mariamem-host" \
  PLAYWRIGHT_BROWSERS_PATH="$PWD/build/live-example/browsers" \
  build/live-example/venv/bin/python -m pytest docs/examples/live/python/test_orders.py -v
```

Run sequentially without pytest-xdist. The existing Django settings use
`CONN_MAX_AGE=0`; requests finish and physical SQL sessions close before the next
reset. The subprocess uses the existing numeric-loopback HTTP harness to avoid
reverse DNS during macOS startup. Application SQL and migration bytes stay the
same. The server log is retained in pytest's temporary directory on failure.

## Go: public Live with a long-running HTTP application

The [complete Go test](go/live_test.go) uses the public Go API directly. It builds
on the maintained Go application variant whose pool has `MaxIdleConns(0)`.
The application starts once as a subprocess; sequential `t.Run` cases send real
GET and POST requests and verify the application PID and DB endpoint. These are
HTTP E2E tests; the Python example above adds browser rendering and interaction.

```sh
mkdir -p build/live-example
go build -p 1 -trimpath -o build/live-example/go-orders ./tests/live_acceptance/goapp
MARIAMEM_RUN_LIVE_EXAMPLES=1 \
  E2E_GO_APP="$PWD/build/live-example/go-orders" \
  go test -count=1 -v ./docs/examples/live/go
```

The explicit opt-in keeps the executable example out of ordinary `go test ./...`
runtime execution. Do not add `t.Parallel` when sharing one Live endpoint.
The fixed two-statement schema file is application setup, not a dump parser.
The Go test registers cleanup as soon as each owner is created, including the
rare nonnil Live returned with a creation-cleanup error.

## Adapting to your application

Finish requests and background jobs, stop new work, and release every physical
SQL connection before resetting. An idle pool connection also holds a session;
`CONN_MAX_AGE=0` and `MaxIdleConns(0)` are the choices in these small examples.
A busy reset preserves the existing database and reports an error. Live does not
carry transactions or prepared handles across resets, clear application caches,
or fence delayed jobs that open new connections later. Keep the parent Snapshot
open while you need resets. See the [Live guide](../../live.md) for failure,
cancellation and cleanup behavior.

The commands write recreatable output only beneath `build/live-example`.
After the tests finish, that directory can be removed. A sample run is not a
cross-platform acceptance or main-adoption decision for the Live candidate.

Local macOS arm64 verification of these source examples is recorded with
[original observations and checksums](verification/assessment.json): Python
3.11.17 and 3.14.9 each pass both browser cases; Go1.26.10 passes both HTTP
cases and application cleanup. The initial Go example cleanup failure is kept
under its original source identity.
