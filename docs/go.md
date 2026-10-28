# Go usage

This guide describes `v0.5.3`: in-memory Snapshot/Fork and process-local baseline
reuse. Public save/load APIs are removed. See
[API changes and migration](changes-since-v050.md) and
[installation](../README.md#installation) for supported platforms.
The public package is `github.com/masahitojp/mariamem`.

For the unreleased Go prepared-test helper candidate, see
[prepared Go fixtures](go-prepared-fixture.md). The v0.5.3 examples below retain
explicit lifecycle ownership.

## Start fresh

Use `Start` to acquire a disposable database and an ordinary MySQL driver to
connect. Fresh means the new database's initial state; it is usually simplest
for light fixtures.

```go
package example

import (
	"context"
	"database/sql"
	"testing"

	_ "github.com/go-sql-driver/mysql"
	"github.com/masahitojp/mariamem"
)

func TestItems(t *testing.T) {
	ctx := context.Background()
	db, err := mariamem.Start(ctx, mariamem.Options{})
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
	defer pool.Close() // Runs before DB Close.
	if _, err := pool.ExecContext(ctx, "CREATE TABLE items(id INT PRIMARY KEY) ENGINE=InnoDB"); err != nil {
		t.Fatal(err)
	}
	if _, err := pool.ExecContext(ctx, "INSERT INTO items VALUES(1)"); err != nil {
		t.Fatal(err)
	}
	var count int
	if err := pool.QueryRowContext(ctx, "SELECT COUNT(*) FROM items").Scan(&count); err != nil {
		t.Fatal(err)
	}
	if count != 1 {
		t.Fatalf("count = %d", count)
	}
}
```

The application may use its own connections, commit and roll back normally.

For application tests, pass a new child-owned `*sql.DB` through your normal
application/GORM construction seam. Keep separate pools for separate children;
do not switch one existing pool between endpoints. Explicit prepared execution
can use `mysql.ParseDSN(child.DSN())`, set `InterpolateParams=false`, then
`mysql.NewConnector` and `sql.OpenDB`. Close statements/pool before the child.
The [tested consumer](../tests/routing_acceptance/go_consumer.go) exercises this
pattern. Python's optional [routing helper](connection-routing.md) is a separate
integration; it does not change the Go API or the current DSN default.
Per-test isolation comes from disposing of the DB, not from a test transaction
imposed by mariamem. Close driver connections and pools before the DB.

## Prepare once, Fork independent databases

### Sequential and parallel cases

Prepare migrations/seed once, commit and close every preparation connection,
then wait for disconnect cleanup before capture. Successful Snapshot consumes
the source DB. Each child owns its own pool, which closes before that child.

The following example first runs cases sequentially, then runs the same cases
with bounded goroutine concurrency against the same unchanged baseline. Each
case sees only the seed and its own insert. Return errors to the caller rather
than failing a test from a background goroutine.

```go
package example

import (
	"context"
	"database/sql"
	"errors"
	"fmt"
	"sync"
	"testing"

	_ "github.com/go-sql-driver/mysql"
	"github.com/masahitojp/mariamem"
)

func TestSnapshotCases(t *testing.T) {
	if err := snapshotCases(context.Background()); err != nil {
		t.Fatal(err)
	}
}

func prepareUsers(ctx context.Context, db *mariamem.Database) (err error) {
	pool, err := sql.Open("mysql", db.DSN())
	if err != nil {
		return err
	}
	defer func() { err = errors.Join(err, pool.Close()) }()
	// ExecContext uses autocommit; explicit migration transactions must commit too.
	if _, err := pool.ExecContext(ctx, "CREATE TABLE users(id INT PRIMARY KEY) ENGINE=InnoDB"); err != nil {
		return err
	}
	_, err = pool.ExecContext(ctx, "INSERT INTO users VALUES(1)")
	return err
}

func checkChild(ctx context.Context, baseline *mariamem.Snapshot, id int) (err error) {
	child, err := baseline.Fork(ctx)
	if err != nil {
		return err
	}
	defer func() { err = errors.Join(err, child.Close()) }()
	pool, err := sql.Open("mysql", child.DSN())
	if err != nil {
		return err
	}
	defer func() { err = errors.Join(err, pool.Close()) }() // Before child.Close.
	if _, err := pool.ExecContext(ctx, "INSERT INTO users VALUES(?)", id); err != nil {
		return err
	}
	var count int
	if err := pool.QueryRowContext(ctx, "SELECT COUNT(*) FROM users").Scan(&count); err != nil {
		return err
	}
	if count != 2 {
		return fmt.Errorf("child %d: count = %d, want 2", id, count)
	}
	return nil
}

func snapshotCases(ctx context.Context) (err error) {
	source, err := mariamem.Start(ctx, mariamem.Options{})
	if err != nil {
		return err
	}
	defer func() { err = errors.Join(err, source.Close()) }()
	if err := prepareUsers(ctx, source); err != nil {
		return err
	} // The preparation pool has closed; never retain it across capture.
	if err := source.WaitDisconnected(ctx); err != nil {
		return err
	}
	baseline, err := source.Snapshot(ctx, mariamem.SnapshotOptions{})
	if err != nil {
		return err
	}
	defer func() { err = errors.Join(err, baseline.Close()) }()
	// source is now consumed; its deferred Close is safe and idempotent.

	ids := []int{2, 3, 4, 5}
	// Sequential: one child and its SQL work finish before the next Fork.
	for _, id := range ids {
		if err := checkChild(ctx, baseline, id); err != nil {
			return err
		}
	}

	// Parallel: at most two child lifecycles run at once.
	slots := make(chan struct{}, 2)
	results := make(chan error, len(ids))
	var children sync.WaitGroup
	for _, id := range ids {
		slots <- struct{}{}
		children.Add(1)
		go func(id int) {
			defer children.Done()
			defer func() { <-slots }()
			results <- checkChild(ctx, baseline, id)
		}(id)
	}
	children.Wait() // All pools/children close before baseline.Close can run.
	close(results)
	for childErr := range results {
		err = errors.Join(err, childErr)
	}
	return err // Includes startup, SQL, assertion and cleanup errors.
}
```

Save the example in `snapshot_test.go` and run it with `go test` in a module
with mariamem and the MySQL driver installed. The buffered result channel holds
one result per case, so errors cannot block the join. All submitted cases finish even if one fails; the example collects their
errors rather than cancelling siblings. Choose a concurrency bound appropriate
to your workload and host resources; it is not a throughput promise.

To compare timing, measure wall elapsed time around the sequential loop and
around the whole parallel batch including `Wait`. Overlapping child operation
durations cannot be summed to obtain the parallel batch's elapsed time. Report
preparation/capture separately, or state explicitly when it is included.

Snapshot fixes schema/data, not a running server or SQL file. Fork starts a new
mutable database; connections and active transactions are not inherited.
Children cannot update the baseline or siblings. Snapshotting a modified child
creates a new baseline.

Fork inherits the preparation DB's options. Startups may run concurrently.
Snapshot Close prevents future Forks, waits for admitted startups, and releases
its backing. Successfully started children remain usable and must be closed
separately. Close is idempotent. Do not copy DB or Snapshot handles.

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
`DELIMITER` is a client directive; this does not add a general dump importer.

Oracle mysql-connector-python26.7.0 has two accepted, native-matched limits:
prepared CALL result traversal can fail and leave that connection unusable;
Mac C/default can shorten a NUL-containing untyped character projection.
Typed binary columns preserve these bytes. The two cases pass with MariaDB
Connector/Python1.1.14 on both supported guest platforms; this is not blanket
driver compatibility. See the [exact consumer boundaries](decisions/prepared-consumer-exceptions.md).
Server-side cursors / COM_STMT_FETCH remain unsupported.


Multiple SQL clients have separate sessions, transactions and temporary tables.
Current capacity is 16, not a permanent API or throughput guarantee. Additional
connections receive recoverable MySQL error 1040; slots are reused after
disconnect cleanup. Close the pool before `WaitDisconnected`.
The DSN enables driver-side parameter interpolation for ordinary queries.
Go explicit Prepare uses real prepared execution in current source builds;
interpolation is not required as a substitute for it.

Ordinary SQL errors leave the DB usable. Host query timeout, client cancellation
or disconnect during active SQL invalidates the DB. Close it and start/fork
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
