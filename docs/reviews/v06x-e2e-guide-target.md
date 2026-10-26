# First E2E target — Python and Go pgmem guide workflows

## Outcome and recommendation

The Human proposed these guides as a useful first target while P0/P1 discovery
was starting. Recommend matching their user workflows before a general Django
adapter: ordinary application settings, a separately launched Web process and a
real browser. The Python example requires worker-local stable-endpoint reset;
the Go example also permits a fresh app and Fork per test. These are different
acceptance cases and must not be conflated. Current mariamem supports the Fork/
settings building blocks, but neither browser path has been executed here and
stable-endpoint reset is not a current public API.

This refines the first milestone of the
[whole dogfood plan](v06x-dogfood-replanned.md), not the eventual supported scope.
Django runner integration, background workers, other metadata/tools and resource
work remain registered follow-ups. No live implementation or new public API is
selected by this source investigation.

## Reference identity and inspection

User-provided published pages:

- [Python E2E guide](https://shibukawa.github.io/pgmem/guides/python/e2e-testing/).
- [Go E2E guide](https://shibukawa.github.io/pgmem/guides/go/e2e-testing/).

The guide examples and associated fixture/helper/reset source were independently
read at pgmem source_commit
`3433a40bd4167daea2d8e364666bd5fcf18ef654`. The
[source receipt](v06x-e2e-reference-evidence/source.json) records the Git tree,
per-file blob IDs and SHA256. The repository default branch was not assumed to
be the website source. The precise deployed Pages commit was not established;
this is a pinned repository comparison of the examples, not deployment provenance
or a claim that the reference runtime was executed.

Python's guide uses process separation, session fixtures, reset before navigation
and worker-local apps. Go's guide passes the child's DB configuration at launch;
its sample permits per-test launch, and its global-environment helper precludes
`t.Parallel`. Both require completed DB work at transitions. This is evidence
about the reference's documented contract, not proof of mariamem behavior.

## Initial workload specification

Use small repository-authored order-entry applications with a comparable HTTP/UI
contract, not a port of PostgreSQL SQL. Freeze each application's source/data
before comparing native MariaDB12.3.3 and mariamem. The planned source does not
exist yet; this section specifies the execution input to author, not a runnable
fixture or a finished P0 runtime manifest.

| Case | Python milestone | Go milestone |
| --- | --- | --- |
| Application | Django development server in one child process, normal MySQL backend/settings and mysqlclient; no autoreload/extra server workers | Small net/http child binary, go-sql-driver/mysql with explicit app-owned DSN/pool |
| Test entry | Plain pytest plus Playwright page/browser, with app fixtures; no Django TestCase or pytest-django live_server ownership | Go testing starts/waits/reaps child; actual browser automation is invoked through a separately pinned browser helper |
| DB configuration | Explicit test settings read host/port/user/schema before Django starts; no in-process routing assumption | Child-specific Cmd.Env passes the DSN before Start; do not copy PostgreSQL-specific environment names or require process-global Setenv |
| Preparation | Actual migrations and common seed before app startup; close preparation connections before baseline capture | Actual schema/seed preparation before capture; same prepared state reused by independent children |
| First lifecycle | One app/DB endpoint per worker, sequential cases, reset before browser navigation | New Fork plus app per test, stop/reap app and close pool before child Close |
| Extended lifecycle | Post-startup schema/data capture and separate worker instances | Worker-local app reuse/reset, assessed separately from the permitted per-test guide path |

Keep the launch/HTTP/business logic ordinary. Test settings and a configuration
entry are allowed; requiring a test token on every request, custom business-path
middleware or rewriting application SQL would be an added burden to report,
not quietly counted as equivalent simple use.

Django TestCase/TransactionTestCase/pytest-django lifecycle research remains W3;
it is not a prerequisite for this plain-pytest browser fixture. The source
reference5.2.7 is retained historically. Django5.2.8 is the source comparison used
here because its official notes explicitly add Python3.14 compatibility; see
[release notes](https://docs.djangoproject.com/en/5.2/releases/5.2.8/) and the
[Django source receipt](v06x-e2e-reference-evidence/django-source.json). This is
neither a latest-version recommendation nor a frozen executable dependency set.
Do not force PyMySQL substitution for mysqlclient and call that normal backend
coverage. Freeze supported Python/client/browser artifacts at the execution gate.

## Minimum acceptance and follow-up cells

| ID | Observation / oracle | Classification |
| --- | --- | --- |
| G1 | Go parent passes child-specific settings before launch; application health query and browser actions reach that test's child; normal app code/DSN entry is used | First required Go/browser path; no live reset claim |
| G2 | Test A commits through UI, stops app; test B with its own app/Fork sees seed but not A's marker; app reaped before DB close; failure path cleans both | Required per-test isolation and shutdown, including injected test failure |
| P1 | Python A/B have the same worker Web PID/start count, HTTP address and DB address; actual browser action commits, B starts with baseline seed and without A's marker | First required Python/browser path; new live behavior must be designed/verified |
| P2 | A fails after commit; the next case restores baseline before navigation; errors/cleanup remain observable | Required failure-recovery path, not silent continue-on-error |
| P3 | In-flight work/transaction prevents safe reset: refuse/timeout with context, admit no next test, allow retry after declared resources close | Required bounded live failure contract; exact API/errno not chosen yet |
| C1 | Independent process-level workers own distinct app/DB/HTTP resources and browser contexts; sequential cases in one worker share no mutations | Required worker-isolation pattern for both languages; exact2/4-worker mandatory cells/budgets must be fixed before execution |
| C2 | App creates schema/seed at startup; a later baseline capture preserves it without stopping/restarting the app | Explicit reference extension; must have its own feasibility/capture decision because Snapshot currently consumes source |
| C3 | Reuse the Go worker app across sequential cases with a stable endpoint and reset | Reference's optional reuse route; separate result, never inferred from G1/G2 |
| C4 | Existing physical sessions survive reset with fresh-session/prepared-handle semantics | Stronger reference implementation feature; separate contract decision, not implied by P1 or endpoint stability |

P1 must not be made green by relaunching the Python Web server. G1/G2 may
relaunch because that is their declared lifecycle, but do not advertise that as
C3. Separate browser contexts alone do not reset database state. Readiness
should include an application/DB response and process identity, not only an open
TCP port. Record cookies/auth/cache policy separately from database reset.

Use real browser DOM actions and retained observations, rather than treating
an HTTP-only request or commented browser placeholder as browser coverage.
The exact browser tooling and helper are still an execution input to pin; the
Go reference snippet itself does not supply a runnable browser implementation.

## Source findings that affect the next design

### Python: fixture ownership and the missing stable endpoint

At the pinned pgmem source, pytest_plugin.py:172 creates a session live fork;
line245 selects a baseline and resets before yielding a function-scoped DB.
The adjacent LiveBaseline class handles post-startup capture. The same file
shows why this is not merely a driver-routing fixture.

mariamem's pytest_plugin.py:117–129 instead disconnects, consumes a preparation
source into Snapshot and creates an independent child per test. Database ready
replies fix each child's connection information (`python/mariamem/__init__.py:119`).
`internal/host/server.go:94` allocates a new ephemeral listener for that DB.
Therefore the present application process cannot simply keep its startup DB
address while a normal fixture replaces the child. This is a source-level
lifecycle gap, not a reproduced Django/driver/SQL failure.

A normal Django configuration with connection close/reopen at request boundaries
is a useful first finite input, but it is not proof of arbitrary persistent pools.
The actual source/setting must be pinned and verified; do not disable pooling or
change application settings silently to widen a PASS.

### Go: child configuration is already an available mechanism

The pinned pgmemtest.go ShadowPG helper uses testing.TB.Setenv (line412) and
returns a test server. Its guide addresses a new child process, not retargeting
an already-running process. mariamem already supplies Snapshot.Fork and child
DSN/connection information; explicit Cmd.Env is a candidate recipe using existing
public API. This does not require choosing a new Go routing/test helper first.
It still requires actual child/browser/cleanup tests; source plausibility is
not a runtime PASS or proof of concurrency safety.

### A stronger reference reset must not be copied by assumption

Pinned pgmem reset.go documents port/client-connection retention and fresh session
state, including restoring selected PostgreSQL prepared/listener metadata. Those
are PostgreSQL-specific implementation contracts. No equivalent MariaDB behavior
is established by matching a fixture name or adding COM_RESET_CONNECTION.
First compare L1/L2 against the actual app and decide which physical-session
behavior is required; validate text/prepared/session/error boundaries separately.
The project's prior Snapshot-consumes-source and explicit-preparation decisions
remain active until a specific new design is accepted.

## Django lifecycle boundary confirmed from source

At the pinned Django source, base/creation.py:32/78 changes the test schema and
runs migration; destroy_test_db at283 closes the connection and later restores
the name. TestCase at testcases.py:1366 uses atomics, while TransactionTestCase's
fixture teardown at1253 flushes data. LiveServerThread at1729 is a thread, not
the separate application process required here. runserver.py:53–61 exposes the
threading/reload controls. These are source findings, not a native test result.
The browser milestone can use ordinary settings/runserver and plain pytest
without inheriting either Django test class's database lifecycle. General adapter
work must still preserve those distinct lifecycles later.

## Execution inputs still to close

The reference source and first behavioral targets are pinned. P0's executable
manifest and P1 native controls are **not complete**:

- Author/pin the small Python and Go apps, migrations/schema/seed and matching
  browser/UI assertions; source SHAs and fixture hashes must be recorded.
- Select exact runtime framework/driver/test/browser automation versions and
  platform wheels/binaries. Playwright's browser revision must match its package;
  record actual executable identity and environment dependencies.
- Pin native12.3.3 controls on macOS arm64 and Ubuntu x86_64, acquisition receipts,
  Python3.11/3.14 cells, Go toolchain, worker counts and serial/failure cases.
- Set per-job timeout, scratch/storage and process/resource budgets, required
  cleanup receipts and the original-endpoint audit before running anything.
- Define native control reset/reseed without a fake mariamem live implementation.
  Native controls may keep the app and address while resetting data in a recorded
  control procedure; that is not evidence of a guest baseline-reset mechanism.

The next bounded work is app/runtime-manifest authoring and native controls,
while the Python stable-endpoint/capture design is investigated separately.
Only after those results choose a live spike/adapter proposal. General Django
runner support, W5 workers, other frameworks and optional C2–C4 remain named
follow-ups, not silently abandoned or claimed as working. No guest/runtime/API
change, browser install, database import or reference/native/guest run occurred
in this source-inspection task.
