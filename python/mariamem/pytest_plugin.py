"""Fixture API inspired by shibukawa/pgmem (MIT); see bundled notices."""
import pytest

from . import start, PrepareCommand
from ._prepare import _run_command
from ._pytest_owner import _Owner, _owner


def pytest_addoption(parser):
    parser.addini("mariamem_route_profiles", "Registered test routing profile: name = host:port/schema", type="linelist", default=[])
    parser.addini("mariamem_route_drivers", "Opt-in routing drivers", type="args", default=["pymysql"])
    parser.addoption("--mariamem-route", action="append", default=[],
                     help="Register name=host:port/schema before application imports")


def pytest_configure(config):
    config._mariamem_entry_owner = _Owner()
    config.addinivalue_line("markers", "shadow_maria: use an independent DB and redirect registered application connections")



@pytest.hookimpl(hookwrapper=True)
def pytest_fixture_setup(fixturedef, request):
    outcome = yield
    # Observe only the named preparation boundary; never replace its result/error.
    if fixturedef.argname == 'mariamem_prepare' and outcome.excinfo is not None:
        _owner(request.config).fail('prepare', outcome.excinfo[1])


def pytest_sessionfinish(session):
    # xdist workers have no terminal reporter. Send bounded owner state, not
    # exception objects or command output, for the master's final summary.
    if hasattr(session.config, 'workeroutput'):
        session.config.workeroutput['mariamem_entry'] = _owner(session.config).summary()


@pytest.hookimpl(optionalhook=True)
def pytest_testnodedown(node, error):
    summary = node.workeroutput.get('mariamem_entry')
    if summary is not None:
        config = node.config
        if not hasattr(config, '_mariamem_entry_workers'):
            config._mariamem_entry_workers = {}
        config._mariamem_entry_workers[node.gateway.id] = summary


def pytest_terminal_summary(terminalreporter):
    config = terminalreporter.config
    summaries = {'local': _owner(config).summary(), **getattr(config, '_mariamem_entry_workers', {})}
    summaries = {name: value for name, value in summaries.items() if value['records']}
    if summaries:
        terminalreporter.section('mariamem entry failures')
        for name, value in summaries.items():
            for stage, error_type in value['records']:
                terminalreporter.write_line(f'{name} {stage}: {error_type}; original error retained in pytest reports')
            cleanup = ('unconfirmed; inspect original cleanup/capture errors'
                       if value['uncertain'] or value['active'] else 'entry-owned finalizers completed')
            terminalreporter.write_line(f'{name}: admission=stopped for this worker; cleanup=' + cleanup)


def pytest_collection_modifyitems(items):
    for item in items:
        for marker in item.iter_markers("shadow_maria"):
            if marker.args or marker.kwargs:
                raise pytest.UsageError("shadow_maria accepts no arguments; prepare via mariamem_prepare. live/shared modes are not implemented.")


@pytest.fixture(autouse=True)
def _shadow_maria(request):
    if request.node.get_closest_marker("shadow_maria") is not None:
        request.getfixturevalue("mariamem_app_db")
    yield


def _profile_definitions(lines):
    from urllib.parse import unquote, urlsplit
    from .routing import Profile
    profiles = {}
    for line in lines:
        name, separator, endpoint = line.partition("=")
        name = name.strip()
        if not separator or not name or name in profiles:
            raise ValueError("use one unique name = host:port/schema profile")
        try:
            value = urlsplit("//" + endpoint.strip())
            if value.username is not None or value.password is not None or value.query or value.fragment:
                raise ValueError("credentials/options are not allowed")
            profiles[name] = Profile(value.hostname, value.port, unquote(value.path[1:], errors="strict"))
        except (ValueError, UnicodeError):
            raise ValueError("Use host:port/schema without credentials or extra options.") from None
    return profiles


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_load_initial_conftests(early_config, parser, args):
    lines = list(early_config.getini("mariamem_route_profiles"))
    lines.extend(getattr(early_config.known_args_namespace, "mariamem_route", []))
    if not lines:
        yield
        return
    from .routing import install, _attach_cleanup
    try:
        registry = install(profiles=_profile_definitions(lines),
                           drivers=tuple(early_config.getini("mariamem_route_drivers")))
    except (ValueError, TypeError, RuntimeError) as error:
        # Do not include rejected config text: it might contain credentials.
        raise pytest.UsageError("mariamem routing could not start; use name=host:port/schema and a tested driver. Inspect the chained cause.") from error
    early_config._mariamem_router = registry
    early_config.add_cleanup(registry.close)
    outcome = yield
    if outcome.excinfo is not None:
        try:
            registry.close()
        except BaseException as cleanup:
            _attach_cleanup(outcome.excinfo[1], cleanup)


@pytest.fixture(scope="session")
def mariamem_router(pytestconfig):
    registry = getattr(pytestconfig, "_mariamem_router", None)
    if registry is None:
        raise pytest.UsageError("Declare mariamem_route_profiles in pytest configuration before using shadow_maria or mariamem_app_db.")
    return registry


@pytest.fixture(scope="session")
def mariamem_sqlalchemy_engines():
    """Override with quiescent, test-owned SQLAlchemy engines to register."""
    return ()


@pytest.fixture
def mariamem_app_db(request, mariamem_router, mariamem_sqlalchemy_engines, mariamem_fork):
    owner = _owner(request.config)
    profile = next(iter(mariamem_router.profiles))
    with owner.operation('routing'):
        for engine in mariamem_sqlalchemy_engines:
            mariamem_router.register_engine(engine, profile=profile, ownership="test")
    with owner.context(lambda: mariamem_router.bind(profile, mariamem_fork), 'routing'):
        yield mariamem_fork
    with owner.operation('routing disconnect', cleanup=True):
        mariamem_fork.wait_disconnected()


@pytest.fixture(scope="session")
def mariamem_options():
    return {}


@pytest.fixture(scope="session")
def mariamem_server(request, mariamem_options):
    owner = _owner(request.config)
    owner.guard()
    with owner.context(lambda: start(**mariamem_options), 'start') as server:
        yield server


@pytest.fixture(scope="session")
def mariamem_prepare():
    """Return None, a callback accepting the source DB, or PrepareCommand."""
    return None


@pytest.fixture(scope="session")
def mariamem_snapshot(request, mariamem_server, mariamem_prepare):
    owner = _owner(request.config)
    owner.guard()
    with owner.operation('prepare'):
        if isinstance(mariamem_prepare, PrepareCommand):
            _run_command(mariamem_prepare, mariamem_server, request.config.rootpath)
        elif mariamem_prepare is not None:
            if not callable(mariamem_prepare):
                raise pytest.UsageError("mariamem_prepare must return None, a callable accepting the preparation DB, or PrepareCommand.")
            mariamem_prepare(mariamem_server)  # Existing return values remain ignored.
    with owner.operation('disconnect'):
        mariamem_server.wait_disconnected()
    with owner.context(lambda: mariamem_server.snapshot(), 'capture') as saved:
        yield saved


@pytest.fixture
def mariamem_fork(request, mariamem_snapshot):
    owner = _owner(request.config)
    owner.guard()
    with owner.context(mariamem_snapshot.fork, 'acquire') as fork:
        yield fork


@pytest.fixture
def mariamem_connection_info(mariamem_fork):
    return mariamem_fork.connection_info()
