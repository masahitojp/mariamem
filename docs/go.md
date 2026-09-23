# Go API (Task 4a)

The public package is `mariamem` at the module root. This is the initial API
skeleton, unit-tested without a real guest. Real MariaDB integration acceptance
is deferred to Task 4b; the current module path is not yet a published import path.

```go
db, err := mariamem.Start(ctx, mariamem.Options{NativeDir: nativeDir})
if err != nil { return err }
defer db.Close()

sqlDB, err := sql.Open("mysql", db.DSN()) // register go-sql-driver/mysql in the app
if err != nil { return err }
sqlDB.SetMaxOpenConns(1)
// SQL, migrations, fixtures...
if err := sqlDB.Close(); err != nil { return err }
if err := db.WaitDisconnected(ctx); err != nil { return err }
snap, err := db.Snapshot(ctx, mariamem.SnapshotOptions{})
if err != nil { return err }
defer snap.Close()
fork, err := snap.Fork(ctx)
if err != nil { return err }
defer fork.Close()
```

`NativeDir` is required and accepts the existing native bundle unchanged:
`manifest.json`, `wasmer-headless`, `mariamem.wasmu`, `mariamem.wasmu.json`, and
optionally the existing `mariamem-host` (unused by Go). Required guest/runtime
files are checked against manifest hashes; the sidecar is also validated.
No binaries are committed to the Go module and no downloads occur. The candidate
platform remains macOS 12 arm64; clean-platform acceptance remains pending.

The host runs in the Go caller; Wasmer/MariaDB remains a child process. Start's
context only controls startup. Zero startup/shutdown/query timeouts default to
120/30/30 seconds; negative values are rejected. Close is idempotent, returning
the stored cleanup result. Guest diagnostics retain their last 16 KiB via Logs.

Snapshot forwards the caller's context without adding a default timeout. A caller
deadline bounds the existing export operation; filesystem copy/hash is still not
context-interruptible, and existing shutdown cleanup may outlast the deadline.
Without a deadline it waits for the existing snapshot operation. Success consumes
the source DB; precondition rejection leaves it running. An accepted failure also
consumes it (`HostError.Closed`). Use errors.Is with ErrBusy, ErrTransactionActive,
and ErrClosed, and errors.As for HostError. Underlying errors remain unwrap-able.

An empty Destination creates an owned temporary snapshot, deleted by Snapshot.Close.
An explicit Destination is retained. Fork inherits options and validates the saved
snapshot through the existing host. Close and Fork startup are serialized; already
started forks survive snapshot Close. Manifest format/hash/commit-marker semantics
are unchanged. ConnectionInfo and DSN are immutable endpoint metadata, available
after Close; use Closed to inspect lifecycle state. Zero-value handles cannot start
operations; construct them through Start and Database.Snapshot.

There is one simultaneous SQL connection per DB. Close the database/sql pool before
WaitDisconnected and snapshot. DSN sets `interpolateParams=true` for driver-side
parameter interpolation through the supported text protocol. **This is not server
prepared-statement support**; explicit Prepare remains unsupported. Query timeout
remains instance-fatal. Signal handlers are not installed in the caller process.
