# Go API

**Direct-linked generated Go is the default v0.4.3 runtime.** Ordinary Go
usage needs no NativeDir, bundle cache/download or external Wasmer. Generated
Go is a normal module dependency/build input; WASM is a build intermediate.
Existing public APIs and cold Snapshot/Fork semantics are preserved.
See [architecture](v04-generated-go-architecture.md) and
[canonical measurements](../benchmarks/v04-integrated-candidate.md).

The public package is `mariamem` at the module root. The module requires Go
1.26.0+; canonical validation uses Go 1.26.8. Go 1.27.0/1.27.1 arm64 are
unsupported because of upstream compiler issue #81036; no local workaround is
used. An upstream-fixed toolchain has been verified. v0.4.3 is released.

```sh
mkdir mariamem-example
cd mariamem-example
go mod init example.com/mariamem-example
go get github.com/masahitojp/mariamem@v0.4.3
go get github.com/go-sql-driver/mysql
```

```go
db, err := mariamem.Start(ctx, mariamem.Options{})
```

Each DB has fresh execution/thread/TLS/FD state and private writable files.
Normal Start does not decode/materialize a native image, spawn a guest process
or resolve a runtime bundle. Development/local replacement builds use the same
default. Once normal Go dependencies are available, startup needs no download.
Optional release audit assets are available separately:

```sh
gh release download v0.4.3 --repo masahitojp/mariamem \
  --pattern 'SHA256SUMS' --pattern 'mariamem-0.4.3-provenance.json'
```

## Retired legacy overrides

On this v0.4.3 candidate branch, generated-Go is the only runtime.
`Options.NativeDir` remains a deprecated source-compatibility field; nonempty
values, `MARIAMEM_NATIVE_DIR`, and `MARIAMEM_RUNTIME=wasmer` are rejected with
migration guidance. Empty or `MARIAMEM_RUNTIME=generated-go` uses compiled source.
For historical Wasmer comparisons, use an old tag and its matching artifacts.

## Lifecycle and sessions

Start's context controls startup. Zero startup/shutdown/query timeouts default
to 120/30/30 seconds; negative values are rejected. Close is idempotent and
returns the stored cleanup result. Guest diagnostics retain their last 16 KiB
via Logs.

Snapshot forwards the caller's context without adding a default timeout. A
caller deadline bounds the export operation; filesystem copy/hash is not
context-interruptible, and shutdown cleanup may outlast the deadline. Without a
deadline Snapshot waits for the export. Success consumes the source DB;
precondition rejection leaves it running. An accepted failure also consumes it
(`HostError.Closed`). Use `errors.Is` with ErrBusy, ErrTransactionActive and
ErrClosed, and `errors.As` for HostError. Underlying errors remain unwrap-able.

An empty Snapshot Destination creates an owned temporary snapshot, deleted by
Snapshot.Close. An explicit Destination is retained. Fork inherits options and
validates the saved snapshot through the host. Fork startups from the same
snapshot may run concurrently. Close waits for admitted startups before deleting
owned files; already-started forks survive Snapshot.Close. Manifest
format/hash/commit-marker semantics are unchanged. ConnectionInfo and DSN are
immutable endpoint metadata available after Close; use Closed to inspect
lifecycle state. Zero-value handles cannot start operations; construct them
through Start and Database.Snapshot.

Multiple clients can connect to one DB up to the guest-advertised session
capacity (16 for the current guest, not a permanent API guarantee).
Each connection has its own guest session and transaction state. A connection
beyond capacity receives MySQL error 1040; closing a client releases its slot
after guest cleanup. Different sessions may have queries in flight together,
without a throughput guarantee. Close the database/sql pool before
WaitDisconnected when taking a snapshot. DSN sets `interpolateParams=true` for
driver-side parameter interpolation through the supported text protocol. This
is not server prepared-statement support; explicit Prepare remains unsupported.

A host QueryTimeout or client context cancellation while SQL runs invalidates
that database instance. Forced reclamation of non-cooperative in-process guest
execution and hard failure containment are not guaranteed. A client disconnect during SQL is
also fatal; a normal disconnect while idle leaves the DB usable. Do not retry
SQL against an invalidated instance: close it and start or fork another.
`db.Closed()` becomes true, and `db.Err()` reports ErrUnusable with the
underlying cause. For a host timeout, `errors.Is(db.Err(), context.DeadlineExceeded)`
is true. A caller context deadline or explicit cancellation is returned by the
MySQL driver as the caller's context error; the host sees the connection loss
and invalidates the instance. Snapshot and WaitDisconnected reject invalidated
instances; Close remains idempotent; normal cooperative shutdown releases runtime
resources and temporary files. Signal handlers are not installed in the caller process.

## Opt-in integration verification

Run default generated-Go acceptance without a native override:

```sh
GOTOOLCHAIN=go1.26.8 python scripts/verify.py integration
```

This runs normal full-guest SQL/Snapshot/Fork/lifecycle tests, Python
multi-client checks and focused handwritten/runtime FD/MemFS/thread/TLS/futex
race coverage. The full generated guest is not Go `-race` clean; its documented
shared-memory adaptation problem is not suppressed or presented as passing.
Forced query-timeout reclamation remains a separate diagnostic, not a guarantee.
The module pins the test driver `github.com/go-sql-driver/mysql` to v1.9.3;
applications register their own driver. See [development](development.md#local-verification).

## Failure diagnostics

Use `errors.As(err, &hostError)` with `var hostError *mariamem.HostError` to read
`Code` and, when available, the failed startup `Stage`. Startup codes distinguish
`unsupported_platform`, `native_unavailable`, `artifact_mismatch`, `guest_start`,
`guest_connection`, and `host_start`. Messages include the failing input or
boundary, and guest greeting failures retain a bounded stderr tail. Causes remain
available through `errors.Is`/`errors.As`, including filesystem and context errors.
Artifact mismatch covers existing manifest/hash/guest metadata checks; the Go
module does not enforce equality with a Python distribution version.

Session capacity exhaustion remains recoverable MySQL error 1040 from the driver.
Ordinary SQL errors do not invalidate a Database. Interrupted active SQL still
invalidates the entire Database: `db.Err()` matches `mariamem.ErrUnusable` and
retains its cause. `Close()` remains safe and idempotent. Stage names provide
diagnostic context rather than a stable inventory of runtime internals.

For startup failures, read the category/stage and retained guest diagnostics.
Remove retired runtime overrides; use the supported generated-Go module.
Startup failure does not return a usable database. Retry Start after correcting
the reported input. Existing lifecycle errors remain controlled and unwrap-able.
