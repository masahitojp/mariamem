# Go usage

This guide describes `v0.5.3` baseline APIs and explicitly labelled, adopted
additions on unreleased main, including in-memory Snapshot/Fork and process-local
baseline reuse. Public save/load APIs are removed. See
[API changes and migration](changes-since-v050.md) and
[installation](../README.md#installation) for supported platforms.
The public package is `github.com/masahitojp/mariamem`.

Use `github.com/masahitojp/mariamem/mariamemtest` as the test entry on current
main. It owns preparation, capture, per-test pools/children and cleanup. This
helper is not in published v0.5.3: use
`go get github.com/masahitojp/mariamem@<version-or-commit>` for the examples below,
replacing the placeholder with the main commit you are testing. Published
installation commands remain in [Development and compatibility](#development-and-compatibility).

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

Unreleased main (not included in published v0.5.3): stored procedures
and functions are supported through ordinary SQL, including
CALL result chains and Snapshot/Fork retention. Packages/package bodies are
outside product support and compatibility testing; events remain unavailable
in the embedded build (1235). DEFINER clauses and SQL SECURITY metadata are
accepted and retained, but `--skip-grant-tables` means account existence and
privileges are not enforced. See the [approved scope](decisions/routine-support-scope.md).
Current source builds add real server-side execution for Go explicit/implicit
Prepare and Python prepared cursors. This is not in published v0.5.3.
`DELIMITER` is a client directive, not server SQL. Python source builds provide
an explicit [bounded dump reader](importing-dump.md); this is not a general
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

See the [CALL/NUL boundaries](decisions/prepared-consumer-exceptions.md)
and [syntax-error presentation](reviews/v06x-prepared-product-design.md#c-extension-syntax-error).
MariaDB Connector/Python 1.1.14 passes the two CALL/NUL cases on both supported
guest platforms; this is not blanket driver compatibility or a repair to Oracle
Connector/Python. Ubuntu's additional explicit C-extension mode may be unavailable
and is an allowed SKIP, not C-mode compatibility PASS; required default/pure modes
have their own executed evidence. No driver mode is silently substituted.
Server-side cursors / COM_STMT_FETCH remain unsupported.

### Wire scope for current source builds

Use the supplied local root/empty-password endpoint profile. TLS/SSL, compression,
DEPRECATE_EOF and alternate authentication are not advertised/supported in this
profile. COM_RESET_CONNECTION, server-side cursors/COM_STMT_FETCH, LOCAL INFILE
transfer, CHANGE_USER, STATISTICS, PROCESS_INFO and binlog/replication streaming
are outside0.6.0 support. Multi-packet continuation is also outside this profile.
SQL-file import is not LOCAL INFILE; metadata SQL is not an administrative wire
command. Per-entry uncaptured paths remain unverified;
passing application/Release tests is not evidence of additional protocol coverage.
See the [bounded wire contract and reopening rule](decisions/v060-wire-contract.md).



Multiple SQL clients have separate sessions, transactions and temporary tables.
Current capacity is 16, not a permanent API or throughput guarantee. Additional
connections receive recoverable MySQL error 1040; slots are reused after
disconnect cleanup. Close the pool before `WaitDisconnected`.
The DSN enables driver-side parameter interpolation for ordinary queries.
Go explicit Prepare uses real prepared execution in current source builds;
interpolation is not required as a substitute for it.

Ordinary SQL errors leave the DB usable. In current source builds, a fatal guest
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
go get github.com/masahitojp/mariamem@v0.5.3
gh release download v0.5.3 --repo masahitojp/mariamem \
  --pattern 'SHA256SUMS' --pattern 'mariamem-0.5.3-corresponding-source.tar.gz'
```

Runtime details belong in [architecture](v04-generated-go-architecture.md).
See [local verification](development.md#local-verification) for scoped
development checks, [release notes](../release/NOTES-v0.5.3.md)
and [API migration](changes-since-v050.md).
The full generated guest is not
Go race-detector clean; focused checks do not establish general race cleanliness.

Unreleased main supports stable Live endpoints across sequential browser E2E
cases. Use independent Forks for concurrent cases; Live does not promise a
parallel shared mutable endpoint. See the [Live guide](live.md) for connection
draining and reset ownership.

## Owned E2E entry — unreleased main

The source-build [owned E2E examples](examples/e2e_owned/README.md) demonstrate
application-specific preparation/start/quiescence/stop hooks over Live. This
entry was approved for bounded main adoption with the supplied hook obligations;
it is not part of published v0.5.3. Existing direct Live APIs remain the mechanism
underneath the entry. See the [integration receipt](reviews/e2e-integration-ci-41095184074/assessment.json)
for exact tested source/profiles. Arbitrary unregistered work and non-cooperative
shutdown remain outside the guarantee; detailed resource characterization is deferred.
