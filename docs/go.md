# Go API

The public package is `mariamem` at the module root. Unit tests and the opt-in
real-guest integration test below cover the initial API. Use Go 1.26 or newer.

Fetch the Go source using a published version or pushed commit (replace the
placeholder; no release tag is required):

```sh
go get github.com/masahitojp/mariamem@<version-or-commit>
```

Import it with:

```go
import "github.com/masahitojp/mariamem"
```

`go get` fetches Go source and module dependencies, **not the native runtime**.
An existing native bundle and explicit `Options.NativeDir` remain required.

```go
db, err := mariamem.Start(ctx, mariamem.Options{
    NativeDir: "/path/to/native",
})
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
snapshot through the existing host. Fork startups from the same snapshot may run
concurrently. Close waits for admitted startups before deleting owned files; once
Close is waiting for the lock, new Fork calls wait and then return ErrClosed.
Already-started forks survive snapshot Close. Manifest format/hash/commit-marker semantics
are unchanged. ConnectionInfo and DSN are immutable endpoint metadata, available
after Close; use Closed to inspect lifecycle state. Zero-value handles cannot start
operations; construct them through Start and Database.Snapshot.

There is one simultaneous SQL connection per DB. Close the database/sql pool before
WaitDisconnected and snapshot. DSN sets `interpolateParams=true` for driver-side
parameter interpolation through the supported text protocol. **This is not server
prepared-statement support**; explicit Prepare remains unsupported. Query timeout
remains instance-fatal. Signal handlers are not installed in the caller process.

## Opt-in integration verification (Task 4b)

Use the existing native bundle, without rebuilding or rearranging its artifacts:

```sh
MARIAMEM_NATIVE_DIR="$PWD/python/mariamem/_native" \
  go test -tags=integration ./tests/gointegration -v -count=1 -timeout=3m
```

The integration build tag keeps this test out of ordinary unit-test runs. An
explicit integration run requires `MARIAMEM_NATIVE_DIR`; a missing bundle is a
failure, not a silently skipped acceptance test. The module pins the test driver
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

This is integration correctness evidence, not a benchmark or clean macOS 12
platform acceptance. Prepared statements and query-timeout behavior are outside
this test's scope.

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
- `CANDIDATE.json`: input manifest/lock hashes and a snapshot of release reviews

The manifest retains its format and compatibility metadata, removes the unused
`mariamem-host` hash, and records exactly the three required artifact hashes.
The host executable is not included. `public_release_ready` is always false for
this candidate tool, even if the input manifest says otherwise.

For local evaluation, or once a future reviewed GitHub Release supplies these
assets, manually obtain the archive and its SHA256SUMS, then:

```sh
go get github.com/masahitojp/mariamem@<version-or-commit>
shasum -a 256 -c SHA256SUMS
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

**This is not cleared for public binary distribution.** WASIX linked runtime
source/licenses, Wasmer static Rust notices, and clean-platform acceptance remain
unresolved. Existing notices are preserved, not asserted complete. No source
archive is replaced by this bundle or by GitHub's default source zip. The existing
release review and corresponding-source requirements in [releasing](releasing.md)
still apply; candidate generation does not stage an approved Release asset.
