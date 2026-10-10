# Go toolchain compatibility

The module minimum remains **Go 1.26.0**. `go-sql-driver/mysql v1.9.3`
is a development/test client dependency; the production library does not import
it or require it to serve the MySQL wire protocol. Applications choose their
own compatible client driver. v0.4.6 made no dependency upgrade.

External-module consumers passed on **macOS arm64** using Go **1.26.8,
1.27.0, 1.27.1 and 1.27.2**, with `GOTOOLCHAIN=local` and actual compiler versions
recorded. Coverage included import/build, Start/SQL/Close, Snapshot/Fork,
multiple connections, commit/rollback and cleanup. These are accepted product
results.

**Ubuntu 24.04 x86_64 / Go 1.27.2** passed the same bounded external consumer
checks, including the new Go `LoadSnapshot` lifecycle. Actual compiler:
`go version go1.27.2 linux/amd64`, `GOTOOLCHAIN=local`, `CGO_ENABLED=1`.
This was real execution under Docker Desktop Rosetta x86_64 emulation on an
arm64 Mac, not cross-compilation or native x86_64 release qualification.
Cleanup returned goroutines 2 → 2 and left no runtime temporary entries.
Final v0.4.6 artifact qualification and public-tag smoke passed on native
macOS15 arm64 and Ubuntu24.04 x86_64 using Go1.26.8 in
[Release CI](https://github.com/masahitojp/mariamem/actions/runs/38040418075),
source `b56be17206b6beef18f55c8ea39b254638da8590`. This does not extend native
release qualification to Go1.27.2 on Ubuntu.

These checks use an exact-source private module-proxy fixture without a Go
`replace` directive. The completed public-tag/artifact release qualification
is separate evidence. Supported platforms and release evidence are separate from the
minimum language directive. No generated/runtime workaround is included.

The new `LoadSnapshot` API also passed focused macOS consumer/lifecycle checks
with Go 1.26.8 and 1.27.1. See the [v0.4.6 review](reviews/v046-human-review.md)
for exact scope, Ubuntu evidence and release gates.
