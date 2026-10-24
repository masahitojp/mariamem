"""Fixture API inspired by shibukawa/pgmem (MIT); see bundled notices."""
import pytest

from . import start


def pytest_addoption(parser):
    parser.addini("mariamem_route_profiles", "Registered test routing profile: name = host:port/schema", type="linelist", default=[])
    parser.addini("mariamem_route_drivers", "Opt-in routing drivers", type="args", default=["pymysql"])
    parser.addoption("--mariamem-route", action="append", default=[],
                     help="Register name=host:port/schema before application imports")


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
    early_config._mariamem_routes = registry
    early_config.add_cleanup(registry.close)
    outcome = yield
    if outcome.excinfo is not None:
        try:
            registry.close()
        except BaseException as cleanup:
            _attach_cleanup(outcome.excinfo[1], cleanup)


@pytest.fixture(scope="session")
def mariamem_routes(pytestconfig):
    registry = getattr(pytestconfig, "_mariamem_routes", None)
    if registry is None:
        raise pytest.UsageError("Declare mariamem_route_profiles in pytest configuration before using mariamem_routed.")
    return registry


@pytest.fixture(scope="session")
def mariamem_route_engines():
    """Override with quiescent, test-owned SQLAlchemy engines to enroll."""
    return ()


@pytest.fixture
def mariamem_routed(mariamem_routes, mariamem_route_engines, mariamem_fork):
    profile = next(iter(mariamem_routes.profiles))
    for engine in mariamem_route_engines:
        mariamem_routes.enroll(engine, profile=profile, ownership="test")
    with mariamem_routes.bind(profile, mariamem_fork):
        yield mariamem_fork
    mariamem_fork.wait_disconnected()


@pytest.fixture(scope="session")
def mariamem_options():
    return {}


@pytest.fixture(scope="session")
def mariamem_server(mariamem_options):
    with start(**mariamem_options) as server:
        yield server


@pytest.fixture(scope="session")
def mariamem_snapshot(mariamem_server):
    mariamem_server.wait_disconnected()
    with mariamem_server.snapshot() as saved:
        yield saved


@pytest.fixture
def mariamem_fork(mariamem_snapshot):
    with mariamem_snapshot.fork() as fork:
        yield fork


@pytest.fixture
def mariamem_connection_info(mariamem_fork):
    return mariamem_fork.connection_info()
