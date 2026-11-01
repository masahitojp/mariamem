# D1 deferred acquisition and routing exclusion follow-up

Both requested repairs are implemented; candidate adoption/protected integration
and new both-OS installed-wheel evidence remain pending. No heavy Release run
was dispatched. The previous four-cell receipt belongs to its original source
and does not qualify this changed lifecycle or its new backend guard.

Executed implementation source_commit:
`86caccf57bab3bdcfbb85a29c70eaffd79ecf110` (clean checkout).
Local macOS27.2 arm64: Python3.11.18 and3.14.10, Django5.2.8,
pytest9.0.2, pytest-django4.12.0, mysqlclient2.2.7. Both passed the20 real-SDK
scenario assessments (10 per runner), including committed/DDL state restoration,
expected failures, partial migrations, actual retained SQL connection refusal,
repeated runs and database-free suites. The latter now start **zero** hosts;
other scenarios still verify the observed host PIDs disappear.

The SDK host is reused from the published0.6.0 wheel, not rebuilt from this
adapter candidate. Host source_commit:
`b3b3b46a8807482ad3f96725af86e031fe369b01`; host SHA256:
`b467baece270d6d3cb0770781695c1960de2c0d9c4bd536d6aac2c14f37c1e2a`.
The downloaded wheel hash and host hash were checked and Go build metadata
matches its clean source. This is source-entry evidence, not installed-candidate
wheel or macOS15/Ubuntu24.04 qualification.

## Behavior and checks

- `prepared_database()` returns declaration-only settings. Runner acquisition
  occurs at `setup_databases()` and pytest acquisition at its corresponding
  fixture. No owner/atexit callback is acquired by declaration alone.
- The thin `mariamem.django.backend` subclasses Django's ordinary MySQL backend;
  its only connection override rejects inactive configurations before driver
  dial. Blank declaration endpoint fields must never fall through to MySQL
  defaults. Keep the helper's engine value. No SQL, engine or wire implementation
  is replaced; this backend is a connection admission guard.
- Actual management `check` and no-SQL `shell` plus pytest collection-only are
  tested with SDK startup forbidden. Early SQL also has driver dial forbidden:
  it must raise `ImproperlyConfigured`, not connect or start a host.
- Actual pytest collection rejects function/class/module shadow_maria marks with
  `UsageError`; `mariamem_app_db` and active routing registries are also refused
  before acquisition. Two additional pure policy controls run without optional
  Django/C dependencies in daily checks. Arbitrary later custom hooks are not
  a universal compatibility promise.
- Each routing binding counts successful routed connections under its existing
  lock. Successful zero-connection scope exit emits `UnusedRoutingWarning`
  after drain and target restoration. Failed scopes retain original/cleanup
  errors; warning-as-error still leaves the binding retired. The diagnostic
  does not prove that an original DB was reached. No mysqlclient routing or
  unified routing/prepared lifecycle is added.

Related Django/workflow/routing/receipt/CI component checks:146 PASS and25
subtests on each Python minor. Six intentional empty bindings in existing
controls emitted the new warning. Afterward, the two new dependency-free
exclusion controls plus existing owner and package/license checks passed24 tests
on each minor. These are overlapping check sets, not170 distinct tests.
Public-source, touched-link and diff checks passed. No Go/guest/generated or
version change was made; no broad Go build or runtime campaign was run.

[Saved evidence](d1-deferred-start-evidence) retains inputs, aggregate assessments,
all acquisition/declaration events and selected original expected-failure output.
The checksum file includes raw and saved hashes; worktree/home prefixes and
trailing whitespace are normalized. Unselected ordinary-success stdout is not
retained. Fake-handle failure controls remain component evidence, not newly
injected real-engine I/O faults. Resource tuning remains separate.

The existing Release Django campaign already runs the updated harness and API
checks using its shared installed wheel, so no workflow/job/build was added.
It now includes the guarded backend in its recursive input hashes. Normal PR
checks remain the handoff for this candidate; heavy installed-wheel acceptance
stays on the existing Release path.
