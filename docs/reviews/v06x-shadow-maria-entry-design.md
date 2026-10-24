# shadow_maria — marker and preparation entry proposal

2026-10-24. Design basis source_commit:
`5651e23d8a6cc57ecaac0c45228da6b4108ed789` on `feat/connection-routing`.
Status: **Human-approved entry/naming direction; implementation and verification
outstanding.** On2026-10-24 the Human accepted the recommended surface below.
This is approval to proceed with that direction, not main adoption, Qualification
or release approval. The old fixture implementation remains the tested candidate.

## Human Review — entry direction accepted

Decision answered: adopt `@pytest.mark.shadow_maria` as the normal application-test
entry, provide direct DB access and explicit preparation as separate fixtures,
and use the approved names below. Keep the existing explicit `mariamem_fork`
entry for callers that supply connection settings themselves.

The decisive benefit is that users can express "run this application test against
an independent MariaDB" without learning the Fork/binding dependency chain.
The strongest objection is that activation still needs original-profile settings,
pool ownership handoff and test-compatible application lifetimes. The approved
entry does not remove these requirements or promise arbitrary live takeover.
The Human assigned live behavior to a separate task. Preparation-time automatic
routing is excluded from0.6.0 and retained for0.6.x reconsideration.

The next gate is main adoption after implementing and verifying this approved
surface. There is no second request to approve the same naming direction.

## Human decision — preparation routing excluded from0.6.0

On2026-10-24, after clarification of the difference from the inspected pgmem
implementation, the Human decided **not to include automatic connection
switching during preparation in0.6.0**. This supersedes the earlier provisional
approval made before that difference was understood. No preparation-routing
implementation was made under that provisional approval.

For0.6.0, preparation follows the inspected pgmem pattern: provide the
preparation DB's connection settings to migration/seed code explicitly. Finish
committed preparation and close its connections before creating the consuming
Snapshot. Each later test gets an independent child; `shadow_maria` selects
that child for registered application connections during the test, not during
preparation. The callback entry is `mariamem_prepare`, described below.

The early registered-profile guard remains active: absence of a preparation
binding must never mean fallback to the original endpoint. Preparation code
uses explicitly supplied DB settings rather than expecting registered original
application settings to be redirected. This is a supported-path boundary, not
permission to remove the guard.

### Reconsider preparation routing in0.6.x

Retain the following as a separate future decision, not approved implementation:
allow existing migration/seed code that opens registered application connections
to run under a preparation binding without accepting explicit DB settings.
Compare the benefit over explicit settings with lifecycle/pool ownership and
maintenance costs. Specify schema bootstrap, preparation-to-test generation
changes, retirement/drain, original-error retention, zero original-endpoint
fallback, and refusal to create a baseline after preparation/cleanup failure.
Return to Human Review before adopting that extension in0.6.x. It is separate
from the live task and is not automatically included in a later patch release.

## Human decision — live is a separate task

On2026-10-24 the Human decided to examine live behavior in a separate task.
Whether to include it in0.6.0 is still a scope decision, informed by the required
internal changes; it is not automatically deferred to a later version.

The current public API does not offer stable-endpoint baseline restoration.
That is a current capability gap, not a finding that live behavior is impossible.
A bounded design investigation must distinguish keeping the application alive
while rebuilding/rebinding its DB resources from preserving the same endpoint
and existing connections. Define which resources survive, how old transactions
and sessions end, and whether each test starts from the baseline. Existing host
reuse and driver/pool generation checks alone do not establish this workflow.
Do not add `live=True` until its meaning and verification have been decided.

### Live baseline and pending task

Here, **baseline means the DB contents each test should start with**. It does
not necessarily mean an empty database, and it does not imply restoring running
application objects, connections or transactions.

| How the initial state is prepared | Baseline contents |
| --- | --- |
| Fresh start, no application preparation | Immediately after mariamem startup: no application tables or seed data yet; internal MariaDB structures may exist |
| Fresh start followed by migrations/seed | The completed preparation state, with its schema and common data |
| Snapshot followed by Fork | The contents fixed when that Snapshot was taken |

For example, migrate and insert common users, then capture a Snapshot. Test A
may add a user and commit. Test B must start with the common users again,
without A's added user. Normal Fork already provides independent children from
that Snapshot. A proposed live mode must define how to provide the same starting
contents while retaining the selected application resources; it must not silently
share the previous test's changes or substitute a rollback-only test wrapper.

The separate live task must compare these resource boundaries explicitly:

| What survives between tests | Question to resolve |
| --- | --- |
| Application stays running; DB resources may be replaced | Can its connections/pool be retired and rebound to a new independent child? |
| Application and connection address stay the same | Can the DB return to the selected baseline, and how do old sessions end or reconnect? |
| Existing connections also stay usable | What happens to transactions, temporary tables, session variables and prepared statements? This is an additional requirement, not implied by a stable address |

Task output: a proposed live contract, feasible implementation alternatives,
required internal changes and bounded isolation/failure verification. Identify
when the baseline is fixed, including applications that migrate during startup,
and whether concurrent tests need separate live instances. Return to Human
Review to decide scope and inclusion in0.6.0. No implementation is authorized
by recording this task, and no current reset/live support is claimed.

## Reference: what pgmem actually exposes

Inspected public source, not a pgmem runtime test:
[pytest_plugin.py at3433a40bd4167daea2d8e364666bd5fcf18ef654](https://github.com/shibukawa/pgmem/blob/3433a40bd4167daea2d8e364666bd5fcf18ef654/packages/python/src/pgmem/pytest_plugin.py).

| Entry | Meaning in that source |
| --- | --- |
| `@pytest.mark.shadow_pg` | `fork=True, live=False`; uses a function child and driver/pool hooks |
| `shadow_pg(fork=False)` | Uses the session shared child; no per-test reset in the shadow handler |
| `shadow_pg(live=True)` | Stable endpoint; `pgmem_live_db` restores a baseline before each sequential test |
| `pgmem_prepare` | Separate session fixture returning a preparation callback, not a shadow marker argument |
| `pgmem_live_baseline.capture()` | Includes changes made while the application starts in the baseline restored later |
| `pgmem_dataset(name)` | Separate selection marker for live baseline datasets |

`live=True, fork=False` is rejected. These are different lifecycle choices,
not just performance knobs. The pgmem example does not establish that mariamem
has equivalent support.

## Approved public surface — not yet implemented

| Entry | Meaning |
| --- | --- |
| `@pytest.mark.shadow_maria` | No arguments; independent child per test, registered application connections use it, ordinary commit/rollback |
| `mariamem_app_db` | Optional direct access to that same child; marker plus fixture must not create two children or nested bindings |
| `mariamem_prepare` | Session fixture returning a preparation callback; receives the source DB, runs once per worker before Snapshot; migration/seed uses explicit DB settings |
| `mariamem_fork` | Existing explicit child acquisition without automatic application binding; retained |
| `mariamem_router` | Session fixture exposing the routing controller for advanced operations; replaces candidate `mariamem_routes` |
| `mariamem_sqlalchemy_engines` | Override with quiescent, test-owned SQLAlchemy engines to register; replaces candidate `mariamem_route_engines` |
| `routing.Router` | Controller returned by `routing.install()`; replaces candidate `Registry` |
| `Router.register_engine(...)` | Explicit engine/pool administration handoff, preserving `ownership="test"`; replaces candidate `enroll(...)` |
| `routing-pymysql` | Installation extra for the pinned PyMySQL route; replaces candidate `routing` extra |
| `routing-sqlalchemy` | Installation extra for SQLAlchemy/PyMySQL; retained |
| `routing-mysql-connector` | Installation extra for Connector/Python; replaces candidate `routing-connector` |

The marker is the normal entry; `mariamem_routed` is not retained as a competing
public entry. Superseded, unreleased candidate names need no compatibility
aliases. Published existing APIs/fixtures are retained. `routing.Profile`,
`routing.install`, `bind`, `create_engine`, `close`, `RoutingError` and the
profile/driver settings (`mariamem_route_profiles`, `mariamem_route_drivers`,
`--mariamem-route`) are unchanged by this naming decision. Historical receipts
retain the actual old names used by their source; do not rewrite them.

Intended usage, pending implementation:

```python
@pytest.fixture(scope="session")
def mariamem_prepare():
    def prepare(db):
        migrate(db.connection_info())
        seed(db.connection_info())
        # Preparation must commit and close its connections before returning.
    return prepare

@pytest.mark.shadow_maria
def test_create_user():
    application.create_user()

@pytest.mark.shadow_maria
def test_update_user(mariamem_app_db):
    application.update_user()
    # Direct assertions may use this same test's DB connection settings.
```

The marker also supports class/module application with independent children for
each test. Execution/cleanup ordering and existing fixture overrides are
implementation responsibilities under this contract, not new product decisions.

Static profile/driver registration still precedes application imports. The
marker activates the per-test target; it cannot retroactively protect import SQL.
For0.6.0, preparation callbacks receive the source DB and explicitly pass its
connection settings to migration/seed code. They do not run under an automatic
preparation binding; that extension is reserved for0.6.x reconsideration.
Source schema creation, callback failure/cleanup and existing fixture override
ordering must be specified before implementing this convenience entry.

## Marker options and separate work

- `prepare=...`: not a marker argument; use the approved separate fixture.
  Multiple datasets or per-test preparation may later justify a selector, but
  do not overload a boolean with callback/name/lifecycle meanings.
- `fork=True`: redundant with the independent-test contract; not accepted.
- `fork=False`: shares mutable state across tests. It changes isolation and
  order-dependence; requires an explicit product decision rather than an alias
  for skipping an expensive operation.
- `live=True`: useful for session-lived applications and pools. Needs stable
  endpoint, baseline restoration, SQL-session/transaction invalidation and
  failure semantics. Current public mariamem has no DB reset API and successful
  Snapshot consumes its source. Endpoint reuse alone cannot provide this mode.
- Profile/dataset selection: one profile is supported today. Adding a marker
  parameter must not imply multiple-profile/dataset support already exists.
- Unknown arguments must produce a clear pytest usage error; no ignored flags
  or fallback to a shared DB.

## Implementation contract — reviewed gaps closed before coding

The Human authorized implementation and explicitly changed supported Python to
**3.11+**; remove3.9/3.10 from advertised support and package metadata as well as
future CI. Historical receipts remain historical. Minimum-version PASS still
requires execution on3.11; the old3.9 run is not a substitute.

- `mariamem_prepare` defaults to `None` (no-op). An override may do preparation
  during fixture setup and return `None`, or return a callable invoked once
  with `mariamem_server`. Other values raise an actionable pytest usage error.
  The callback's return value is unused. It must finish commits and close its
  connections before returning. A setup/callback error propagates unchanged;
  Snapshot creation and child admission do not occur. The session server's
  existing context manager remains responsible for cleanup.
- The default dependency chain is server -> prepare callback -> disconnect wait
  -> Snapshot -> per-test Fork -> routing binding. A custom `mariamem_server`
  still participates. A custom `mariamem_snapshot` owns its own preparation;
  it bypasses the default Snapshot body. A custom `mariamem_fork` owns child
  construction and may bypass the Snapshot chain. Document these pytest
  override boundaries; do not invoke preparation again from the marker.
- A function-scoped autouse dispatcher activates only marked tests and requests
  `mariamem_app_db`. That single cached fixture uses `mariamem_fork`, registers
  configured engines and binds once. Marker plus explicit fixture access yields
  the identical object/binding. Requesting `mariamem_app_db` without a marker is
  also an explicit opt-in and performs the same operation. Class/module markers
  apply per test; they never change child scope to class/module.
- Reject every positional/keyword marker argument before running tests; do not
  ignore `fork`, `live`, `prepare`, profile or other misspellings. Unmarked tests
  not requesting the DB fixture start no child/routing binding. Configured early
  guards still protect imports independently of marker activation.
- Per-test application fixtures run inside marker activation; fixtures needing
  explicit teardown ordering may depend on `mariamem_app_db`. Session-scoped
  application connection activity has no per-test target and is not silently
  moved into a test. Drain owned resources before child Close. Keep initial and
  final engine-disposal authority unchanged.

## Scope and verification boundary

[CI40045368302](https://github.com/masahitojp/mariamem/actions/runs/40045368302)
passed on source_commit `0698698eb77bbb4df91aea0d83f62e901b711d77`: both native
OSes passed17 control cases, six exact injected defects and4 pytest tests with
two workers. Ubuntu explicit Connector C retained its permitted SKIP; default/pure
executed, and macOS default/pure/C executed. These results verify the previous
fixture entry, not the approved marker/preparation surface. They remain evidence
for the unchanged routing core. Marker implementation needs direct/class/module use,
strict argument rejection, early guard preservation, application-fixture setup
and teardown ordering, no-marker inactivity, same-child fixture access and the
existing two-worker/SQL failure oracles. Preparation needs once-per-worker,
first/second child seed independence and failure cleanup coverage using explicit
preparation DB settings. Preserve the early guard, zero original-endpoint
contacts and refusal to capture/admit children after failed preparation/cleanup.
Automatic preparation-routing oracles belong to the0.6.x reconsideration above;
no such behavior is claimed for0.6.0. Python3.9/3.10
are no longer future verification targets; use3.11 and the current selected3.14.

This documentation update changes no runtime/guest/generated code. Implementation
of the approved entry is next; main merge, Qualification and release remain
separate decisions. The approved [Snapshot contract](../decisions/snapshot-product-contract.md)
and [routing contract](../decisions/connection-routing-contract.md) remain the basis.
