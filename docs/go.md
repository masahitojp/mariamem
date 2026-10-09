# Go usage

This guide describes `v0.4.4`.
[Installation](../README.md#installation) uses the published module tag `v0.4.4`.
The public package is `github.com/masahitojp/mariamem`.

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
Per-test isolation comes from disposing of the DB, not from a test transaction
imposed by mariamem. Close driver connections and pools before the DB.

## Prepare once, Fork independent databases

Prepare migrations/fixtures through the usual driver, commit, close all clients
and wait for disconnect cleanup. Then create the fixed baseline:

```go
// setupDB is a database returned by Start; its SQL preparation is complete.
if err := setupDB.WaitDisconnected(ctx); err != nil {
    return err
}
baseline, err := setupDB.Snapshot(ctx, mariamem.SnapshotOptions{})
if err != nil {
    return err
}
defer baseline.Close()
// Successful Snapshot has ended setupDB.

first, err := baseline.Fork(ctx)
if err != nil {
    return err
}
defer first.Close()

second, err := baseline.Fork(ctx)
if err != nil {
    return err
}
defer second.Close()
// first and second start with the same schema/data.
// Committed writes or schema changes in first cannot appear in second.
```

Snapshot fixes schema/data, not a running server or SQL file. Fork starts a new
mutable database; connections and active transactions are not inherited.
Children cannot update the baseline or siblings. Snapshotting a modified child
creates a new baseline.

Fork inherits the preparation DB's options. Startups may run concurrently.
Snapshot Close prevents future Forks, waits for admitted startups, and releases
its backing. Successfully started children remain usable and must be closed
separately. Close is idempotent. Do not copy DB or Snapshot handles.

## Persist expensive preparation

An empty `SnapshotOptions.Destination` makes temporary, implementation-owned
capture storage. Closing the handle releases it.

An explicit Destination additionally persists the fixed baseline:

```go
baseline, err := setupDB.Snapshot(ctx, mariamem.SnapshotOptions{
    Destination: "./prepared",
})
```

The destination must not already exist. Snapshot Close leaves this artifact
intact while releasing the handle's owned resources. The returned handle forks
from independent owned backing, so changes to the saved output cannot affect it.

The Go API does not currently expose arbitrary path-based reopening.
Python's `load_snapshot(path)` provides that acquisition boundary. This is an
existing language-surface asymmetry; the ownership/isolation contract is the
same where the concepts exist. A new Go import API is not added in v0.4.4.

Saved baselines contain database files tied to the compatible guest build.
They are advanced derived artifacts; retain their migration/fixture/source
inputs so they can be regenerated. mariamem does not manage invalidation,
regeneration or deletion.

Creation/import fully validates the baseline and takes ownership of the exact
state used by children. Subsequent Forks do not read every content byte again
to validate it. Damage arising in owned storage after acquisition is not
guaranteed to be detected on every Fork. This is not a same-user process
security boundary.

## Lifecycle, cancellation and errors

Start's context governs startup, not the lifetime of the returned DB.
Zero startup/shutdown/query timeouts default to 120/30/30 seconds; negative
values are rejected. Close is idempotent and returns its stored cleanup result.
Endpoint information remains available after Close; it does not imply the DB
is usable.

Snapshot forwards its context without adding a default timeout. The export
deadline does not make copy/validation context-interruptible; cleanup can
outlast it. Successful Snapshot consumes its source; precondition rejection
leaves it running. Failure after acceptance can consume it as well
(`HostError.Closed`). Use `errors.Is` with `ErrBusy`,
`ErrTransactionActive`, `ErrClosed`, and `errors.As` with `*HostError`.

Multiple SQL clients have separate sessions, transactions and temporary tables.
Current capacity is 16, not a permanent API or throughput guarantee. Additional
connections receive recoverable MySQL error 1040; slots are reused after
disconnect cleanup. Close the pool before `WaitDisconnected`.
DSN enables driver-side parameter interpolation; server-side prepared
statements are unsupported.

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
go get github.com/masahitojp/mariamem@v0.4.4
gh release download v0.4.4 --repo masahitojp/mariamem \
  --pattern 'SHA256SUMS' --pattern 'mariamem-0.4.4-corresponding-source.tar.gz'
```

Runtime details belong in [architecture](v04-generated-go-architecture.md).
See [local verification](development.md#local-verification) for scoped
development checks, and [release notes](../release/NOTES-v0.4.4.md)
for removed metadata/class-fixture interfaces. The full generated guest is not
Go race-detector clean; focused checks do not establish general race cleanliness.
