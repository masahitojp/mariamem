# Go usage

This guide describes `v0.6.2`, including in-memory Snapshot/Fork and process-local
baseline reuse. Public save/load APIs remain removed. See
[API changes and migration](changes-since-v050.md) and
[installation](../README.md#installation) for supported platforms.
The public package is `github.com/masahitojp/mariamem`.

Use `github.com/masahitojp/mariamem/mariamemtest` as the test entry. It owns
preparation, capture, per-test pools/children and cleanup. Installation commands
are in [Development and compatibility](#development-and-compatibility).

The local endpoint accepts any username and password, including
test credentials such as `test/test` or `root/root`. Credentials are not
validated and do not select a guest account or change SQL privileges. The
returned connection information still defaults to `root` with an empty
password. Use a real server for authentication and per-user privilege tests.

Since 0.6.2, the endpoint accepts [bounded input pipelining](mysql-protocol.md)
with serial execution/responses and at most1,048,581 pending bytes per physical
connection. Exceeding the bound terminates that database instance. This does not
declare general Node/ORM support or add a driver-specific SDK entry.

<a id="same-process-connections-unreleased"></a>

## Same-process connections

Since 0.6.2, Go callers can select same-process MySQL wire connections.

TCP remains the default. For Go-owned pools, opt in to `net.Pipe` with
`mariamemtest.Options{InProcess: true}`. This selects Pipe for the helper's
preparation and per-test pools. The `Prepare` callback's DSN still targets TCP,
so an external migration command can use it normally. No Node/Python connection
routing, global driver registration or listener-free startup is implied.

For a low-level `Database` returned by Start or Fork, assign its method to the
normal MySQL connector (add `database/sql` and the mysql import to your program):

```go
config, err := mysql.ParseDSN(db.DSN())
if err != nil {
    return err
}
config.DialFunc = db.DialContext
connector, err := mysql.NewConnector(config)
if err != nil {
    return err
}
pool := sql.OpenDB(connector)
defer pool.Close() // Before closing/capturing the owning database.
```

The connector stays bound to that specific Database. It accepts only `tcp` or
`tcp4` and the exact endpoint from that Database's DSN; it never redirects an
unrelated endpoint. Database name and normal driver settings still apply.
`DSN()` keeps its existing interpolation setting; select
`config.InterpolateParams = false` for real prepared parameter execution.

The same handshake, wire handlers, session slots and guest serve both transports.
A full local Pipe admission returns a `HostError` matching `ErrCapacity` before
starting a worker; TCP keeps its existing MySQL1040 response. Closed/consumed
owners match `ErrClosed`, and failed instances match `ErrUnusable`. A cancelled
Dial context is rejected; after Dial returns, the driver controls handshake/query
cancellation and I/O deadlines. Query interruption retains instance invalidation
and cooperative cleanup semantics.

Close every connection/pool and call `WaitDisconnected` before Snapshot capture.
A raw pipe awaiting handshake is busy and prevents capture. Forked databases
require their own connector/DialContext. Closing one child does not close its
siblings. Live's stable public endpoint continues to use TCP; do not reuse a
consumed Database's dialer for another owner. This opt-in reduces TCP overhead,
not SQL/wire work, and adds no compatibility or performance guarantee.

## Prepare once, Fork independent databases

Put migrations and seed SQL in `Prepare`, then request `fixture.DB(t)` in each
test. A nil `Prepare` uses an empty baseline. The complete example includes two
ordinary tests and bounded parallel subtests. Save it as `items_test.go`:

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

func TestParallelSeeds(t *testing.T) {
	for _, name := range []string{"first", "second", "third", "fourth"} {
		t.Run(name, func(t *testing.T) {
			t.Parallel()
			db := fixture.DB(t)
			if _, err := db.ExecContext(t.Context(), "INSERT INTO items VALUES (2, 'own')"); err != nil {
				t.Fatal(err)
			}
			var count int
			if err := db.QueryRowContext(t.Context(), "SELECT COUNT(*) FROM items").Scan(&count); err != nil {
				t.Fatal(err)
			}
			if count != 2 {
				t.Fatalf("count = %d, want seed plus this child's insert", count)
			}
		})
	}
}
```

Run `go test ./...`. `TestCommit` and `TestSeed` see the same seed in either order; committed
mutations and ordinary assertion failures do not become the next test's data.
`Run` invokes preparation once in this package process, runs the suite and closes
the fixture before returning its exit code to `os.Exit`. Preparation failures
skip the suite; final cleanup failure changes an otherwise successful exit to1.
Repeated `DB(t)` in one test returns that test's pool. Another test/subtest gets
another child. Do not close the supplied pool manually; the helper registers
cleanup in pool-before-child order.

Your callback may use the supplied `db` or pass `dsn` to a migration command.
Return the original error, finish transactions and retire any additional pools
or processes before returning. The helper closes its preparation pool and waits
for physical disconnect before capture. It cannot find unregistered application
work or force noncooperative callbacks to stop.

### Sequential and parallel cases

Ordinary tests run sequentially. `TestParallelSeeds` in the complete example
uses testing subtests and calls `t.Parallel()` before `DB(t)`.

`MaxForks: 2` bounds admitted child lifecycles per fixture. Run with
`go test -parallel 4 ./...` to allow four scheduled parallel tests while that
fixture still admits at most two children at a time. The parent does not acquire
a DB while waiting for subtests. Other packages/processes and additional
fixtures have independent budgets and baselines; this is not a global resource
cap or a throughput promise. No goroutine join or manual child cleanup is needed
for these testing subtests.

For helper timeouts, admission failures, cleanup debt and explicit fixture
ownership with `New`, see [prepared Go fixtures](go-prepared-fixture.md).

## Low-level database lifetimes

### Start fresh

Use `mariamem.Start(ctx, mariamem.Options{})` when you need a Fresh database
outside the test helper. Open a driver pool using its DSN, then close statements
and pools before the database. For a manual prepared lifecycle, commit and close
preparation connections, call `WaitDisconnected`, capture with `Snapshot`, and
close each Fork before releasing the baseline. Successful capture consumes the
source. These APIs remain available; ordinary tests above delegate ownership
to `mariamemtest`.

When application code accepts `*sql.DB`, pass `fixture.DB(t)` through that
construction seam, including to GORM's MySQL configuration. Keep distinct pools
for distinct children; never switch an existing pool to another endpoint. An
application-created pool remains application-owned and must close before its
child; the helper cannot automatically enroll it. Its supplied pools use real
prepared execution (`InterpolateParams=false`). Python's opt-in
[routing](connection-routing.md) is a separate integration.

## In-memory baseline lifetime

`Snapshot(ctx, SnapshotOptions{})` consumes a disconnected source DB and owns a
fixed baseline with private immutable blocks. Heap-backed capture seals the same
backing and checks its identity and structure, without rescanning every byte.
Content checks remain at internal import/transfer boundaries and when borrowed
file mappings are copied into owned memory.
`Fork` creates independent MariaDB execution
with private block changes. Closing the baseline prevents new Forks and waits
for admitted startups; started children remain usable until separately closed.

Snapshot content is process-local. `SnapshotOptions.Destination` and
`LoadSnapshot` are removed in this version. Re-run migrations/seed to prepare
state in each test process. No user-managed file or daemon is required.
Closing a handle releases its ownership; other children may still own blocks.
Go memory reclamation and OS RSS reduction have different timing.

### Per-Snapshot Fork limits

The Go API adds `SnapshotOptions.MaxForks` and `Snapshot.MaxForks()`:

```go
prepared, err := source.Snapshot(ctx, mariamem.SnapshotOptions{MaxForks: 2})
if err != nil { return err }
defer prepared.Close()
child, err := prepared.Fork(ctx)
if err != nil { return err }
defer child.Close()
```

Zero selects a finite automatic limit once at capture; explicit values1 through
2,147,483,647 override it. Invalid values reject before consuming the source.
The automatic budget is one quarter of the minimum observed physical RAM,
Linux cgroup limit and Go runtime memory limit, divided by256 MiB per child;
it falls back to a finite CPU count if memory information is unavailable.
On Linux, validated `sysinfo(2)` totalram/mem_unit and `/proc/meminfo` MemTotal
observations both participate in the minimum; either source may fail without
discarding the other. Cgroup/Go memory limits still apply when physical readings
fail. CPU fallback is used only when all memory observations are unavailable.
`MaxForks()` returns the resolved number. This is a memory heuristic, not a
CPU/latency optimum or OOM guarantee. Use an explicit limit for a latency-sensitive
suite, and budget multiple baselines/processes separately.

If the container memory limit is unreadable or invisible, auto sizing can use
host RAM and admit more children than the container can afford (for example,
64 GiB host RAM can resolve to64 despite a hidden512 MiB container limit).
Set an explicit cap in that environment. Independent root `Start` / `start()`
calls are outside Snapshot caps; finite Fork defaults are not a global DB limit.

A slot counts reservation/startup, a live child and unconfirmed cleanup. Full
capacity waits before starting another MariaDB. Go's context covers waiting and
startup; an expired capacity wait returns `HostError` with code `pool_timeout`,
stage `fork_wait` and an underlying context error. Closing a child permits a
later Fork. Capacity errors include `max_forks`, observed `occupied_slots` and
"close owned children or increase max_forks". Counts include reserved/startup,
live and unconfirmed-cleanup owners; they can change after sampling. Go's
underlying context error remains available through `errors.Is`.
Closing the baseline wakes capacity waiters while existing children
remain usable. Cleanup uncertainty stops admission; later disposal alone does
not automatically resume it. Prepare a new baseline or use an explicit Live
Reset that confirms all cleanup debt. There is no unlimited Snapshot/Fork setting.

A capture failure has a stricter limit: if cleanup of its newly owned Snapshot
also fails, the shared host records permanent `captureDebt`. `Owned.Close` caches
that error and cannot retry the descriptors; the affected parent slot remains
occupied and admission stays stopped, even after runtime disposal is confirmed.
Cleanup retry and Live Reset cannot clear this capture debt. Do not reuse that
pool; safely close its remaining owners and prepare a fresh independent lineage.
This is distinct from retryable child-runtime cleanup debt described above.

Do not synchronously request another child while the same goroutine holds every
slot. Release one first, or use a context deadline/cancellation; a deferred Close
runs only after the waiting Fork returns. Use keyed option literals when upgrading:
the expanded `SnapshotOptions` / `HTTPConfig` structs require updates to positional
literals.

Finite admission shipped in 0.6.1. See the
[adoption decision](decisions/issue53-fork-limit-adoption.md) for its accepted
limits and [current release evidence](project-status.md#current-published-release)
for exact-version qualification. Historical candidate receipts retain their own SHAs.


## Lifecycle, cancellation and errors

Start's context governs startup, not the lifetime of the returned DB.
Zero startup/shutdown/query timeouts default to 120/30/30 seconds; negative
values are rejected. Close is idempotent and returns its stored cleanup result.
Endpoint information remains available after Close; it does not imply the DB
is usable.

Snapshot forwards its context without adding a default timeout. The shutdown
deadline does not make freeze/content validation context-interruptible; cleanup can
outlast it. Successful Snapshot consumes its source; precondition rejection
leaves it running. Failure after acceptance can consume it as well
(`HostError.Closed`). Use `errors.Is` with `ErrBusy`,
`ErrTransactionActive`, `ErrClosed`, and `errors.As` with `*HostError`.

Stored procedures
and functions are supported through ordinary SQL, including
CALL result chains and Snapshot/Fork retention. Packages/package bodies are
outside product support and compatibility testing; events remain unavailable
in the embedded build (1235). DEFINER clauses and SQL SECURITY metadata are
accepted and retained, but `--skip-grant-tables` means account existence and
privileges are not enforced. See the [approved scope](decisions/routine-support-scope.md).
Since 0.6.0, the endpoint supports real server-side execution for Go explicit/implicit
Prepare and Python prepared cursors.
`DELIMITER` is a client directive, not server SQL. Python provides
an explicit [bounded dump reader](importing-dump.md); this is not a general
SQL-script importer or a Go dump API.

Oracle mysql-connector-python 26.7.0 has two named, accepted consumer exceptions:

- For the tested prepared CALL emitting two result sets via nextset, advancing
  after the first set can fail and leave that connection unusable. This affects
  pure mode on both supported guest platforms and macOS C/default in the fixed
  native-matched observations; it is not a claim about every CALL or driver.
- macOS C/default can shorten an untyped prepared character projection of
  A-NUL-B to A without a useful error. Typed binary columns preserve all bytes;
  pure mode preserves that projection. This is not evidence of file corruption.

Separately, in the native-matched macOS C-extension prepared syntax-error
case, the client reports `2006/HY000` although raw wire returns `1064/42000`
and subsequent SQL succeeds. This is the native-parity error-presentation
disposition, not a third exception under the CALL/NUL decision. It does not
make other `2006` errors safe or recoverable.

See the [CALL/NUL boundaries](decisions/prepared-consumer-exceptions.md)
and [syntax-error presentation](reviews/v06x-prepared-product-design.md#c-extension-syntax-error).
MariaDB Connector/Python 1.1.14 passes the two CALL/NUL cases on both supported
guest platforms; this is not blanket driver compatibility or a repair to Oracle
Connector/Python. Ubuntu's additional explicit C-extension mode may be unavailable
and is an allowed SKIP, not C-mode compatibility PASS; required default/pure modes
have their own executed evidence. No driver mode is silently substituted.
Server-side cursors / COM_STMT_FETCH remain unsupported.

<a id="wire-scope-for-current-source-builds"></a>

### Wire scope

Connection information defaults to root/empty password; placeholder credentials
are also accepted without authentication. TLS/SSL, compression,
DEPRECATE_EOF and alternate authentication are not advertised/supported in this
profile. COM_RESET_CONNECTION, server-side cursors/COM_STMT_FETCH, LOCAL INFILE
transfer, CHANGE_USER, STATISTICS, PROCESS_INFO and binlog/replication streaming
are outside0.6.2 support. Multi-packet continuation is also outside this profile.
SQL-file import is not LOCAL INFILE; metadata SQL is not an administrative wire
command. Per-entry uncaptured paths remain unverified;
passing application/Release tests is not evidence of additional protocol coverage.
See the [bounded wire contract and reopening rule](decisions/v060-wire-contract.md).



Multiple SQL clients have separate sessions, transactions and temporary tables.
Current capacity is 16, not a permanent API or throughput guarantee. Excess TCP
connections receive recoverable MySQL error 1040; Go Pipe admission returns
`ErrCapacity`. Slots are reused after disconnect cleanup. Close the pool before `WaitDisconnected`.
The DSN enables driver-side parameter interpolation for ordinary queries.
Go explicit Prepare uses real prepared execution since 0.6.0;
interpolation is not required as a substitute for it.

Ordinary SQL errors leave the DB usable. A fatal guest
worker trap invalidates the DB promptly and retains its cause, without waiting
for the query timeout. Host query timeout, client cancellation or disconnect
during active SQL also invalidates the DB. Close it and start/fork
another rather than retrying against it. `db.Err()` matches `ErrUnusable` and
retains the cause; a host deadline also matches `context.DeadlineExceeded`.
`db.Closed()` becomes true. Forced reclamation of hung execution is not guaranteed.

`HostError.Code` identifies startup/lifecycle errors and `Stage` adds diagnostic
context; causes remain unwrap-able. Startup failures return no usable DB.
`Logs()` retains bounded diagnostics. Stage names are not a stable list of
internal mechanisms.

## Development and compatibility

Install the published module and optional release audit files with:

```sh
go get github.com/masahitojp/mariamem@v0.6.2
gh release download v0.6.2 --repo masahitojp/mariamem \
  --pattern 'SHA256SUMS' --pattern 'mariamem-0.6.2-corresponding-source.tar.gz'
```

Runtime details belong in [architecture](v04-generated-go-architecture.md).
See [local verification](development.md#local-verification) for scoped
development checks, [release notes](../release/NOTES-v0.6.2.md)
and [API migration](changes-since-v050.md).
The full generated guest is not
Go race-detector clean; focused checks do not establish general race cleanliness.

Since 0.6.0, the package supports stable Live endpoints across sequential browser E2E
cases. Use independent Forks for concurrent cases; Live does not promise a
parallel shared mutable endpoint. See the [Live guide](live.md) for connection
draining and reset ownership.

## Owned E2E entry

The [owned E2E examples](examples/e2e_owned/README.md) demonstrate
application-specific preparation/start/quiescence/stop hooks over Live. This
entry was approved for bounded main adoption with the supplied hook obligations;
it is available since 0.6.0. Existing direct Live APIs remain the mechanism
underneath the entry. See the [integration receipt](reviews/e2e-integration-ci-41095184074/assessment.json)
for exact tested source/profiles. Arbitrary unregistered work and non-cooperative
shutdown remain outside the guarantee; detailed resource characterization is deferred.
