# Unreleased release notes — staging

This file is the sole staging content source for future release notes. Adopted entries below are unreleased; this staging file does not select a
release version or grant qualification/publication approval. Published0.6.0 notes remain authoritative in
[NOTES-v0.6.0.md](../../release/NOTES-v0.6.0.md); published installation commands
and version metadata remain unchanged.

## Candidate under review — #53 / PR #85

- Go Snapshot adds `SnapshotOptions.MaxForks` and `Snapshot.MaxForks()`. Omission
  now resolves a finite memory-based limit; full capacity waits under the Go
  context before starting a child. Child cleanup retains its slot, and parent
  Close wakes waiting Forks without closing successful children.
- Go Live needs at least2 slots and reserves replacement capacity before draining;
  a full parent returns busy while preserving the current generation. Explicit
  Reset can recover only after all cleanup debt is confirmed. The Go test helper
  retains default2 and passes the same cap to its Snapshot; HTTPConfig exposes
  a cap override. Auto sizing is not CPU-optimal or a process-wide memory guarantee.
- Python adds `snapshot(max_forks=...)`, read-only `max_forks`,
  `fork(timeout=...)` and `Database(snapshot=..., fork_timeout=...)`.
  Different-host children retain their origin slot through actual disposal;
  capacity waits release the parent lock and retain finite control watchdogs.
  Pytest adds `mariamem_max_forks` (None/auto) and finite
  `mariamem_fork_timeout` (default30 seconds). Acquisition failure stops dependent
  admission in that worker and preserves the original error; normal assertions
  keep their existing behavior. None/callable/PrepareCommand preparation is unchanged.
- Python E2E `Config.max_forks` reaches its Live baseline and explicit1 rejects
  before preparation. Prepared Django adds `max_forks` / `fork_timeout`, forwards
  them to each capture/acquisition and retires class/test owners before requesting
  its final DROP child. These per-Snapshot/worker caps are not a global resource
  limit or CPU/latency optimum; choose explicit caps and worker totals as needed.
- Nested acquisition while holding every slot can wait indefinitely. Release a
  child before the next synchronous Fork, or bound the wait with a Go context /
  Python timeout. Expanded Go `SnapshotOptions` and `HTTPConfig` require keyed
  literals instead of old positional literals.
- Capacity wait/busy diagnostics report `max_forks` and observed `occupied_slots`
  with a close-children/increase-limit remedy. Python uses the last responsive
  capacity reply, or explicit `unknown` if none arrived. Existing error identity,
  code/stage and closed semantics are preserved.
- Linux auto-sizing validates kernel sysinfo units and proc MemTotal separately;
  either physical source can fail while the other/cgroup/Go limit still applies.
  Only absence of all valid memory observations uses the existing finite CPU
  fallback. This remains a sizing heuristic, not an OOM guarantee.
- If cgroup limits are unreadable or invisible, auto sizing may use host RAM
  and over-admit relative to the container budget; configure an explicit cap.
  Independent root `Start` / `start()` calls are outside per-Snapshot caps.
  Private control rejects negative capacity tokens, including `-0`, request-locally.
- Host WASI writes now propagate zero-byte write errors, including broken pipes,
  and preserve actual short-write progress. This fixes the tested interrupted-
  guest cleanup stall without changing the accepted prepared CALL observations.
- This draft is not adopted on main. The fixed both-host/Python-version matrix,
  including installed D1 cap1 execution, passed on `c53771cd`. The later G1
  diagnostics correction requires its own verification; see the
  [review follow-up](../reviews/issue53-review-followup.md). The original
  [adoption review](../reviews/issue53-fork-limit-adoption-review.md) records evidence
  and limits. Adoption and a future release remain separate Human decisions.

## Adopted on main — unreleased

### Explicit prepared Django entry (#43 / PR #67)

- Add `mariamem.django.prepared_database`, `PreparedDiscoverRunner`,
  `PreparedTestCase` / `PreparedTransactionTestCase` and the explicit
  `mariamem.django.pytest_plugin`, with optional `django` / `django-pytest` extras.
  Django creates/migrates the test DB, a callback prepares seed once, and each
  test starts from an independent Fork of prepared class state, including after
  committed writes or ordinary failure. Original and cleanup errors remain
  visible; retirement failure stops subsequent admission in that run.
- This is explicit opt-in, not transparent TestCase compatibility. There is no
  class-wide atomic; class preparation is committed and `on_commit()` may run
  immediately there. Per-test TestCase atomics remain. Initial scope is one
  default alias and serial execution; unsupported modes are rejected.
- Routing/`shadow_maria` and prepared Django ownership cannot be combined in
  one test invocation. This exclusion is a documented support boundary, not a
  universal automatic detector. Unused routing bindings now warn with
  `UnusedRoutingWarning` after successful cleanup when they routed zero
  connections. See the [entry guide](../django-prepared.md).
- Local source-entry results on a reused published host do not qualify the
  installed wheel on both supported OSes. The existing Release Django job
  subsequently passed macOS15 arm64 / Ubuntu24.04 x86_64 × Python3.11/3.14 on
  reviewed source `ad9c7e67`; [the receipt](../reviews/d1-release-41320361521/README.md)
  preserves its identity. PR #67 is adopted on main; the original Release run
  failed core policy tests and is not Release READY. Their test-only repair
  passed the required Development checks before merge.
  `prepared_database()` is now declarative: host acquisition occurs only at
  database setup, and SQL outside that lifecycle is refused before driver dial.
  Settings import, check/shell, discovery and collection-only do not start hosts.
  The follow-up passed fresh four-cell installed-wheel acceptance and READY at
  `90e7ed5f` in [verify41327745652](../reviews/d1-release-41327745652/README.md)
  and was adopted through PR #70. No candidate assets were published.
  Collection rejects shadow_maria/mariamem_app_db and setup rejects active routing.
  No guest/generated code, core Go runtime or version change is included; no
  performance or detailed resource claim is added.

## Adopted local D1 xdist — unreleased

The local extension adds explicit `-n N` local workers for `load` / `loadscope`, using
pytest-xdist3.8.0 / execnet2.1.2 in the `django-pytest` extra. Serial stays the
default. Each DB-using worker owns a separate host and migration/seed baseline;
class preparation can repeat per worker or when rescheduling re-enters a class. Controller/idle/DB-free workers acquire
none. No cross-process SDK handles or shared global Snapshot are introduced.

The extension retains failed tests on worker crash; a replacement prepares a
fresh lineage under normal xdist restart policy. Cleanup debt remains local to
the failed worker. Hard death closes the host by control EOF but cannot run
Python temporary-directory finalizers; runner/job scratch cleanup remains
necessary. Automatic counts, remote/manual gateways, loop-on-fail, other
schedulers and Django --parallel are outside the accepted scope.
The existing Release Django job adds installed-entry cases with its existing
shared wheel/host. No new workflow/build/version or performance claim is added.
Both OSes × Python3.11/3.14 passed installed-wheel serial/parallel acceptance
and Release READY in operation=verify; the Human approved adoption. See the
[adoption receipt](../reviews/d1-xdist-adoption.md). Publication remains separate.

## Django6 support — unreleased

The `django` / `django-pytest` extras accept Django5.2 LTS,6.0 and6.1
(`Django>=5.2.8,<6.2`). Django6 requires Python3.12+; Python3.11 continues with5.2.
The existing Release Django profiles become3.11/5.2 LTS and3.14/latest6.1,
without additional jobs or builds. Prepared ownership, routing exclusions and
serial/local-xdist lifecycle semantics are unchanged. Published0.6.0 metadata
is unchanged; use a current-source wheel for the expanded extras.

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
