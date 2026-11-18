# mariamem v0.7.0

mariamem gives Go and Python tests disposable MariaDB databases. This release
improves startup and shutdown for test suites that repeatedly fork a prepared
database. The Python distribution version is `0.7.0`.

## Go database cleanup

`Database.CloseAsync(ctx)` lets Go callers wait for the database to stop, then
track resource cleanup through the returned handle. This can overlap cleanup
with other work. Fork capacity is returned after resource release is confirmed.
`Database.Close()` remains the synchronous API.

## Snapshot and Fork performance

- Instances reuse a process-local immutable initial memory image. Startup also
  reuses prepared SQL lexer and collation data.
- InnoDB avoids redundant buffer-pool page initialization and loads buffer-pool
  pages on demand. The first scan can take longer when it has to load pages.
- Ordinary disposal uses a faster InnoDB shutdown mode. Snapshot creation uses
  a clean shutdown to prepare the image for later forks.
- Snapshot creation still consumes the source database. Each fork starts from
  the captured state and can be modified independently.

## SQL execution

- The generated runtime handles prepared-statement result rows through a more
  direct path and avoids rescanning rows to determine which fields are present.
- The WebAssembly memory bounds trap path does less work in generated Go while
  keeping the existing bounds checks.
- InnoDB full-page CRC32C processing is faster and retains checksum validation.

## Installation and release assets

Go requires Go 1.26.0 or later. Python requires Python 3.11 or later. This
release targets macOS 15+ arm64 and Ubuntu 24.04 x86_64.

The host executable bundled in each release wheel is stripped to reduce
download size. Release assets include corresponding source, provenance,
license notices, and checksums.
