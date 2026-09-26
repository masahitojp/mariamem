# mariamem v0.1.0

Disposable, real MariaDB databases for Go and Python tests. The Python
distribution version is `0.1.0`.

## Highlights

- Go and Python lifecycle APIs with ordinary MySQL clients, InnoDB,
  transactions, Snapshot and independent Fork support.
- Native support for macOS 15+ / Apple Silicon arm64 and
  Ubuntu 24.04 LTS / x86_64. Ubuntu requires SSE2 and SSSE3; other Linux
  distributions, Linux arm64 and Windows are not supported.
- Actionable startup diagnostics preserve failure category, stage and cause,
  with expected platform/path/hash and recovery guidance. Runtime stderr is
  bounded; detected AOT/CPU incompatibility includes compatibility guidance.
- Multi-platform Release CI builds one common WASIX guest, accepts immutable
  platform artifacts separately and requires aggregate READY before publication.
  The release tag identifies the exact artifact build commit. Acceptance
  evidence stays external; retries verify source identity and artifact hashes.

## Connection and lifecycle semantics

The current guest supports 16 independent MariaDB sessions. Session variables,
temporary tables and transactions are isolated. Capacity exhaustion returns
recoverable MySQL error 1040; 16 is not a permanent API guarantee.
Normal Go connection pools do not require `SetMaxOpenConns(1)`.
Concurrent queries carry no performance-scaling guarantee.

Interrupted active SQL (timeout, cancellation or disconnect) invalidates the
whole Database, including its other connections. Close it and start or fork
another instance. Ordinary SQL errors and idle disconnects do not invalidate it.
Snapshot rejects unfinished transactions in any session; a successful Snapshot
consumes its source. Temporary snapshots are cleaned up by their owner;
explicit destinations are retained.

## Distribution and limitations

Go users supply the native bundle through `Options.NativeDir`; there is no
automatic runtime download. Python wheels include their runtime. MariaDB runs
as a Wasmer/WASIX guest rather than a SQL reimplementation. Server-side prepared
statements are not supported; Go DSNs use parameter interpolation.
Validation is scoped to Go 1.26 and Python 3.14. The 0.x API may change.

Assets include two native bundles, two Python wheels, platform-specific
corresponding-source archives and SHA256SUMS. Project code is GPL-2.0-only;
bundled dependencies retain their own licenses and notices. This release does
not upload to PyPI.
