# mariamem v0.6.0 — Prepared tests, E2E and bounded wire support

## Prepared application tests and E2E

- Python's pytest entry prepares one worker-local baseline and gives each test
  an independent child. Opt-in `shadow_maria` routes explicitly enrolled
  application connections; migration/seed receives explicit DB settings.
  Preparation-time automatic routing is not provided.
- New public `mariamem.PrepareCommand(argv, *, timeout=120, cwd=None, env=None)`
  adds a declarative command beside None and a callback. Existing callback return
  values remain ignored; unknown inputs remain pytest UsageError. The environment
  overlays the parent environment, with actual connection JSON supplied through
  the reserved variable. This is not hermetic or shell-interpolated execution.
- Command stdout/stderr are drained continuously, retaining a trailing 16 KiB
  per stream with truncation metadata. Timeout/interrupt attempts bounded owned
  process-group termination and reaping. Diagnostics quote application output
  without inferring its root cause.
- **Behavior change:** child or routing cleanup failure stops later dependent
  tests in the same worker. Ordinary assertion failure with successful cleanup
  allows the next independent child; other xdist workers remain independent.
  Explicit fixture overrides own their lifecycle boundary.
- Go's `mariamemtest` owns preparation, capture, bounded child pools and cleanup;
  the callback still supplies migration/seed and its success signal.
- Live endpoints support sequential E2E through Python
  `mariamem.e2e.BrowserEntry` and Go `mariamemtest.NewHTTP`;
  call `fixture.Case(t)` on the returned `*mariamemtest.HTTPFixture`.
  Entries own reset/admission/cleanup sequencing; application hooks own readiness,
  quiescence, physical SQL/job retirement and stop/reap. Independent owners can
  run in parallel. Parallel cases sharing one Live, session continuity,
  automatic pool retirement, arbitrary delayed-job fencing and non-cooperative
  shutdown are outside this contract.

See [Python](../docs/python.md), [Go fixtures](../docs/go-prepared-fixture.md),
[routing](../docs/connection-routing.md), the [complete shadow_maria example](../docs/python.md#existing-application-connections-shadow_maria),
and [owned E2E examples](../docs/examples/e2e_owned/README.md).

## SQL and bounded dump input

Stored procedures/functions and real server-side prepared execution are supported
within the declared client profile. Routine DEFINER/SQL SECURITY metadata is
retained; the local skip-grant-tables endpoint does not enforce account privileges.
Scheduled events and packages/package bodies remain outside support.

Python `mariamem.import_dump` with the optional `dump` extra accepts only the
documented MariaDB 12.3.3 producer profile, with finite framing/input bounds,
explicit errors and failed-source discard. It is not a general SQL-script or
MySQL/legacy application importer. Views, triggers, events, other producers and
a Go dump API remain outside the profile. `DELIMITER` is a client directive,
not server SQL. See [the format contract](../docs/importing-dump.md).

Internal MariaDB status is validated as an unsigned 32-bit value and projected
to the low 16 protocol flag bits; engine-internal bit 16 does not cross the wire.

The wire contract fixes the supported command/capability inventory and retains
native/guest and declared-client-path evidence with named exceptions. Uncaptured
per-entry paths remain UNVERIFIED; acceptance does not mean every path has paired
native comparison or packet capture. TLS/compression, alternate authentication,
LOCAL INFILE, administrative commands, binlog/replication, COM_RESET_CONNECTION,
server-side cursors, packet continuation and capacity increases remain outside
the declared profile. Live Reset is not COM_RESET_CONNECTION. A concrete required
sequence or discrepancy reopens a bounded probe. Release CI adds no wire coverage.
See [the exact wire contract](../docs/decisions/v060-wire-contract.md).

## Compatibility and accepted limitations

- **Python now requires 3.11 or later; 3.9/3.10 are dropped.** Go minimum remains
  1.26.0; the selected build toolchain is 1.26.10. Go 1.27.3 forward compatibility
  remains a final Qualification check, not a new PASS asserted by these notes.
- Supported hosts remain macOS 15+ arm64 and Ubuntu 24.04 x86_64. Linux wheel
  testing is not a manylinux compatibility claim. Distribution remains GitHub
  Release wheels, Go source, corresponding source, provenance and SHA256SUMS;
  PyPI publication remains unavailable.
- Oracle mysql-connector-python 26.7.0 has two named accepted consumer exceptions:
  the tested multi-result prepared CALL can fail during traversal and leave
  the connection unusable; and macOS C/default can truncate an untyped NUL-containing character
  projection. Typed binary columns preserve those bytes. These cases do not
  make arbitrary connection errors recoverable or imply general driver support.
  Separately, native-matched macOS C-extension prepared syntax errors can report
  `2006/HY000` instead of raw `1064/42000` despite successful subsequent SQL.
  This is the native-parity error-presentation disposition, not a third
  exception under the [CALL/NUL decision](../docs/decisions/prepared-consumer-exceptions.md).
  [Exact modes and boundaries](../docs/python.md) remain authoritative.
  MariaDB Connector/Python 1.1.14 passes the two CALL/NUL cases in the fixed
  supported-host profiles; this is not a repair to Oracle's connector.
- Ubuntu's additional explicit C-extension mode may be unavailable and is an
  allowed SKIP, not a compatibility PASS. Required default/pure modes retain
  their own evidence. Homebrew Python3.14/OpenSSL4 can prevent Connector/Python
  26.7.0 import; OpenSSL3 CI does not qualify that local environment. No driver
  mode or SSL constants are silently substituted.
- The ordinary [Django standard-runner recipe](../docs/django-testing.md) is supported
  within its fixed Django5.2.8/mysqlclient2.2.7/pytest-django4.12.0 profile
  (with pytest9.0.2). Additional D1 prepared-Snapshot restoration is
  deferred from 0.6.0 for consideration in 0.6.1, not promised for that version. Fixed dbt workload
  evidence is not general dbt or dbt unit-test support.
- Detailed resource characterization/tuning belongs to 0.7.x; no throughput,
  peak-memory, cold-setup or larger-capacity guarantee is added. Cooperative
  ownership/cleanup remains required. Existing shared-memory/race and forced
  query-timeout containment limits remain as documented in [releasing](../docs/releasing.md).

## Validation boundary

P1/G1/EP1/EG1 adoption, the explicit D1 disposition and the fixed dbt replay
are complete under their source-bound receipts. The #24 source-only panic
inventory correction is integrated; it is not runtime or general WASIX proof.
No historical receipt is relabelled onto a different release SHA.

Final exact-version acceptance must succeed before publication.
Release CI owns both-platform build/qualification, declared feature acceptance,
guard evaluation and, only when authorized with operation=release, publication
and public smoke. Existing component or daily CI success is not release READY.
