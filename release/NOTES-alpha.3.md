# mariamem v0.1.0-alpha.3

This alpha provides disposable, real MariaDB databases for Go and Python tests.
The Python distribution version is `0.1.0a3`.

## Highlights

- One `Database` now accepts multiple simultaneous SQL connections. Normal Go
  connection-pool use no longer requires `SetMaxOpenConns(1)`.
- The current guest supports up to 16 independent MariaDB sessions. A 17th
  simultaneous connection receives recoverable MySQL error 1040; this capacity
  is a property of the current guest, not a permanent API guarantee.

## Connection and lifecycle semantics

Session variables, temporary tables, and transaction state are isolated between
connections. Different slots may execute queries concurrently, without a
parallel-performance guarantee. A slot is reused only after the guest confirms
session close.

An interrupted active SQL operation (timeout, cancellation, or disconnect)
still makes the whole `Database` unusable, including its other connections.
Close that instance and start or fork another. Snapshot rejects an unfinished
transaction in any session; a successful Snapshot consumes its source database.

## Development and distribution

Canonical local verification commands, baseline GitHub Actions, and a single
source for the Git/Go and Python release versions were added. Go users supply
the separate native bundle with `Options.NativeDir`; the Go module does not
download it. The Python wheel includes the native runtime. Both APIs use a real
MariaDB guest under Wasmer/WASIX.

Native support in this release is macOS 15+ on Apple Silicon (arm64). The
current validation scope is Go 1.26 and Python 3.14. Linux and Windows are not
supported by this release. This is an alpha; API and packaging may change.

The release assets include the native bundle, Python wheel, corresponding
source, and SHA256SUMS. Project code is GPL-2.0-only; bundled dependencies
retain their own licenses and notices.
