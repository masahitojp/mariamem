"""Production routing lifecycle tests; fake connections do not imply SQL PASS."""
import contextvars
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys
import threading

import pytest
import pymysql
from mariamem import routing


PROFILE = routing.Profile("127.0.0.1", 3307, "app")
OPTIONS = dict(host=PROFILE.host, port=PROFILE.port, database="app", user="original", password="unit-private-value")


class DB:
    def __init__(self, name="A"):
        self.id, self.closed = name, False

    def connection_info(self):
        return dict(host="127.0.0.1", port=12345, database="test", user="child", password="private-child-value")


class Connection:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


class Record:
    def __init__(self, connection):
        self.dbapi_connection = connection
        self.info = {}

    def invalidate(self):
        self.dbapi_connection.close()
        self.dbapi_connection = None


@pytest.fixture
def routes():
    registry = routing.install(profiles={"app": PROFILE}, cleanup_timeout=.05)
    yield registry
    registry.close()


def connect(registry, connection=None, callback=None):
    connection = connection or Connection()
    registry._connect(connection, callback or (lambda info: None), connection.close, "unit")
    return connection


def test_import_has_no_driver_or_framework_side_effect():
    result = subprocess.run([sys.executable, "-c", "import sys; import mariamem.routing; assert not any(n in sys.modules for n in ('pymysql','mysql.connector','sqlalchemy'))"], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_install_failure_restores_prior_hooks():
    original = pymysql.connections.Connection.connect
    with pytest.raises(routing.RoutingError, match="unsupported_driver"):
        routing.install(profiles={"app": PROFILE}, drivers=("pymysql", "unknown"))
    assert pymysql.connections.Connection.connect is original
    with routing.install(profiles={"app": PROFILE}):
        assert pymysql.connections.Connection.connect is not original
    assert pymysql.connections.Connection.connect is original


def test_hook_conflict_is_reported_and_can_retry(routes, monkeypatch):
    installed = pymysql.connections.Connection.connect
    other = lambda *args, **kwargs: None
    monkeypatch.setattr(pymysql.connections.Connection, "connect", other)
    with pytest.raises(routing.RoutingError, match="hook_conflict"):
        routes.close()
    assert pymysql.connections.Connection.connect is other
    monkeypatch.setattr(pymysql.connections.Connection, "connect", installed)
    routes.close()


@pytest.mark.parametrize("schema", ["other", None, "", b"other"])
def test_schema_mismatch_is_before_dial(routes, monkeypatch, schema):
    monkeypatch.setattr("socket.create_connection", lambda *a, **k: pytest.fail("unexpected dial"))
    with pytest.raises(routing.RoutingError, match="schema_mismatch") as error:
        pymysql.connect(**dict(OPTIONS, database=schema))
    assert "unit-private-value" not in json.dumps(error.value.diagnostics)


def test_preinstall_deferred_tls_and_schema():
    required = pymysql.connect(**OPTIONS, defer_connect=True, ssl={"check_hostname": False})
    wrong = pymysql.connect(**dict(OPTIONS, database="other"), defer_connect=True)
    with routing.install(profiles={"app": PROFILE}):
        with pytest.raises(routing.RoutingError, match="tls_unavailable"):
            required.connect()
        with pytest.raises(routing.RoutingError, match="schema_mismatch"):
            wrong.connect()
    assert required._ssl_required is True and required._sock is None


def test_missing_expired_closed_and_nested_targets(routes):
    with pytest.raises(routing.RoutingError, match="missing_target"):
        pymysql.connect(**OPTIONS)
    a, b = DB(), DB("B")
    with routes.bind("app", a):
        assert routes._target().database is a
        with routes.bind("app", b):
            assert routes._target().database is b
        assert routes._target().database is a
        copied = contextvars.copy_context()
    with pytest.raises(routing.RoutingError, match="expired_target"):
        copied.run(lambda: connect(routes))
    a.closed = True
    with pytest.raises(routing.RoutingError, match="closed_target"):
        with routes.bind("app", a):
            pytest.fail("closed target admitted")


def test_connect_failure_keeps_provenance_and_original_error(routes):
    connection = Connection()
    original = OSError("driver original")
    def broken(info):
        raise original
    with routes.bind("app", DB()):
        with pytest.raises(OSError) as error:
            connect(routes, connection, broken)
        assert error.value is original
    with routes.bind("app", DB("B")):
        with pytest.raises(routing.RoutingError, match="held_connection"):
            connect(routes, connection)


def test_slow_connection_is_closed_if_retirement_wins(routes):
    entered, release = threading.Event(), threading.Event()
    errors = []
    connection = Connection()
    def slow(info):
        entered.set()
        assert release.wait(2)
    def work():
        try:
            connect(routes, connection, slow)
        except BaseException as error:
            errors.append(error)
    with routes.bind("app", DB()) as lease:
        ctx = contextvars.copy_context()
        worker = threading.Thread(target=ctx.run, args=(work,))
        worker.start()
        assert entered.wait(2)
        with lease.condition:
            lease.live = False
        release.set()
    worker.join(2)
    assert not worker.is_alive()
    assert len(errors) == 1 and errors[0].code == "expired_target"
    assert connection.closed


def test_drain_timeout_preserves_original_error_and_close_retry(routes):
    db = DB()
    original = ValueError("test failed")
    with pytest.raises(ValueError) as error:
        with routes.bind("app", db):
            connection = connect(routes)
            resource = connection._mariamem_resource
            resource.checked_out = True
            raise original
    assert error.value is original
    assert original.cleanup_errors[0].code == "drain_timeout"
    assert not db.closed and not connection.closed
    with pytest.raises(routing.RoutingError, match="drain_timeout"):
        routes.close()
    assert not routes._closed
    with resource.lease.condition:
        resource.checked_out = False
        resource.lease.condition.notify_all()
    routes.close()
    assert connection.closed and routes._closed


def test_active_scope_prevents_registry_close(routes):
    with routes.bind("app", DB()):
        with pytest.raises(routing.RoutingError, match="active_scope"):
            routes.close()


def test_pool_disposal_authority_and_sibling_survival(routes):
    from sqlalchemy import create_engine
    engine = create_engine("mysql+pymysql://original@127.0.0.1:3307/app")
    disposals = []
    original_dispose = engine.dispose
    def dispose(*args, **kwargs):
        disposals.append(1)
        original_dispose(*args, **kwargs)
    engine.dispose = dispose
    routes.enroll(engine, profile="app", ownership="test")
    assert len(disposals) == 1
    with routes.bind("app", DB()):
        a = connect(routes); ar = Record(a)
        engine.pool.dispatch.checkout(a, ar, None)
        with routes.bind("app", DB("B")):
            b = connect(routes); br = Record(b)
            engine.pool.dispatch.checkout(b, br, None)
            engine.pool.dispatch.checkin(b, br)
        assert b.closed and not a.closed and len(disposals) == 1
        # Invalidation can clear record.info before checkin(None).
        engine.pool.dispatch.invalidate(a, ar, OSError("disconnect"))
        ar.info.clear()
        engine.pool.dispatch.checkin(None, ar)
    assert a.closed and len(disposals) == 1
    routes.close()
    assert len(disposals) == 2


def test_pool_active_and_custom_creator_refuse(routes, monkeypatch):
    from sqlalchemy import create_engine
    engine = create_engine("mysql+pymysql://original@127.0.0.1:3307/app")
    original = engine.pool.checkedout
    monkeypatch.setattr(engine.pool, "checkedout", lambda: 1)
    with pytest.raises(routing.RoutingError, match="active_pool"):
        routes.enroll(engine, profile="app", ownership="test")
    assert engine.pool is not None
    monkeypatch.setattr(engine.pool, "checkedout", original)
    with pytest.raises(routing.RoutingError, match="ownership_required"):
        routes.enroll(engine, profile="app", ownership="application")
    calls = []
    custom = create_engine("mysql+pymysql://original@127.0.0.1:3307/app", creator=lambda: calls.append(1))
    with pytest.raises(routing.RoutingError, match="custom_creator"):
        routes.enroll(custom, profile="app", ownership="test")
    assert not calls
    engine.dispose(); custom.dispose()


def test_unrequested_framework_is_not_imported_by_driver_install():
    code = "from mariamem import routing; import sys; r=routing.install(profiles={'app':routing.Profile('127.0.0.1',3307,'app')}); assert 'sqlalchemy' not in sys.modules; r.close()"
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
