# P1 prepared pytest entry — proposal after G1 evidence

Status: PROPOSED; source inspection plus local pytest characterization, not P1
implementation or runtime acceptance.
Inspected candidate: f58eebcdcb9ddb38a08fdbbd4ace8f6717154ab8. The Human
approved the overall P1/G1/EP1/EG1 direction and G1 first; this proposal does not
silently extend the structured contract's G1-only implementation authorization.

The next decision is the P1 command declaration and diagnostic boundary.
Recommendation: retain the existing fixtures and marker, add a declarative
command alternative to the preparation callback, and keep lifecycle ownership
inside the entry. Users then provide their migration/seed operation and ordinary
test code. The main concern is compatibility: existing preparation fixtures may
execute side effects before returning None, rather than return a callback.
Those setups must keep working and preserve their original pytest failures;
we must not silently call them twice or promise to intercept arbitrary fixtures.
The [local report probe](v06x-python-fixture-reporting.md) now shows a narrow
fixture hook can add notes without replacing original failures, on pytest 7/9.
No P1 implementation approval is inferred from that local result.

## Existing foundation and gaps

The plugin already supplies session-scoped mariamem_server, mariamem_prepare
and mariamem_snapshot, function-scoped mariamem_fork, routing via mariamem_app_db,
and the no-argument shadow_maria marker. A session is local to each xdist worker.
Current callback return values are ignored; returning None can also follow
side-effect preparation through a fixture dependency. Keep both behaviors.

Source: python/mariamem/pytest_plugin.py (preparation and capture fixtures),
python/mariamem/__init__.py (Database connection_info/snapshot/Close), and
python/mariamem/snapshot.py (baseline/child ownership). Existing subprocess
policy tests are tests/test_routing_pytest.py; the native/guest Alembic recipe
is in docs/preparing-test-data.md and tests/preparation_migration_acceptance/.
Those tests are foundations, not a new P1 acceptance receipt.

Missing mechanisms: an entry-owned command runner and success check; uniform
readable-owned failure detail for operations the entry executes; explicit
combined-failure/admission behavior; and the full P1 use-case/resource campaign.
Nested context managers currently call close directly: preserving the primary
error when cleanup also fails needs its own oracle, not an assumption.

## Proposed usage (not implemented)

Existing callback preparation stays unchanged:

```python
import pytest

@pytest.fixture(scope="session")
def mariamem_prepare():
    def prepare(db):
        # Application code owns its SQL connections and must retire them.
        migrate_and_seed(db.connection_info())
        # No exception means success; return values remain ignored.
    return prepare

@pytest.mark.shadow_maria
def test_changes(application, mariamem_app_db):
    application.commit_changes()

@pytest.mark.shadow_maria
def test_seed_again(application):
    assert application.list_names() == ["baseline"]
```

Proposed command alternative uses the same fixture, not a second preparation
phase or automatic migration discovery:

```python
import sys
import mariamem
import pytest

@pytest.fixture(scope="session")
def mariamem_prepare():
    return mariamem.PrepareCommand(
        [sys.executable, "tools/migrate_and_seed.py"],
        timeout=60,
    )
```

Proposed constructor: `PrepareCommand(argv, *, timeout=120, cwd=None, env=None)`.
Copy argv into an immutable tuple and copy env at declaration. Reject a string
in place of argv, an empty executable, non-string/NUL arguments, non-finite or
non-positive timeout (including bool), malformed env keys/values, and an override
of the reserved connection variable. `cwd=None` means pytest's rootpath; a
relative cwd is relative to rootpath. Set the child cwd without changing the
parent process directory. There is no shell option. This is one command; a user
script composes migration and seed. Descriptor validation and its original
exception precede command launch and still require source cleanup if started.

The application script reads JSON connection_info from the reserved environment
variable MARIAMEM_PREPARE_CONNECTION_INFO (host, port, user, password, database)
and passes it explicitly to its own migration entry. The runner supplies the
actual preparation endpoint; routing is not active during preparation. An app
may create its declared schema explicitly, as the existing Alembic recipe does.
No Django, Alembic, URL rewriting, shell interpolation or framework auto-routing
is built into this runner. Optional cwd/env arguments must have explicit types;
caller env must not override the reserved connection variable. Do not print
connection data or environment values in entry diagnostics.

None, callable and the explicit PrepareCommand descriptor are distinct inputs.
A callable's returned object never implicitly becomes another command: that
would change the existing ignored-return contract. Invalid descriptor/argv/
timeout fails before command launch. No new command CLI or subprocess helper is
added until the proposal is approved.

## Lifecycle and failure contract

1. Lazily start one source for the worker. Unmarked tests do not start a DB.
2. Resolve preparation exactly once. For a callback, invoke it once with the
   source; for a command, launch once without a shell. Exit 0 means successful
   execution, not validation of application business correctness. Nonzero exit,
   spawn failure, timeout or interrupt prevents capture and dependent admission.
3. Retire entry-owned command processes, then wait for physical SQL disconnect
   and capture. User callbacks must retire their own pools/transactions. A
   callback can block noncooperatively; do not promise forced Python cancellation.
4. Each test gets an independent prepared child. Close registered routing pools
   and bindings before child teardown. Preserve explicit fixture overrides:
   replacing a fixture transfers that boundary's ownership to its author.
5. Cleanup attempts all entry-owned finalizers and retains primary plus cleanup
   failures. A cleanup debt stops later dependent admission in that worker;
   another worker's independent owners are not silently claimed stopped.
6. Close children before baseline and always finalize the source through its
   idempotent Close, including consumed capture and invalid-but-not-disposed
   cases. A flag alone is not proof of disposal.

The command runner owns the process group it launches, including timeout and
KeyboardInterrupt unwind: bounded terminate/kill/reap of owned processes, with
unknown cleanup reported honestly. It does not promise recovery after machine
loss, hard kill or an application daemon escaping the owned process group.
Tests must observe the actual child process and temp/connection counts.

Diagnostic level: readable-owned (proposed before implementation; no basic-first
fallback for P1). Preserve exception identity through an original-cause field
and chaining; command errors retain exit code/stdout/stderr and timeouts retain
TimeoutExpired. Interrupts remain interrupts. Combined errors retain every
cleanup cause. Use a private owner record plus exception notes and a focused final summary
for stage, known/unknown cause, next action, original failure, admission and
cleanup states. Reuse pytest's separate setup/call/teardown error reports;
no new public exception hierarchy is proposed here. Do not infer
completed capture-internal cleanup from completed helper finalization, as G1's
regression demonstrated. Direct user SQL/assertions retain ordinary pytest output.

Example diagnostic, with application-owned stderr and no endpoint/environment:

```text
mariamem prepare: migration command exited 23
cause: migration reported "seed table missing"; inspect migration stderr
admission: stopped for this worker; capture was not attempted
cleanup: command reaped; source closed
original: CalledProcessError(returncode=23); stdout/stderr retained
```

A mariamem_prepare override can fail during fixture resolution before a callback
runs. The [source-bound characterization](v06x-python-fixture-reporting.md)
confirms that pytest preserves preparation and source-finalizer failures as
separate reports, but does not supply the entry's admission/cleanup fields.
Use a hook restricted to the named preparation fixture to observe that original
failure and attach a stage note, leaving pytest's exception object and result
unchanged. Annotate operations the entry executes directly at their owned
boundary. Keep the owner record for actual finalization/admission state and
render its final summary after cleanup; do not label pending cleanup complete.

The same probe shows the current entry admits the second body after the first
child cleanup fails. P1 must add a worker-local stop-on-cleanup-debt check before
child acquisition, preserving the first cleanup cause. Another worker is a
distinct owner. Notes alone are not that guard. The prototype note deliberately
says cleanup=pending; it does not implement final summary, actual disposal or
that admission guard. These remain mandatory P1 implementation oracles.

## Finite acceptance and resource budget

| Boundary | Required observation / negative control |
| --- | --- |
| Callback/command success | Preparation once per worker, exact schema/seed per test; command receives the actual source endpoint; callback return remains ignored |
| Isolation | First child commits DDL/data; second sees exact baseline; reverse order, four-case batch, ordinary failing subprocess then healthy child |
| Failures | Invalid input, spawn failure, exit 23 + stderr, timeout, interrupt, disconnect/capture failure, primary plus cleanup error; no dependent case after failed setup/debt |
| Physical ownership | Source preserved/consumed/invalid, partial baseline, command group/process and pool/connection retirement, FD/temp baselines and teardown ordering |
| Routing | PyMySQL 1.2.3 and SQLAlchemy 2.0.54; import guard, bound target, test-owned pool retirement; no preparation-time automatic routing |
| Compatibility | None, callback, existing side-effect fixture, explicit fixture overrides, no marker/no startup, original failure identity; pytest 7-compatible supported API |
| Detection net | Omit command wait, ignore exit, continue after setup error, skip child/source/baseline cleanup, replace original error and lie about cleanup; each control must fail its named normal-pass oracle |

Required environment: macOS 15 arm64 / Ubuntu 24.04 x86_64 × Python 3.11/3.14,
fixed driver locks and source-bound receipts. Keep existing native MariaDB
12.3.3 controls at their recorded scope; a changed app/input needs a fresh bound
native control. Django and Connector/Python are not added to the P1 profile.

Run xdist worker counts 1/2 with four cases, one warmup plus three observed
batches. One active case per worker is the default; up to two simultaneous
workers means at most two active test children in the canonical campaign.
Preparation pools have max-open 1, child pools max-open 2/max-idle 1. Record the
observed multiplication and transient preparation/cleanup, not merely xdist's
worker setting. No pytest-thread concurrency scheduler or 16-session change.

Use the accepted retained-baseline 1/2/3 input and resource ceilings from
v06x-fixture-acceptance.json. Observe process-tree RSS/available memory, FD,
physical connections, temp bytes and final owners, with actual guard STOP.
Record first-test setup, second-test edit delta and repeated-batch/phase elapsed
time. Separate acquisition from execution, label cache state and leave unmeasured
cold/human time unclaimed. Fix exact command/measurement orchestration before
implementation acceptance; this document is not a measurement.

## Next bounded work and stopping point

Review the fixed command declaration and narrow annotation/owner-state design, then commit
its decision before P1 runtime/helper code and update the implementation allowlist
through the normal contract change. Start with focused subprocess/fake-owner
oracles, then real guest/schema/seed/routing checks, then the bounded both-host
campaign and installed-wheel example. Failures must be diagnosed without skipping
or relaxing their oracle. No independent upstream app, D1 mechanism, EP1/EG1
implementation, wire extension or release work is implied by P1 completion.
