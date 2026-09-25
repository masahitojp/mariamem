mariamem v0.1.0-alpha.2 is an early Go and Python alpha for disposable MariaDB tests.
The Python distribution version is 0.1.0a2.

- Start a real MariaDB from the Go package using `mariamem.Start` and connect
  through `database/sql` with an ordinary MySQL driver.
- Start a real MariaDB with `with mariamem.start() as db:`.
- Connect with PyMySQL using `db.connection_info()`.
- Use the bundled pytest fixtures and cold snapshot/fork API for isolated tests.
- The platform wheel includes the Go host, Wasmer headless, and MariaDB guest.
- Go users provide the separate native bundle through `Options.NativeDir`; the
  Go module does not download runtime binaries.

Candidate target: macOS 15+ arm64. The native candidate passed clean macOS 15.7.7
arm64 acceptance; the Python wheel is accepted separately after each rebuild.
One simultaneous SQL connection per DB. Text protocol only; no prepared statements.
Python starts a Go host process; the Go API hosts it in the caller. Both run the
Wasmer/MariaDB guest as a child process. Snapshot creation stops its source DB
and writes a cold filesystem image.

The guest is derived from shyim/lite4mariadb and MariaDB Server. Project code is
GPL-2.0-only; bundled dependencies retain their original licenses.

This file is a release draft. Binary publication requires the checks documented
in docs/releasing.md and a complete corresponding-source asset.
