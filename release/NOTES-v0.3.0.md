# mariamem v0.3.0

The v0.3.0 release focuses on ordinary ORM use and disposable database
isolation. It remains a stable 0.x release; public APIs may change before 1.0.

## SQLAlchemy and GORM

The Go and Python APIs now have dogfood coverage with conventional application
patterns. The SQLAlchemy User/Address workload covers relationships, normal
sessions and pools, CRUD, commit, rollback and constraint errors. GORM coverage
includes CRUD, relationships, transactions, default connection pools and
repeated `AutoMigrate`.

Both frameworks can use a fresh mariamem database per test. A test may commit
data and finish without reset or cleanup SQL; the next test receives an
independent database and cannot observe that committed state. Database, snapshot
and client handles still need their normal resource cleanup.

Protocol compatibility includes `CLIENT_FOUND_ROWS`: an unchanged UPDATE
reports one matched row when the client requests that capability and zero under
ordinary changed-row semantics. MariaDB schema discovery also supports GORM's
introspection and repeated migration checks.

## Go setup

Tagged Go releases support the ordinary call:

```go
db, err := mariamem.Start(ctx, mariamem.Options{})
```

On first use, mariamem resolves the native bundle for the exact module tag and
platform, downloads and verifies its checksums and metadata, and installs it
atomically in the user cache. Later starts verify and reuse the cache, including
offline. `NativeDir` and `MARIAMEM_NATIVE_DIR` remain available for offline,
CI and advanced use. Development, pseudo-version and local-replacement builds
require a matching explicit bundle; they do not fall back to an unrelated
release.

Python wheels include the required host, runtime and guest artifacts. PyPI
publication is temporarily unavailable; use the platform-specific wheels from
the GitHub Release. PyPI remains a planned distribution channel.

## Tested platforms

Clean acceptance covers macOS 15+ arm64 and Ubuntu 24.04 LTS x86_64. The Ubuntu
native bundle requires SSE2 and SSSE3. This release makes no generic Linux,
manylinux, Linux arm64, macOS Intel or Windows support claim.

The SQLAlchemy and GORM dogfood suites passed on both supported platforms.
Release CI also checks each candidate's packaged native bundle and wheel with
focused Go zero-setup, GORM schema-discovery, and installed-wheel SQLAlchemy
smokes. These results describe the tested platforms and framework versions;
they are not compatibility guarantees for every ORM version or migration
workload.
