# mariamem v0.7.1

mariamem gives Go and Python tests disposable MariaDB databases. This release
updates the embedded engine to MariaDB 12.3.4 on the native-wire runtime,
adds non-consuming snapshots (`KeepDatabase` / `keep_database=True`), expands
PyPI wheel distribution to six-target builds, and fixes snapshot cancellation
and failure-cleanup progress bugs. The Python distribution version is `0.7.1`.

## Embedded MariaDB 12.3.4 and native-wire runtime

- Updated the embedded generated-Go guest from MariaDB 12.3.3 to MariaDB
  12.3.4 (`#227`).
- Adopted the `internal/nativewire` native-wire host and guest path, retiring
  the legacy `./internal/guest`, `./internal/mysqlwire`, and
  `./internal/preparedproto` packages (`#241`, `#251`).
- Switched guest control threads to an event-driven writer/monitor and lazy
  killer path (`#265`), preserved atomic fences during Binaryen optimization
  (`#262`), and moved linked guest I/O to bounded in-process pipes (`#235`).
- Advertised `CLIENT_FOUND_ROWS` during the MySQL handshake and updated the Go
  MySQL driver dependency to `github.com/go-sql-driver/mysql v1.10.1` (`#230`).

## Non-consuming snapshots and snapshot/lifecycle reliability

- Added opt-in non-consuming snapshots in Go (`SnapshotOptions.KeepDatabase`,
  `#225`) and Python (`db.snapshot(keep_database=True)`, `#226`), preserving
  the source database and idle sessions after capture.
- Allowed waiting `Database.Snapshot` callers to return on `ctx` cancellation
  or deadline while a leading snapshot is in flight (`#266`).
- Returned detected `Snapshot` failures before waiting for guest disposal while
  retaining parent fork-limit ownership until disposal completes (`#268`), and
  clarified busy snapshot errors (`#267`).
- Woke pending Python submission waiters when the managed host exits (`#262`).

## Python routing and compatibility

- Added `mysqlclient` (`MySQLdb`) and SQLAlchemy `mysql+mysqldb` routing
  support (`#264`).
- Relaxed optional driver and SQLAlchemy dependency pins in `extras_require`
  to compatibility ranges (`#263`).

## Installation and release assets

Go requires Go 1.26.0 or later (release builds use Go 1.26.11). Python requires
Python 3.11 or later.

This release uses the six-target release gate by default (`#245`, `#250`):

- **PyPI wheels**: macOS 15+ arm64 (`macosx_15_0_arm64`), portable Linux
  x86_64 and aarch64 (`manylinux_2_28` / `musllinux_1_2`), and Windows build
  22000+ x86_64 and arm64 (`win_amd64` / `win_arm64`).
- **GitHub Release assets**: all five PyPI wheels, the Ubuntu 24.04 x86_64
  wheel (`linux_x86_64`), corresponding source, provenance, license notices,
  and `SHA256SUMS`.
