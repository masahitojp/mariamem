# Scoped application connections

This is an unreleased source feature, not part of published v0.5.3. It lets a
pytest marker supply an independent MariaDB child while the application keeps
its ordinary driver calls, SQL, commits and rollbacks. Preparation still happens
once through migrations/seed; each test gets its own mutable child.

If your application accepts connection settings or a pool, pass the child's
settings through that construction seam. Routing is useful when existing Python
code already creates its own connections. It is opt-in: `mariamem.start()` and
importing `mariamem.routing` alone do not install hooks or load optional drivers.

## Direct binding

Install the optional `routing-pymysql` extra for PyMySQL1.2.3, `routing-sqlalchemy` for
SQLAlchemy2.0.54 with PyMySQL, or `routing-mysql-connector` for Connector/Python26.7.0.
Select the driver explicitly when installing the router; PyMySQL is the default.
Other versions receive an actionable refusal; explicit child configuration is
available without interception. Existing [Prepared exceptions](decisions/prepared-consumer-exceptions.md)
remain applicable.

```python
from mariamem import routing

# These are the application's ORIGINAL endpoint/schema, without its password.
profile = routing.Profile("127.0.0.1", 3306, "app")
with routing.install(profiles={"app": profile}, drivers=("pymysql",)) as routes:
    import application  # install before code that can create SQL connections
    with baseline.fork() as child:
        with routes.bind("app", child):
            application.create_user()  # ordinary application SQL/driver code
```

Prepare schema `app` in the baseline. The application's requested schema stays
`app`; the child supplies endpoint/credentials. Another or missing schema on
the registered endpoint is refused before dialing. No SQL or schema-name rewrite
is performed. Other endpoints are outside this registered profile. The initial
API supports one named profile; use explicit configuration for additional DBs.

PyMySQL direct calls, saved class aliases, deferred connections and reconnects
are covered. A connection created for one binding cannot reconnect under another
binding; create a new connection. Required TLS, supplied sockets and unresolved
option-file settings receive explicit refusals on their supported entry.
Ordinary driver defaults are retained, including its PREFERRED TLS behavior.

For Connector/Python, use the module factory `mysql.connector.connect` with
explicit TCP settings and `drivers=("mysql.connector",)`. Its normal default
selection and `prepared=True` remain. Built-in pools, option files, DNS/failover
and required TLS need explicit integration rather than silent option loss.
Previously saved factory aliases with advanced options can preprocess work
before our hook; they are outside this initial support boundary. Import/extension
problems are reported as driver availability failures, not guest SQL failures.

## Existing SQLAlchemy engines

```python
routes.register_engine(application.engine, profile="app", ownership="test")
```

Register the default `mysql+pymysql` QueuePool before application activity. The
caller hands off a quiescent, test-owned engine: enrollment may discard its idle
pool, but an active checkout/transaction refuses the transition and is preserved.
Use `routes.create_engine(url, profile="app", **options)` at an application test
factory if a fresh engine is easier. Custom creators/pools require an explicit
adapter/configuration seam. This is not hot takeover of an active application.

The engine object remains the caller's. It stays enrolled across tests; checkout
validates the binding/generation and replaces stale physical sessions. One test's
teardown closes only its owned sessions, never globally disposes another test's
pool. Explicit registry close may dispose remaining idle entries only after all
bindings/checkouts are finished. A timeout/error retains the guard; release the
resources and retry `routes.close()`. Child DB/Snapshot ownership stays with the
caller/fixture. Stop registered application users before removing the guard.

## pytest: configure once, then reuse the same test entry

The installed pytest plugin enables routing only when profiles are configured.
Declare the profile in configuration so protection starts before conftest and
test-module imports, rather than waiting for a function fixture:

```toml
[tool.pytest.ini_options]
mariamem_route_profiles = ["app = 127.0.0.1:3306/app"]
# Optional: ["mysql.connector"] or both tested drivers.
mariamem_route_drivers = ["pymysql"]
```

`--mariamem-route app=127.0.0.1:3306/app` is the equivalent CLI entry. Profiles
contain no credentials. Empty configuration preserves existing behavior.
If plugin auto-loading is disabled, load `-p mariamem.pytest_plugin` explicitly.
Protection begins when this plugin's early guard runs; it cannot undo SQL already
executed by an earlier plugin or application import. A collection-time connection
attempt receives `missing_target`; defer application SQL to a marked test or
its function fixtures. Preparation instead receives explicit DB settings, as
below. Cold engine construction can remain at import.

Prepare `app` once using `mariamem_prepare`. It is a session fixture returning a
callback that receives the source DB. Pass its connection settings explicitly
to migration/seed code; preparation-time automatic connection switching is not
included in0.6.0. Create the application's schema as part of preparation. For
SQLAlchemy, also list the application's quiescent engines once:

```python
# conftest.py
import pytest

@pytest.fixture(scope="session")
def mariamem_prepare():
    def prepare(db):
        migrate(db.connection_info())
        seed(db.connection_info())
        # Finish commits and close preparation connections before returning.
    return prepare

@pytest.fixture(scope="session")
def mariamem_sqlalchemy_engines():
    from application.database import engine
    return (engine,)
```

For a concrete Alembic migration/seed callback with explicit URL configuration,
see [prepare once, test independently](preparing-test-data.md).

Then ordinary application tests use one marker:

```python
import pytest
import application

pytestmark = pytest.mark.shadow_maria

def test_create():
    application.create_user()
    # assert through the application's normal API

def test_update():
    application.update_user()
    # a separate child starts from the same prepared baseline
```

The marker accepts no arguments. Function, class and module use all create one
independent child per test. `fork`, `live` and `prepare` marker options are not
supported. If a test needs direct SQL as well, request `mariamem_app_db`; it is
the exact same child as the marker and `mariamem_fork`, not another DB. Requesting
`mariamem_app_db` alone is also an explicit opt-in to the same binding. Unmarked
tests not requesting it create no routed DB; configured early guards remain.

`mariamem_prepare` defaults to `None` (no-op). An override can prepare through
fixture setup and return `None`, or return a callable taking the source DB.
Other values receive a pytest usage error; callback return values are ignored.
**Returning a cleanup function does not register or execute teardown.** Close
preparation SQL connections inside the callback using context managers or
`try/finally`, before it returns and before Snapshot. The callback's returned
value is not a finalizer.
Preparation runs once per worker in the default Snapshot chain, before the
disconnect wait and consuming capture. A setup/callback failure stops that
chain, creates no Snapshot/child, and preserves the original error while the
source fixture performs cleanup. A callback must close its own SQL resources.

A custom `mariamem_server` still feeds this chain. Overriding `mariamem_snapshot`
replaces its preparation/capture body, so the custom fixture owns those steps.
Overriding `mariamem_fork` owns child construction and can bypass the Snapshot
chain. The marker does not run preparation a second time.

Function-scoped application fixtures run under marker activation. For explicit
setup/teardown dependency ordering, let them request `mariamem_app_db`. Session-
scoped applications cannot acquire a per-test target during their setup: stop or
reconfigure their resources at a suitable boundary. Stable-endpoint/live reset
is a separate design task, not implied by host reuse or this marker.

`mariamem_router` exposes the session registry; `mariamem_app_db` yields that
test's child; `mariamem_sqlalchemy_engines` defaults to no engines. Each xdist worker
owns its registry and existing session baseline. Synchronous DBAPI calls in
asyncio tasks retain task-local selection; async drivers are a separate boundary.
Explicitly propagate context to application threads and join cooperative work
before leaving the binding. Arbitrary tasks are not discovered or forcibly stopped.

## Failure information and cleanup

`routing.RoutingError` provides `code`, `stage`, `action`, `profile`, `child`,
`generation`, `driver`, and a `diagnostics` mapping without DSNs/passwords. Examples
include missing/expired target, schema mismatch, unsupported driver/creator,
active pool, drain timeout and conflicting hooks. The action gives the next step.
Ordinary driver/SQL exceptions retain their type/cause; routing does not label
them application defects or generic MariaDB incompatibility.

Original setup/test exceptions survive a simultaneous cleanup failure. Additional
errors are available in `cleanup_errors` (and notes where Python supports them).
On a failed drain, release checkouts/join work, then retry registry close.
An incomplete cleanup is reported as such. Nested bindings restore their outer
selection; copied contexts are revoked when their binding ends. Registry removal
is explicit and restores only hooks it still owns.
