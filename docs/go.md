# Go API

**Direct-linked generated Go is the default v0.4.2 runtime.** Ordinary Go
usage needs no NativeDir, bundle cache/download or external Wasmer. Generated
Go is a normal module dependency/build input; WASM is a build intermediate.
Existing public APIs and cold Snapshot/Fork semantics are preserved.
See [architecture](v04-generated-go-architecture.md) and
[canonical measurements](../benchmarks/v04-integrated-candidate.md).

The public package is `mariamem` at the module root. The module requires Go
1.26.0+; canonical validation uses Go 1.26.8. Go 1.27.0/1.27.1 arm64 are
unsupported because of upstream compiler issue #81036; no local workaround is
used. An upstream-fixed toolchain has been verified. The v0.4.2 candidate is
prepared, not published. After publication:

```sh
mkdir mariamem-example
cd mariamem-example
go mod init example.com/mariamem-example
go get github.com/masahitojp/mariamem@v0.4.2
go get github.com/go-sql-driver/mysql
```

```go
db, err := mariamem.Start(ctx, mariamem.Options{})
```

Each DB has fresh execution/thread/TLS/FD state and private writable files.
Fork's prepared files use file-backed `MAP_PRIVATE` views: clean pages may be
OS-shared, while modified pages and filesystem metadata are child-private.
`Fork()` does not clone a running MariaDB or use Unix `fork()` for runtime
cloning. See [Copy-on-Write semantics](copy-on-write.md); sharing is not a public
memory-usage guarantee.
Normal Start does not decode/materialize a native image, spawn a guest process
or resolve a runtime bundle. Development/local replacement builds use the same
default. Once normal Go dependencies are available, startup needs no download.
Optional release audit assets are available separately:

```sh
gh release download v0.4.2 --repo masahitojp/mariamem \
  --pattern 'SHA256SUMS' --pattern 'mariamem-0.4.2-provenance.json'
```

## Legacy Wasmer compatibility override

Explicit `NativeDir` or `MARIAMEM_NATIVE_DIR` selects legacy Wasmer execution.
Use only a matching, independently verified legacy bundle. The normal v0.4.2
artifact contract does not include a new Wasmer/AOT bundle.

```go
db, err := mariamem.Start(ctx, mariamem.Options{
    NativeDir: "/path/to/verified/legacy/native",
})
```

A legacy bundle contains `manifest.json`, `wasmer-headless`, `mariamem.wasmu`
and `mariamem.wasmu.json`. Hashes and sidecar metadata remain verified on that
explicit path; its guest runs as a child process. The historical manual bundle
section below applies only to this fallback, not ordinary Go startup.

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
Set `MARIAMEM_NATIVE_DIR` only to exercise explicit legacy Wasmer acceptance.
The module pins the test driver `github.com/go-sql-driver/mysql` to v1.9.3;
applications register their own driver. See [development](development.md#local-verification).

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

For legacy evaluation, verify the matching previously published archive
against its published SHA256 and then extract it:

```sh
go get github.com/masahitojp/mariamem@<published-tag>
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

Legacy Ubuntu 24.04 x86_64 AOT bundles require a CPU with SSSE3. Compilation uses
a fixed SSE2+SSSE3 feature set and does not require AVX or AVX-512.

For startup failures, read the category/stage first, then the expected path,
platform or hash in the message. Reinstall the matching host-only Python wheel,
or, for explicit legacy execution, re-extract a complete matching native bundle;
do not mix files from different
bundles. Preserve executable permissions. An AOT/CPU compatibility error may
require a supported machine or VM exposing the required CPU features; the
Ubuntu 24.04 x86_64 bundle requires SSE2 and SSSE3. Startup failure does not
return a usable database; retry Start after correcting the reported input.
