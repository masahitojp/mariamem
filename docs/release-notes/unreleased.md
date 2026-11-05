# mariamem v0.6.1 — release-notes draft

This file is the sole staging content source for future release notes.
The Human requested a 0.6.1 draft; the text below summarizes changes already
merged after v0.6.0. It does not approve publication. Version metadata and
published installation commands remain unchanged.

Content basis (2026-11-04): main source_commit
`bc00b8e66e5fd57bc9b2127001faf8e05952b417`, compared with v0.6.0
source_commit `b3b3b46a8807482ad3f96725af86e031fe369b01`
(tag_object_sha `b57183b08d48884840111e8b53daa500734337f0`).
This is a content reference, not final-version artifact qualification.

## Prepared Django tests

- New opt-in `mariamem.django.prepared_database`, `PreparedDiscoverRunner`,
  `PreparedTestCase` / `PreparedTransactionTestCase` and
  `mariamem.django.pytest_plugin` prepare migrated/seeded state and give each
  test an independent Fork of its prepared class state. Committed writes, DDL
  and ordinary assertion failures do not become the next test's initial state.
  Install the optional `django` or `django-pytest` extra and explicitly select
  this entry. The ordinary standard-runner recipe remains available.
- `prepared_database()` is declarative. Settings import, check/shell, discovery,
  collection-only and database-free suites do not acquire a host. SQL outside
  the owned test lifecycle is refused before connecting. Preparation/retirement
  failures retain their errors; unconfirmed cleanup stops dependent admission.
- Local pytest-xdist workers are supported with explicit `-n N` and `load` or
  `loadscope`. Each DB-using worker owns its own host and migration/seed baseline;
  controller, idle and DB-free workers acquire none. A replacement worker
  prepares a fresh lineage. Hard worker death cannot run Python temporary-file
  finalizers, so job scratch cleanup remains necessary.
- The extras accept Django 5.2 LTS, 6.0 and 6.1 (`Django>=5.2.8,<6.2`).
  Django 6 requires Python 3.12+; Python 3.11 continues with Django 5.2.
  Maintained Release profiles are Python 3.11 / Django 5.2 and
  Python 3.14 / latest Django 6.1.

This entry supports one default database alias and explicit prepared classes.
There is no class-wide atomic: class preparation is committed and `on_commit()`
may run immediately there; per-test TestCase atomics remain. Do not combine
prepared Django with routing/`shadow_maria` ownership in one invocation, or mix
ordinary database test classes/function-style `django_db` tests into the prepared
run. Unused routing bindings now report `UnusedRoutingWarning` after successful
cleanup. Remote workers, automatic worker counts, other xdist schedulers and
Django `--parallel` remain outside the accepted scope.
See the [prepared Django guide](../django-prepared.md) for setup and worker sizing.

## Finite Snapshot/Fork capacity

**Behavior change:** omitted Snapshot Fork limits now resolve to a finite,
memory-based capacity. Full capacity waits before another child starts;
reserved, starting and cleanup-pending children retain their slots until actual
retirement. Capacity is per Snapshot, not a process-wide or machine-wide limit.

- Go adds `SnapshotOptions.MaxForks` and read-only `Snapshot.MaxForks()`.
  Fork waits honor the caller's context. Closing the parent wakes waiters
  without closing successful children. Use keyed `SnapshotOptions` and
  `HTTPConfig` literals: adding fields breaks old positional literals.
- Python adds `snapshot(max_forks=...)`, read-only `max_forks`,
  `fork(timeout=...)` and `Database(snapshot=..., fork_timeout=...)`.
  Cross-host children keep their origin slot through disposal. Supplied pytest
  fixtures add `mariamem_max_forks` (default `None`, automatic) and
  `mariamem_fork_timeout` (default 30 seconds). Acquisition failure stops
  dependent admission in that worker; ordinary assertions retain their behavior.
- Go Live requires at least two slots and reserves replacement capacity before
  draining. A full parent returns busy while preserving the current generation.
  Go test helpers retain their default of two; `HTTPConfig` exposes an override.
  Python E2E `Config.max_forks` reaches its Live baseline and rejects one before
  preparation. Prepared Django forwards `max_forks` / `fork_timeout` to its
  run/class baselines and child acquisitions, including final DROP cleanup.
- Capacity diagnostics include the resolved limit and observed occupancy
  (or explicitly unknown), with guidance to close children or increase the cap.

Nested acquisition while holding every slot can wait indefinitely. Release a
child first or bound the wait with a Go context / Python timeout. Automatic
sizing is a memory heuristic, not an OOM guarantee or a CPU/latency optimum.
Hidden/unreadable cgroup limits can cause host-RAM sizing to over-admit; configure
explicit caps and choose the total worker count separately. Independent root
`Start` / `start()` calls are outside these caps.

Failed capture cleanup has an accepted permanent failure path: if a newly owned
Snapshot also fails Close, the shared host latches `captureDebt`, retains its
origin slot and stops parent admission even after runtime disposal. Cleanup
retry or Live Reset cannot clear it; safely close remaining owners and prepare
a fresh lineage. This differs from retryable child cleanup debt.
See [Go](../go.md), [Python](../python.md) and the
[adoption decision](../decisions/issue53-fork-limit-adoption.md).
PR #85 is merged; older candidate records describing integration as pending
retain their historical context.

## Fixes

- Local test endpoints accept arbitrary handshake usernames and password
  responses, allowing applications to retain placeholder test credentials.
  Protocol validation remains; all sessions use the existing embedded guest
  privilege context. This adds no authentication, account management or
  credential isolation. See [connection behavior](../python.md).
- `import_dump` now rejects statements above the existing 1 MiB text SQL budget
  during preflight, before connecting, instead of advertising a 4 MiB reader
  limit that execution could not accept. The limit counts transmitted UTF-8
  bytes, including leading whitespace/comments. Source-location diagnostics
  and failed-source discard remain; file/count limits stay 16 MiB / 10,000.
  See the [dump format contract](../importing-dump.md).
- The WASM buffer-pool allocator avoids redundant allocation/zeroing work by
  passing its existing extent alignment to the internal allocator. Zero-filled
  memory and allocation/free semantics remain. A small retained-RSS saving was
  observed; CPU/batch speedup is inconclusive and queue latency is unmeasured.
  See the [bounded allocation decision](../decisions/buffer-pool-alignment.md).
- Host WASI writes propagate zero-byte write errors, including broken pipes,
  and preserve actual short-write progress. This fixes the tested interrupted
  guest cleanup stall; the accepted prepared CALL observations remain unchanged.

## Compatibility and validation

MariaDB remains 12.3.3. Python minimum remains 3.11 and Go minimum remains 1.26.0.
Supported hosts remain macOS 15+ arm64 and Ubuntu 24.04 x86_64. Distribution
continues through GitHub Release assets; no PyPI publication is added.
The [v0.6.0 wire/connector limitations](../../release/NOTES-v0.6.0.md)
continue to apply. No general SQL compatibility or throughput/peak-memory
improvement is claimed.

Installed prepared-Django and local-xdist acceptance passed on both supported
OSes with Python 3.11/3.14 under their
[Django](../reviews/d1-release-41327745652/README.md) and
[xdist](../reviews/d1-xdist-adoption.md) receipts. The finite-Fork matrix passed
on exact candidate `cddd8dcbd6d664171907ffc1769b83e472640875`; see the
[source-bound receipt](../reviews/issue53-fork-limit-evidence/ci-41778273108/README.md).
These results are not relabelled as acceptance of this draft or the final 0.6.1
source. CI ownership/cache consolidation after 0.6.0 is maintenance, not added
product compatibility evidence.

Before publication, finalize the selected 0.6.1 source and notes, then submit
that exact candidate to Release CI for qualification and the authorized
operation. No release workflow has been submitted by this drafting task.

## Historical 0.6.0 drafting reference

The text below preserves the pre-publication drafting context. Its pending
statements describe that historical checkpoint, not today's published release
or the new Django candidate above. Do not carry it forward as new release scope.

### mariamem 0.6.0 — original draft

Reviewed content basis: main `1c3a7945587dd9862d6d222dc9193a069d51f603`
(including PR50), with this PR's documentation clarifications applied. This is a
content reference, not an assertion that the draft tree equals that main tree.
This is not a published release, final-candidate qualification, or publication
approval. Version metadata and install commands remain at published 0.5.3.
This file is the sole staging content source for 0.6.0 release notes.
During authorized version preparation, transfer the reviewed text to
`release/NOTES-v0.6.0.md` and update the final version/installation examples.
The release workflow does not consume this draft automatically.

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

See [Python](../python.md), [Go fixtures](../go-prepared-fixture.md),
[routing](../connection-routing.md), the [complete shadow_maria example](../python.md#existing-application-connections-shadow_maria),
and [owned E2E examples](../examples/e2e_owned/README.md).

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
not server SQL. See [the format contract](../importing-dump.md).

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
See [the exact wire contract](../decisions/v060-wire-contract.md).

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
  exception under the [CALL/NUL decision](../decisions/prepared-consumer-exceptions.md).
  [Exact modes and boundaries](../python.md) remain authoritative.
  MariaDB Connector/Python 1.1.14 passes the two CALL/NUL cases in the fixed
  supported-host profiles; this is not a repair to Oracle's connector.
- Ubuntu's additional explicit C-extension mode may be unavailable and is an
  allowed SKIP, not a compatibility PASS. Required default/pure modes retain
  their own evidence. Homebrew Python3.14/OpenSSL4 can prevent Connector/Python
  26.7.0 import; OpenSSL3 CI does not qualify that local environment. No driver
  mode or SSL constants are silently substituted.
- The ordinary [Django standard-runner recipe](../django-testing.md) is supported
  within its fixed Django5.2.8/mysqlclient2.2.7/pytest-django4.12.0 profile
  (with pytest9.0.2). Additional D1 prepared-Snapshot restoration is
  deferred from 0.6.0 for consideration in 0.6.1, not promised for that version. Fixed dbt workload
  evidence is not general dbt or dbt unit-test support.
- Detailed resource characterization/tuning belongs to 0.7.x; no throughput,
  peak-memory, cold-setup or larger-capacity guarantee is added. Cooperative
  ownership/cleanup remains required. Existing shared-memory/race and forced
  query-timeout containment limits remain as documented in [releasing](../releasing.md).

## Validation boundary

P1/G1/EP1/EG1 adoption, the explicit D1 disposition and the fixed dbt replay
are complete under their source-bound receipts. The #24 source-only panic
inventory correction is integrated; it is not runtime or general WASIX proof.
No historical receipt is relabelled onto this draft or a future release SHA.

**Final exact-version candidate acceptance and publication are still pending.**
Release CI owns both-platform build/qualification, declared feature acceptance,
guard evaluation and, only when authorized with operation=release, publication
and public smoke. Existing component or daily CI success is not release READY.


## Post-v0.6.1 staging — unreleased

The original 0.6.1 draft above retains its source/evidence context. This section
is later staging content and is not part of release/NOTES-v0.6.1.md.

- The local MySQL endpoint accepts bounded input pipelining while keeping SQL
  execution and responses serial. At most 1,048,581 pending bytes are retained per
  physical connection; overflow terminates that database instance. Disconnect,
  deadline and owner-stop behavior remain in place. See the
  [protocol limits](../mysql-protocol.md). No Node SDK or general ORM support
  declaration is added.

- Go callers can explicitly select same-process MySQL wire connections using
  `Database.DialContext` with the normal MySQL connector, or
  `mariamemtest.Options.InProcess` for helper-owned pools. TCP remains the default
  and available for external migration commands. Local session admission returns
  `ErrCapacity` without a rejection worker; Close/capture/failure rules remain
  in force. See the [Go guide](../go.md#same-process-connections-unreleased).
