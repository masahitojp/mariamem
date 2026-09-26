# mariamem v0.1.0-alpha.4

This alpha provides disposable, real MariaDB databases for Go and Python tests.
The Python distribution version is `0.1.0a4`.

## Highlights

Alpha.4 exercises the new end-to-end release path, rather than introducing a
new database feature. CI builds an exact remote source commit, accepts the
immutable artifacts on a separate clean macOS runner, checks release readiness,
and publishes those exact bytes. The release tag identifies the artifact build
commit; acceptance evidence remains external to candidate artifacts.

The canonical guest build now uses Linux x86_64 for WASIX WASM, followed by
macOS arm64 Wasmer AOT compilation and packaging. Docker and Tart are not
required by this release path. Release CI supports acceptance-only and
guard-only retries with source identity and hash verification. Release-facing
version consistency is mechanically checked.

## Connection and lifecycle semantics

Existing multi-client behavior is unchanged. The current guest supports up to
16 independent MariaDB sessions, with recoverable MySQL error 1040 at capacity.
This capacity is not a permanent API guarantee. Session variables, temporary
tables, and transactions are isolated; normal Go connection-pool use does not
require `SetMaxOpenConns(1)`. Concurrent queries carry no performance-scaling
guarantee.

Interrupted active SQL (timeout, cancellation, or disconnect) makes the entire
`Database` unusable, including other connections. Close it and start or fork
another instance. Snapshot rejects an unfinished transaction in any session;
a successful Snapshot consumes its source database.

## Platform and distribution

Native support remains macOS 15+ on Apple Silicon (arm64), with validation
scoped to Go 1.26 and Python 3.14. The Linux guest build does not provide Linux
runtime support. Linux and Windows are not supported by this release.

Go users supply the native bundle through `Options.NativeDir`; there is no
automatic download. The Python wheel includes its runtime. Both APIs run a
real MariaDB guest under Wasmer/WASIX. This is an alpha; APIs and packaging may
change.

Assets include the native bundle, Python wheel, corresponding-source archive,
and SHA256SUMS. Project code is GPL-2.0-only; bundled dependencies retain their
own licenses and notices. This release does not publish to PyPI.
