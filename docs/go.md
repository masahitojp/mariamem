# Go API

These public usage instructions retain the current packaging contract. The
unpublished v0.4 artifact migration and NativeDir compatibility decision are in
[the integration audit](v04-integration-audit.md); no manual NativeDir requirement
is proposed for ordinary v0.4 usage.

The public package is `mariamem` at the module root. Go 1.26 or newer is
required; canonical release validation uses Go 1.26.8, not a broad language
version matrix. The v0.3.0 candidate is in preparation and is not published yet.

After publication, add the exact release to a fresh module:

```sh
mkdir mariamem-example
cd mariamem-example
go mod init example.com/mariamem-example
go get github.com/masahitojp/mariamem@v0.3.0
go get github.com/go-sql-driver/mysql
```

The ordinary API needs no native path:

```go
db, err := mariamem.Start(ctx, mariamem.Options{})
```

On first use, the tagged release downloads the native bundle for that exact
module version and supported platform. It verifies release metadata, SHA256,
manifest and package/input identity, then installs atomically in the user cache.
Later starts verify and reuse that cache, including offline. It never requests
`latest` or substitutes an older bundle. Candidate URLs will work after
v0.3.0 publication.

## Advanced, offline and development override

Explicit `NativeDir` and `MARIAMEM_NATIVE_DIR` override automatic resolution and
work without network access. Use them for CI, offline environments, and
unreleased development builds. Pseudo-version, local-replacement and untagged
builds require an explicitly matching bundle.

After v0.3.0 publication, download the platform-specific bundle for offline use:

```sh
# macOS 15+ arm64
gh release download v0.3.0 --repo masahitojp/mariamem \
  --pattern 'mariamem-native-darwin-arm64.tar.gz'
# Ubuntu 24.04 x86_64
gh release download v0.3.0 --repo masahitojp/mariamem \
  --pattern 'mariamem-native-ubuntu24.04-x86_64.tar.gz'
```

```go
db, err := mariamem.Start(ctx, mariamem.Options{
    NativeDir: "/path/to/native",
})
```

A manual bundle contains `manifest.json`, `wasmer-headless`, `mariamem.wasmu`,
`mariamem.wasmu.json`, and optionally `mariamem-host` (unused by Go). Required
files are checked against manifest hashes and sidecar metadata. No native binary
is committed to the Go module. Supported bundles are macOS 15+ arm64 and Ubuntu
24.04 LTS x86_64 (SSE2 + SSSE3); other distributions and architectures are not
supported.

The host runs in the Go caller; Wasmer/MariaDB remains a child process.

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
capacity (16 for the current native bundle, not a permanent API guarantee).
Each connection has its own guest session and transaction state. A connection
beyond capacity receives MySQL error 1040; closing a client releases its slot
after guest cleanup. Different sessions may have queries in flight together,
without a throughput guarantee. Close the database/sql pool before
WaitDisconnected when taking a snapshot. DSN sets `interpolateParams=true` for
driver-side parameter interpolation through the supported text protocol. This
is not server prepared-statement support; explicit Prepare remains unsupported.

A host QueryTimeout or client context cancellation while SQL runs terminates the
guest and invalidates that database instance. A client disconnect during SQL is
also fatal; a normal disconnect while idle leaves the DB usable. Do not retry
SQL against an invalidated instance: close it and start or fork another.
`db.Closed()` becomes true, and `db.Err()` reports ErrUnusable with the
underlying cause. For a host timeout, `errors.Is(db.Err(), context.DeadlineExceeded)`
is true. A caller context deadline or explicit cancellation is returned by the
MySQL driver as the caller's context error; the host sees the connection loss
and terminates the guest. Snapshot and WaitDisconnected reject invalidated
instances; Close remains idempotent and releases the guest process and temporary
files. Signal handlers are not installed in the caller process.

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
covers query interruption and multiple independent SQL clients. Separate clean
release acceptance covers both supported platforms. Server-side prepared
statements remain unsupported.
For when to run the other local checks, see [development](development.md#local-verification).

## Manual native bundle (local candidate)

Generate a Go bundle from the existing wheel staging artifacts; this does not
rebuild the guest, alter the wheel, download binaries, or publish a release:

The commands/layout below show the macOS bundle. On Ubuntu use the same tooling
with the Ubuntu native directory/archive; its manifest records Ubuntu 24.04,
x86_64, SSE2 + SSSE3 and the verified ELF dependencies instead of Mach-O minimums.

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

For local evaluation, or when using the v0.3.0 published archive, verify it
against its published SHA256 and then extract it:

```sh
go get github.com/masahitojp/mariamem@v0.3.0
shasum -a 256 mariamem-native-darwin-arm64.tar.gz
tar -xzf mariamem-native-darwin-arm64.tar.gz
export MARIAMEM_NATIVE_DIR="$PWD/mariamem-native-darwin-arm64"
```

To force use of this local bundle, pass its directory explicitly or set the
supported environment override:

```go
db, err := mariamem.Start(ctx, mariamem.Options{
    NativeDir: os.Getenv("MARIAMEM_NATIVE_DIR"),
})
```

The locally generated archive remains a candidate with
`public_release_ready=false` in its metadata; this packaging command does not
publish or stage it as an approved Release asset. Release CI must obtain clean
platform evidence for its exact hash and verify source/runtime notices. Tracked
`release/review.json` describes historical artifacts, not a new candidate's
approval. The native archive is separate from the wheel and corresponding-source
archive checked by the [release guard](releasing.md).

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

Ubuntu 24.04 x86_64 candidates require a CPU with SSSE3. AOT compilation uses
a fixed SSE2+SSSE3 feature set and does not require AVX or AVX-512.

For startup failures, read the category/stage first, then the expected path,
platform or hash in the message. Re-extract a complete matching native bundle
(or reinstall the matching Python wheel); do not mix files from different
bundles. Preserve executable permissions. An AOT/CPU compatibility error may
require a supported machine or VM exposing the required CPU features; the
Ubuntu 24.04 x86_64 bundle requires SSE2 and SSSE3. Startup failure does not
return a usable database; retry Start after correcting the reported input.
