# Go API

The public package is `mariamem` at the module root. Unit tests and the opt-in
real-guest integration test below cover the initial API. Use Go 1.26 or newer.
The [README](../README.md#go) has a complete first-query example.

The published Go version is `v0.1.0-alpha.3`. In a fresh directory, initialize
a consumer module and fetch it with:

```sh
mkdir mariamem-example
cd mariamem-example
go mod init example.com/mariamem-example
go get github.com/masahitojp/mariamem@v0.1.0-alpha.3
```

Save the complete [README example](../README.md#go) as `main.go`. It imports
both mariamem and `github.com/go-sql-driver/mysql`. Resolve the imports of your
own program before running it:

```sh
go mod tidy
```

`go get mariamem` does not by itself resolve every package imported directly
by a consumer's source file. The example imports mariamem with:

```go
import "github.com/masahitojp/mariamem"
```

`go get` fetches Go source and module dependencies, **not the native runtime**.
Download `mariamem-native-darwin-arm64.tar.gz` from the published GitHub Release,
extract it, and run the example:

```sh
gh release download v0.1.0-alpha.3 --repo masahitojp/mariamem \
  --pattern 'mariamem-native-darwin-arm64.tar.gz'
tar -xzf mariamem-native-darwin-arm64.tar.gz
export MARIAMEM_NATIVE_DIR="$PWD/mariamem-native-darwin-arm64"
go run .
# SELECT 1 = 1
```

An existing native bundle and explicit `Options.NativeDir` remain required.
The README example reads `MARIAMEM_NATIVE_DIR` and passes it as `NativeDir`;
the Go package does not read this environment variable automatically.
The following excerpt belongs inside a function with `ctx`; import
`database/sql` and register `github.com/go-sql-driver/mysql` as in the README.

```go
db, err := mariamem.Start(ctx, mariamem.Options{
    NativeDir: "/path/to/native",
})
if err != nil { return err }
defer db.Close()

sqlDB, err := sql.Open("mysql", db.DSN()) // register go-sql-driver/mysql in the app
if err != nil { return err }
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
No binaries are committed to the Go module and no downloads occur. The supported
native platform is macOS 15+ arm64. The recorded native candidate passed clean
macOS 15.7.7 arm64 acceptance; see [the evidence](../release/evidence/macos15-arm64-acceptance.json).

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
snapshot through the existing host. Fork startups from the same snapshot may run
concurrently. Close waits for admitted startups before deleting owned files; once
Close is waiting for the lock, new Fork calls wait and then return ErrClosed.
Already-started forks survive snapshot Close. Manifest format/hash/commit-marker semantics
are unchanged. ConnectionInfo and DSN are immutable endpoint metadata, available
after Close; use Closed to inspect lifecycle state. Zero-value handles cannot start
operations; construct them through Start and Database.Snapshot.

Multiple clients can connect to one DB up to the guest-advertised session
capacity (16 for the current native bundle). Each connection has its own guest
session and transaction state. A connection beyond capacity receives MySQL
error 1040; closing a client releases its slot after guest cleanup. Different
sessions may have queries in flight together, without a throughput guarantee.
Close the database/sql pool before WaitDisconnected when taking a snapshot.
DSN sets `interpolateParams=true` for driver-side
parameter interpolation through the supported text protocol. **This is not server
prepared-statement support**; explicit Prepare remains unsupported.

A host `QueryTimeout` or client context cancellation while SQL runs terminates
the guest and invalidates that database instance. The host also treats a client
disconnect during SQL as fatal; a normal disconnect while idle leaves the DB
usable. Do not retry SQL against an invalidated instance: close it and start or
fork another. `db.Closed()` becomes true, and `db.Err()` reports
`ErrUnusable` with the underlying cause. For a host timeout,
`errors.Is(db.Err(), context.DeadlineExceeded)` is true; a MySQL-driver query
receives a server error explaining that the instance was terminated. For a
caller context deadline or explicit cancellation, go-sql-driver/mysql returns
the caller's context error (`errors.Is` matches `context.DeadlineExceeded` or
`context.Canceled`); the host sees the resulting connection loss and terminates
the guest. The wire protocol does not carry the caller's context reason to the
host, so `db.Err()` reports a client disconnect in that case. Snapshot and
WaitDisconnected reject invalidated instances; Close remains idempotent and
releases the guest process and temporary files. Signal handlers are not
installed in the caller process.

## Opt-in integration verification

Use the existing native bundle, without rebuilding or rearranging its artifacts:

```sh
MARIAMEM_NATIVE_DIR="$PWD/python/mariamem/_native" python3 scripts/verify.py integration
```

The integration entry point runs Go real-guest tests with the race detector and
Python timeout/multi-client checks. It requires `MARIAMEM_NATIVE_DIR`; a missing
bundle is a failure, not a silently skipped test. The module pins the test driver
`github.com/go-sql-driver/mysql` to v1.9.3. Applications register their own driver.

Verified on the development macOS arm64 machine with the existing native bundle:
MariaDB reported `13.1.0-MariaDB-embedded`. The test passed ConnectionInfo and DSN
connections, SELECT 1/version, verified InnoDB storage, parameterized INSERT/SELECT
via text interpolation, BEGIN/COMMIT, and ErrTransactionActive mapping without
consuming the source. It also passed pool Close → WaitDisconnected, seeded
snapshot/source closure, independent A/B forks, temporary snapshot deletion while
forks remain usable, explicit snapshot retention/existing-destination rejection,
and idempotent Close with listener shutdown. No production fixes were required.

Only the deliberate active-transaction rejection test snapshots with a live SQL
connection. It tolerates the brief ErrBusy interval between a wire reply and host
session-idle bookkeeping, then requires ErrTransactionActive. All successful
snapshots follow pool Close → WaitDisconnected.

This integration test is correctness evidence, not a benchmark. It now also
covers query interruption and multiple independent SQL clients. The separate
clean macOS 15 acceptance is recorded above. Prepared statements are not tested.
For when to run the other local checks, see [development](development.md#local-verification).

## Manual native bundle (local candidate)

Generate a Go bundle from the existing wheel staging artifacts; this does not
rebuild the guest, alter the wheel, download binaries, or publish a release:

```sh
python3 scripts/package_native.py
python3 scripts/package_native.py --verify build/release/native-candidate/mariamem-native-darwin-arm64.tar.gz
```

Use `--native-dir /path/to/existing/native` for another staged bundle. Inputs must
match its manifest, sidecar, and the repository's candidate deployment target.
Outputs live under ignored `build/release/native-candidate/`, separate from the
release-approved `build/release/publish/` directory. The archive and SHA256SUMS
are accompanied by `native-candidate.json` recording archive and member hashes.
Packaging the same input bytes produces the same archive bytes (sorted members,
fixed timestamps/ownership/modes and gzip header); this does not promise identical
MariaDB/Wasmer binaries from independent builds or across compression toolchains.

The archive expands to `mariamem-native-darwin-arm64/`, containing:

- `manifest.json`, `wasmer-headless` (executable), `mariamem.wasmu`, `mariamem.wasmu.json`
- Existing `LICENSE`, `NOTICE`, `THIRD_PARTY_LICENSES`, and `licenses/` copied unchanged
- `CANDIDATE.json`: stable input build-manifest/lock hashes; release reviews and
  clean-platform acceptance remain external and refer to the archive SHA256

The manifest retains its format, declares the macOS 15 minimum, removes the
unused `mariamem-host` hash, and records the three required artifact hashes.
The host executable is not included. `public_release_ready` is always false for
this candidate tool, even if the input manifest says otherwise.

For local evaluation, or when using the published archive, verify it against
its published SHA256 and then extract it:

```sh
go get github.com/masahitojp/mariamem@v0.1.0-alpha.3
shasum -a 256 mariamem-native-darwin-arm64.tar.gz
tar -xzf mariamem-native-darwin-arm64.tar.gz
export MARIAMEM_NATIVE_DIR="$PWD/mariamem-native-darwin-arm64"
```

Pass the extracted directory explicitly to Go; the API does not automatically
read this environment variable:

```go
db, err := mariamem.Start(ctx, mariamem.Options{
    NativeDir: os.Getenv("MARIAMEM_NATIVE_DIR"),
})
```

The locally generated archive remains a candidate with
`public_release_ready=false` in its metadata; this packaging command does not
publish or stage it as an approved Release asset. The exact candidate hash has
clean-platform evidence, and [release review](../release/review.json) records the
source and runtime-notice checks. It is separate from the Python wheel and the
corresponding-source archive staged by the [release guard](releasing.md).
