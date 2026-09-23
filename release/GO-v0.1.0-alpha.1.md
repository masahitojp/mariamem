# mariamem v0.1.0-alpha.1 — source-only Go alpha

## What this is

mariamem makes real MariaDB disposable for application tests. This is the first
versioned alpha of the public Go API at `github.com/masahitojp/mariamem`.

The current runtime target is darwin/arm64. The Go host runs inside the caller;
the real MariaDB guest runs in a separate Wasmer/WASIX process. Cold snapshots
and independent forks let tests reuse a seeded database without sharing changes.

## What works

Validated with the existing native bundle on the development Mac:

- Start / idempotent Close and ordinary `database/sql` connections using go-sql-driver/mysql.
- Real MariaDB 13.1, InnoDB tables, INSERT/SELECT and transactions.
- Transaction-active snapshot rejection and WaitDisconnected after closing the SQL pool.
- Snapshot success closes its source Database.
- Concurrent, independent Fork from the same snapshot; Close waits for admitted startups.
- Temporary snapshots are owned and cleaned up by their handles; explicit destinations are retained.

## Getting the Go source

Requires Go 1.26 or newer:

```sh
go get github.com/masahitojp/mariamem@v0.1.0-alpha.1
```

```go
import "github.com/masahitojp/mariamem"

// Inside a function, with an existing local native bundle:
db, err := mariamem.Start(ctx, mariamem.Options{
    NativeDir: "/path/to/native",
})
```

See the [Go guide](https://github.com/masahitojp/mariamem/blob/v0.1.0-alpha.1/docs/go.md)
for lifecycle usage and native bundle requirements. Fetching the Go module alone
does not supply a runnable database runtime.

## Alpha limitations

- `Options.NativeDir` is required. Native runtime binaries are **not distributed in this source-only release**.
- No artifact auto-download. Users need a separately prepared local native bundle.
- One simultaneous SQL connection per DB at the host level; use `SetMaxOpenConns(1)`.
- Prepared statements are unsupported. DSN sets `interpolateParams=true` for client-side parameter interpolation through the text protocol.
- Query timeout is currently instance-fatal.
- Snapshot is a cold filesystem snapshot, not a live/COW snapshot. Close the SQL pool and call WaitDisconnected before normal snapshot creation.
- macOS 12 arm64 remains a candidate deployment target; clean-platform acceptance is incomplete.
- This is an unstable alpha; API compatibility is not guaranteed.

## Release status

**Source-only alpha. No native bundle or wheel is attached. No Python/PyPI release
is made by this tag.** Python `0.1.0a1` remains independent and awaits PyPI account
recovery.

Binary release/license/platform review is incomplete. In particular, WASIX linked
runtime corresponding source/licenses, Wasmer static Rust dependency notices,
and clean-platform acceptance remain unresolved. `guest_source`, `runtime_notices`,
`platform_acceptance`, and candidate `public_release_ready` remain false.

GitHub's automatically generated source archives contain this repository; they
are not asserted to be the complete corresponding-source set for a binary release.
The native packaging tooling produces local evaluation candidates only. This
source tag does not approve those candidates for public distribution.

Project code is GPL-2.0-only; upstream components retain their original licenses
and notices. See LICENSE, NOTICE and THIRD_PARTY_LICENSES in the tagged sources.
