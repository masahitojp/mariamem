# Connection switching — productization design and spike closure

2026-10-24. Source_commit: `804ff502e487a89fa690126ab4de375ff7d818ef`,
the [native result review](v06x-connection-routing-human-review.md).
The Human accepted proceeding with productization design and the remaining
R2/R3 checks. This authorizes this design and authored experiment changes;
production implementation, public API selection, main adoption and release
remain separate decisions. Branch: `experiment/connection-routing-contract`.

## Human Review — prepared, awaiting the closure results

**Proposed next decision: approve the implementation boundary in sections2–6.**
Recommendation is a small opt-in Python routing layer, an explicit SQLAlchemy
adapter and thin pytest integration, with ordinary configuration injection and
child-owned Go pools alongside them. For supported applications this keeps SQL
and connection creation in application code, while a test fixture supplies each
independent DB. Install the registered-profile guard before application imports;
bind a child only for its test. No connection is silently redirected outside a
live binding.

The strongest objection is that existing application state can precede a fixture:
an imported factory can preprocess options, or an existing engine can have live
connections. A function fixture alone cannot contain these states. The proposed
boundary therefore includes early guard installation, explicit engine enrollment
and actionable rejection of unsupported entries. It does not promise that any
running application can be redirected by one line. The pending R2/R3 oracles
must pass before the implementation recommendation is final. No approval of
production implementation is inferred from the Human's request to proceed here.

## 1. Evidence and the two remaining checks

[CI40026373681](https://github.com/masahitojp/mariamem/actions/runs/40026373681)
at prototype `dd3b44d46012093fa7dfa05f0ed8f5b8729740a2` passed13 executable
cases and four mutation controls on each OS. The previous review preserves
the distinction between those PASSes and the full approved R1–R8 scope.
The current changes add two real-guest cases and two mutation controls; the
original13 cases and four controls remain. **New runtime outcomes are pending.**

| Added case | Positive oracle | Deliberate defect and required negative observation |
| --- | --- | --- |
| R2 `idle-session-state` | A/A/B/A bindings use distinct physical connections. Before each use, a session variable is NULL, a temporary table is absent (1146), and a prepared statement is absent (1243). Each is then created and read successfully, proving the state was actually seeded | `retain_session` disables checkout-generation validation. The second A sees `scope-0` from the previous generation although its destination marker remains A. The runner requires that exact observation |
| R3 `unknown-physical-ownership` | A matching-profile engine contains a real untagged connection to local child A. First enrollment while checked out/in a real transaction rejects without closing/rolling back that handle. After return, idle enrollment closes it, creates an owned replacement and queries B | `adopt_unknown` disables both enrollment's idle discard and checkout's unknown-owner refusal. A request for B reads A. The runner requires that exact requested/observed pair |

R3 seeds the old connection using a temporary SQLAlchemy `do_connect` listener
that returns a connection only to child A, without mutating the creator's retained
connection arguments. It removes that listener **before** enrollment; the engine's
default creator and registered logical URL are otherwise unchanged.
This is different from the previous unknown-**profile** refusal. The mutation
removes both defenses because either defense can prevent reuse; its FAIL is not
evidence that removing only one necessarily causes a wrong-target query.

The runner now requires the exact15 case names, all R1–R8 rows and six expected
mutation locations. For the two new controls it also requires the specific
observed leaked state/wrong child, not just an arbitrary AssertionError. It
retains host cleanup and original-endpoint sentinel requirements. The receipt
names contract `routing-r1-r8-session-ownership-v2`. A missing case or unexpected
SQL error cannot count as closure.

Five local receipt-gate tests pass, including rejecting the old13-case success
as new-scope completion, duplicate/missing/failed cases, a nonzero control exit,
lost cleanup, required Connector SKIP, and wrong negative-oracle observations.
They also accept the unchanged four prior mutation receipts. The two added
positive rows in these unit tests are explicitly synthetic; these tests validate
the decision gate and make no new runtime PASS claim. CI runs them before the
real-guest campaign. Source syntax and runner argument parsing pass locally.

Runtime source_commit remains `dfa6b21c4b4fb2c6e5e7e5db0d21eeef52394776`;
Go1.26.10, guest SHA256
`8f6177627855232d096cfb3987d94e35c19fc4fc0c7f32ca8c69ff9fd4990a40`,
PyMySQL1.2.3, SQLAlchemy2.0.54, Connector/Python26.7.0 and Go driver1.9.3
are unchanged. The workflow verifies clean runtime source/binary metadata and
records the new prototype SHA/file hashes separately. No generated Go, guest
patch or converter change is involved. Both OSes remain required; Ubuntu C's
known import SKIP remains distinct from required default/pure behavior.

## 2. Proposed user entry and public surface

API spellings below are **proposals**, not installed features. Put routing in
an optional `mariamem.routing` module; importing/using today's `mariamem.start`
alone must not install hooks, import SQLAlchemy or change connection defaults.

```python
# Install before importing application code that can create SQL connections.
with routing.install(profiles={"app": profile}, drivers=("pymysql",)) as routes:
    import application

    # Explicit registration before engine use; no per-test global dispose.
    routes.enroll(application.engine, profile="app", ownership="test")
    with baseline.fork() as child:
        with routes.bind("app", child):
            application.create_user()
```

`profile` names the original logical TCP endpoint, requested schema and supported
driver entry. Child metadata replaces transport/credentials, while the logical
schema stays unchanged. Reject duplicate/ambiguous profile registrations; start
with one registered application profile, not a new multi-database mapping API.
Keep preparation connection settings explicit. A preparation callback may run
against a bound setup DB, but must release its handles before consuming Snapshot.

For an application that accepts settings/pools, configuration injection remains
the simplest public path: pass `child.connection_info()` with its prepared schema
to the normal application factory. Go keeps a separately owned `sql.DB` per
child and passes it/its DSN through the application or GORM construction seam.
No context-switched shared Go pool or new Go interception API is proposed.

For pytest, propose an opt-in profile declaration in pytest's ini configuration
and function fixture `mariamem_routed`. For example, the following **draft**
configuration carries endpoint/schema matching, not passwords:

```toml
[tool.pytest.ini_options]
mariamem_route_profiles = ["app = 127.0.0.1:3306/app"]
```

After declaring preparation and any engine adapter once in `conftest.py`, a test
module can use `pytestmark = pytest.mark.usefixtures("mariamem_routed")` and
invoke its ordinary application functions. The second test reuses that fixture.
The fixture binds one child from the existing worker-local baseline. Document
the profile and engine setup alongside this short entry: “one line” must not
conceal configuration that the example actually needs. First coverage remains
one profile, existing synchronous drivers and explicit SQLAlchemy enrollment;
the wider framework map remains open.

## 3. Admission before application imports

There are two separate lifetimes: a process/session guard for a registered
profile, and a shorter child/generation lease. The guard remains installed when
no lease exists, so collection-time and late background connection attempts
reject with a stage and next action instead of reaching the original endpoint.
A cold engine constructed at import can be enrolled before its first checkout;
an import that immediately executes SQL must move that work into preparation or
application setup. Interception cannot retroactively undo an earlier query.

Proposed pytest implementation uses the existing installed plugin entry point
and an early `pytest_load_initial_conftests` hook wrapper, installing before its
inner conftest loader runs. Profile definitions must be available from static
ini/CLI input at that point; a function/session fixture is too late to install
this guard. Empty configuration keeps current behavior. Fail clearly if a
configured driver/version cannot be guarded. Uninstall on startup/collection
failure as well as normal session end. Plugin-disabled/manual entry remains an
explicit user responsibility; unrelated earlier plugins are outside this
installation boundary. Do not advertise protection before the guard runs.

The [pytest hook reference](https://docs.pytest.org/en/stable/reference/reference.html#pytest.hookspec.pytest_load_initial_conftests)
states this hook is an early-plugin hook and is not called for conftest files;
the [plugin discovery order](https://docs.pytest.org/en/stable/how-to/writing_plugins.html#plugin-discovery-order-at-tool-startup)
puts installed/explicit plugins before initial conftest loading. These documents
were checked on2026-10-24; the retrieved reference describes pytest9.0.2.
They support the seam, not proof across mariamem's declared `pytest>=7` range.
Implementation must exercise early imports in subprocesses at the selected
minimum/current pytest versions or return to Human Review before narrowing that
range. No pytest requirement change is authorized by this design.

## 4. Supported entries, pools and ownership

| Entry/state | Proposed initial behavior | Evidence / implementation condition |
| --- | --- | --- |
| PyMySQL direct, saved class alias, deferred/reconnect | Guard registered profile; bind a fresh physical session to one live lease | R1 passed; preserve option normalization and the driver's ordinary defaults |
| Connector/Python module factory, default/prepared | Guard the enrolled module entry before its advanced preprocessing; retain selected default/pure/C behavior | R7 passed for available modes; keep precise accepted Prepared exceptions |
| Saved Connector factory alias | Ordinary explicit-TCP call worked in the spike; broad saved-factory support is **not proposed yet** | Earlier function references can preprocess option files/DNS/pools before the abstract hook. Use the explicit factory adapter/module entry for this boundary; do not promise universal early rejection |
| SQLAlchemy default QueuePool | Explicitly enroll before application activity; discard unknown idle entries once; validate lease at every checkout | R2/R3 closure pending. No mid-query migration, statement replay or COM_RESET_CONNECTION dependency |
| Checked-out session/transaction | Reject enrollment and retain the external handle/transaction for caller-controlled release | Never equate `dispose()` with closing active checkouts |
| Custom creator/pool, external/native handles | Reject unsupported enrollment with an explicit adapter/injection action | No global discovery of raw handles; profile matching is not ownership proof |
| Unregistered connection | Remains outside the registration contract | Never claim process-wide containment |

The saved Connector alias boundary is an explicit proposed support choice for
Human Review, not an erasure of the spike observation or of future capability
work. DNS/failover, option files, built-in Connector pools, supplied sockets and
required TLS need normalized support or an enforceable rejection at the enrolled
entry. An advanced call that bypasses that entry has no such containment claim.
Do not market it as supported merely because the simple saved-alias case passes.

Enrollment is a caller handoff while the application is quiescent. Checking a
pool's checked-out count is useful refusal evidence, not an atomic barrier
against arbitrary concurrent external calls. Offer construction of a test-owned
engine when this handoff is unavailable. The helper must not claim safe hot
takeover of a live application. During tests, generation checks protect the
shared enrolled pool; invalidate only that stale physical record. Do not dispose
the entire engine on every test exit and disrupt another active scope.

Use public SQLAlchemy events/invalidation where possible. The prototype's
`pool._creator` inspection is a version-specific seam; isolate it in the adapter,
check known supported versions and refuse an unknown layout. The current
[SQLAlchemy invalidation documentation](https://docs.sqlalchemy.org/en/20/core/pooling.html#more-on-invalidation)
describes checkout-triggered replacement; today's documentation reports2.0.55,
while the experiment remains pinned to2.0.54. No dependency update is implied.

## 5. Scope, cleanup and useful errors

Lease admission checks, physical connection creation and retirement must share
a lock/state protocol. Recheck the lease after a slow connect completes; if
retirement won, close the new session before it escapes. A copied ContextVar
retains a revocable lease, not permission to keep connecting after its test.
Nested leases restore the outer token. Explicit propagation is required for a
new thread; synchronous DBAPI in asyncio does not establish async-driver support.

Teardown order is stop admissions, finish/join cooperative application work,
release tracked checkouts, close owned physical sessions, wait disconnected,
then close the child and restore scope. The guard survives until the registered
application users have stopped. `bind` borrows the child; the fixture/caller
owns its Close. A bounded drain failure is reported with unreleased resources;
it does not mean those resources were safely reclaimed. Any subsequent child
Close follows the existing lifecycle/error behavior. No arbitrary-task discovery
or new forced-stop guarantee is proposed.

The adapter owns only explicitly handed-off engines and its created physical
sessions. Closing one lease must not close another lease's session. Installation
must be reversible: restore a hook only if still owned by this installation,
report a conflicting later patch, and unwind a partial install. One process-level
registry owns hooks; separate lease contexts carry targets. Its protection
applies to registered calls after installation.

Routing failures carry stable reason/stage, profile, child/generation, driver
mode and one next action. Keep the original connection/SQL exception and cause;
do not classify a driver SQL error as an application bug or rewrite SQL. Preserve
the original setup/test error when cleanup also fails, attaching cleanup details
without DSNs, passwords or query data. Python remains compatible with the current
`>=3.9` declaration: the prototype's Python3.14 `add_note` use needs a compatible
fallback in product code, not a silent minimum-version increase.

## 6. Implementation work and finite acceptance after Human approval

| Reviewable change | Work / maintenance cost | Required evidence |
| --- | --- | --- |
| Routing core and two driver adapters | New optional Python module, normalized profile/option checks, hook ownership, revocable leases, cleanup and structured failures; maintain pinned driver seams | R1/R5/R6/R7, partial-install failure, retirement/connect races, diagnostic redaction, unchanged default driver modes |
| SQLAlchemy adapter | Explicit enrollment and ownership handoff, version/layout check, per-record generation invalidation; optional dependency | R2/R3 including the two closure oracles, concurrent scopes, unknown layouts/custom creators rejected; no global per-test dispose |
| pytest integration and user examples | Early guard configuration plus one function fixture, unwind on collection failure, existing baseline/preparation hooks; maintain early-plugin version compatibility | Subprocess tests importing cold/SQL-opening apps from conftest and test modules, missing/late targets, plugin disabled/manual entry, worker-local xdist, failure teardown |
| Go/example and documentation integration | Keep explicit child-owned pool examples; align current public guides and capability map with actual eligibility | Existing Go Prepare/non-interpolated consumer, first/second test examples, no Go API/runtime change |

This is more than moving the ~220-line prototype into the package. Its cost is
driver/framework lifecycle maintenance and deterministic tests, not a new guest
build. No duration or speed saving has been measured. Optional dependency
loading, supported Python/pytest versions and hook-version refusal belong in
the initial implementation, not post-adoption debt. Do not merge exploratory
history into main as the implementation.

The already-approved closure step ends when the exact15-case control and six
specific defect oracles pass on both supported OSes (allowed explicit Ubuntu C
SKIP retained), with identities and cleanup receipts. Until those results arrive,
R2/R3 remain pending. Unexpected guest/protocol work stops for a separate scope
decision. After closure, report results and the single implementation decision
above to Human Review; do not start production code, main integration,
Qualification or release from CI success alone.

## Basis

- [Approved original design](v06x-connection-routing-design.md), R1–R8 and mutation requirements.
- [Native result review](v06x-connection-routing-human-review.md), fixed evidence and gaps; preserve it as the earlier checkpoint.
- [Workflow design options](v06x-workflow-design-options.md), complementary methods and failure information.
- [Capability map](v06x-capability-map.md) and [north star](v06x-kickoff-notes.md#11-north-star-and-capability-coverage-matrix-ideal-driven), first/second-test benefit and wider coverage.
- [Snapshot product contract](../decisions/snapshot-product-contract.md), consuming source, child isolation and worker-local baseline.
- [Accepted Prepared exceptions](../decisions/prepared-consumer-exceptions.md), unchanged; no exception is relabeled PASS.
- [Existing Python fixtures](../../python/mariamem/pytest_plugin.py) and [packaging](../../python/setup.cfg), current lifecycle, pytest entry point and minimum versions.

Local preparation checks: five receipt-gate unit tests PASS; Python syntax and
runner help PASS;143 local file-link targets exist; public-source/version checks
and `git diff --check` PASS. The unchanged production/guest/generated owners and
accepted-exception document have no diff from the source above. Local checks
do not substitute for the pending two-platform real-guest closure campaign.
