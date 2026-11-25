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
    result = subprocess.run([sys.executable, "-c", "import sys; import mariamem.routing; assert not any(n in sys.modules for n in ('pymysql','mysql.connector','MySQLdb','sqlalchemy'))"], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_install_failure_restores_prior_hooks():
    original = pymysql.connections.Connection.connect
    with pytest.raises(routing.RoutingError, match="unsupported_driver"):
        routing.install(profiles={"app": PROFILE}, drivers=("pymysql", "unknown"))
    assert pymysql.connections.Connection.connect is original
    with routing.install(profiles={"app": PROFILE}):
        assert pymysql.connections.Connection.connect is not original
    assert pymysql.connections.Connection.connect is original


def test_uninstalled_registry_cannot_present_a_binding_as_active():
    registry = routing.Router({"app": PROFILE}, ("pymysql",), .05)
    with pytest.raises(routing.RoutingError, match="uninstalled_registry"):
        with registry:
            pytest.fail("uninstalled guard was presented as active")
    with pytest.raises(routing.RoutingError, match="uninstalled_registry"):
        with registry.bind("app", DB()):
            pytest.fail("uninstalled guard admitted a binding")
    registry.close()


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
    assert getattr(required, "_ssl_required", required.ssl) is True and required._sock is None


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
    with pytest.raises(routing.RoutingError, match="closed_registry"):
        with routes.bind("app", DB("B")):
            pytest.fail("failed close admitted a new binding")
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
    routes.register_engine(engine, profile="app", ownership="test")
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
        routes.register_engine(engine, profile="app", ownership="test")
    assert engine.pool is not None
    monkeypatch.setattr(engine.pool, "checkedout", original)
    with pytest.raises(routing.RoutingError, match="ownership_required"):
        routes.register_engine(engine, profile="app", ownership="application")
    calls = []
    custom = create_engine("mysql+pymysql://original@127.0.0.1:3307/app", creator=lambda: calls.append(1))
    with pytest.raises(routing.RoutingError, match="custom_creator"):
        routes.register_engine(custom, profile="app", ownership="test")
    assert not calls
    engine.dispose(); custom.dispose()


def test_unrequested_framework_is_not_imported_by_driver_install():
    code = "from mariamem import routing; import sys; r=routing.install(profiles={'app':routing.Profile('127.0.0.1',3307,'app')}); assert 'sqlalchemy' not in sys.modules; r.close()"
    result = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_unused_binding_warns_after_draining_and_resets_target(routes):
    with pytest.warns(routing.UnusedRoutingWarning, match='routed 0 connections'):
        with routes.bind('app', DB()) as lease:
            assert lease.routed == 0
    assert not lease.live and not routes._leases
    with pytest.raises(routing.RoutingError, match='missing_target'):
        connect(routes)


def test_used_binding_does_not_warn(routes):
    import warnings
    with warnings.catch_warnings(record=True) as seen:
        warnings.simplefilter('always', routing.UnusedRoutingWarning)
        with routes.bind('app', DB()) as lease:
            connection = connect(routes)
            assert lease.routed == 1
    assert connection.closed
    assert not any(isinstance(w.message, routing.UnusedRoutingWarning) for w in seen)


def test_unused_warning_as_error_still_retires_binding(routes):
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter('error', routing.UnusedRoutingWarning)
        with pytest.raises(routing.UnusedRoutingWarning):
            with routes.bind('app', DB()) as lease:
                pass
    assert not lease.live and not routes._leases
    with pytest.raises(routing.RoutingError, match='missing_target'):
        connect(routes)


def test_unused_warning_never_masks_primary_or_cleanup_failure(routes, monkeypatch):
    import warnings
    with warnings.catch_warnings():
        warnings.simplefilter('error', routing.UnusedRoutingWarning)
        original = ValueError('original body failure')
        with pytest.raises(ValueError) as caught:
            with routes.bind('app', DB()):
                raise original
        assert caught.value is original
        drain = routes._drain
        def fail(lease):
            raise OSError('original drain failure')
        monkeypatch.setattr(routes, '_drain', fail)
        with pytest.raises(OSError, match='original drain failure'):
            with routes.bind('app', DB()) as failed_lease:
                pass
        monkeypatch.setattr(routes, '_drain', drain)
        drain(failed_lease)


def test_version_parser_boundaries_and_rejections():
    from mariamem._routing_drivers import _parse_stable_version
    assert _parse_stable_version("1.1.0") == (1, 1, 0)
    assert _parse_stable_version("1.2.4") == (1, 2, 4)
    assert _parse_stable_version("2.0") == (2, 0, 0)
    assert _parse_stable_version("2.0.5.post1") == (2, 0, 5)
    assert _parse_stable_version("2.1.9") == (2, 1, 9)
    assert _parse_stable_version("9.0.0") == (9, 0, 0)
    assert _parse_stable_version("26.10.0") == (26, 10, 0)
    for bad in ("", "abc", "2.0.0rc1", "2.0.0b1", "2.0.0a1", "1.2.3.dev0", "1!1.2.3", "1.2.3+local", None):
        assert _parse_stable_version(bad) is None


@pytest.mark.parametrize("bad_version", ["1.0.3", "2.0.0", "1.2.0rc1", "1!1.2.3", "invalid"])
def test_pymysql_version_range_rejects_out_of_range_and_prerelease(monkeypatch, bad_version):
    original_connect = pymysql.connections.Connection.connect
    monkeypatch.setattr(importlib.metadata, "version", lambda pkg: bad_version if pkg == "PyMySQL" else "2.0.54")
    with pytest.raises(routing.RoutingError, match="unsupported_driver_version"):
        routing.install(profiles={"app": PROFILE}, drivers=("pymysql",))
    assert pymysql.connections.Connection.connect is original_connect


@pytest.mark.parametrize("good_version", ["1.1.0", "1.1.3", "1.2.3", "1.2.4", "1.2.4.post1"])
def test_pymysql_version_range_accepts_compatible_versions(monkeypatch, good_version):
    real_version = importlib.metadata.version
    monkeypatch.setattr(importlib.metadata, "version", lambda pkg: good_version if pkg == "PyMySQL" else real_version(pkg))
    with routing.install(profiles={"app": PROFILE}, drivers=("pymysql",)):
        pass


@pytest.mark.parametrize("bad_version", ["1.4.54", "2.2.0", "2.1.0b1", "1!2.0.54", "invalid"])
def test_sqlalchemy_version_range_rejects_out_of_range_and_prerelease(routes, monkeypatch, bad_version):
    from sqlalchemy import create_engine
    real_version = importlib.metadata.version
    engine = create_engine("mysql+pymysql://original@127.0.0.1:3307/app")
    try:
        monkeypatch.setattr(importlib.metadata, "version", lambda pkg: bad_version if pkg == "SQLAlchemy" else real_version(pkg))
        with pytest.raises(routing.RoutingError, match="unsupported_adapter_version"):
            routes.register_engine(engine, profile="app", ownership="test")
        with pytest.raises(routing.RoutingError, match="unsupported_adapter_version"):
            routes.create_engine("mysql+pymysql://original@127.0.0.1:3307/app", profile="app")
    finally:
        engine.dispose()


@pytest.mark.parametrize("good_version", ["2.0.0", "2.0.5.post1", "2.0.54", "2.1.0", "2.1.9"])
def test_sqlalchemy_version_range_accepts_compatible_versions(routes, monkeypatch, good_version):
    from sqlalchemy import create_engine
    real_version = importlib.metadata.version
    monkeypatch.setattr(importlib.metadata, "version", lambda pkg: good_version if pkg == "SQLAlchemy" else real_version(pkg))
    engine = create_engine("mysql+pymysql://original@127.0.0.1:3307/app")
    try:
        routes.register_engine(engine, profile="app", ownership="test")
    finally:
        engine.dispose()


@pytest.mark.parametrize("bad_version", ["8.4.0", "27.0.0", "26.10.0a1", "1!26.7.0"])
def test_connector_version_range_rejects_and_rolls_back_prior_hooks(monkeypatch, bad_version):
    original_connect = pymysql.connections.Connection.connect
    real_version = importlib.metadata.version
    def fake_version(pkg):
        if pkg == "mysql-connector-python":
            return bad_version
        return real_version(pkg)
    monkeypatch.setattr(importlib.metadata, "version", fake_version)
    with pytest.raises(routing.RoutingError, match="unsupported_driver_version"):
        routing.install(profiles={"app": PROFILE}, drivers=("pymysql", "mysql.connector"))
    assert pymysql.connections.Connection.connect is original_connect


def test_pymysql_1_1_style_connection_without_ssl_required_attribute(monkeypatch):
    connected = []
    class LegacyConnection:
        def __init__(self, *, host, port, db, ssl=False):
            self.host, self.port, self.db = host, port, db
            self.user, self.password = "original", b"unit-private-value"
            self.unix_socket = None
            self.ssl = ssl
            self.closed = False
        def connect(self, sock=None):
            connected.append((self.host, self.port, self.user, self.password))
        def close(self):
            self.closed = True

    fake_connections = type("FakeConnections", (), {"Connection": LegacyConnection})
    fake_err = type("FakeErr", (), {"Error": RuntimeError})
    fake_pymysql = type("FakePyMySQL", (), {"connections": fake_connections, "err": fake_err})
    real_import = importlib.import_module
    monkeypatch.setattr(importlib.metadata, "version", lambda pkg: "1.1.3" if pkg == "PyMySQL" else "2.0.54")
    monkeypatch.setattr(importlib, "import_module", lambda name: fake_pymysql if name == "pymysql" else real_import(name))

    with routing.install(profiles={"app": PROFILE}, drivers=("pymysql",)) as reg:
        with reg.bind("app", DB()):
            plain = LegacyConnection(host="127.0.0.1", port=3307, db="app", ssl=False)
            assert not hasattr(plain, "_ssl_required")
            plain.connect()
            assert connected == [("127.0.0.1", 12345, "child", b"private-child-value")]
            tls = LegacyConnection(host="127.0.0.1", port=3307, db="app", ssl=True)
            assert not hasattr(tls, "_ssl_required")
            with pytest.raises(routing.RoutingError, match="tls_unavailable"):
                tls.connect()
        assert plain.closed


def test_missing_hook_target_refuses_and_rolls_back(monkeypatch):
    original_connect = pymysql.connections.Connection.connect
    fake_abstracts = type("FakeAbstracts", (), {"MySQLConnectionAbstract": type("Abs", (), {})})
    fake_connector = type("FakeConnector", (), {"connect": lambda **kw: None})
    real_import = importlib.import_module
    real_version = importlib.metadata.version

    def fake_version(pkg):
        return "26.10.0" if pkg == "mysql-connector-python" else real_version(pkg)

    def fake_import(name):
        if name == "mysql.connector":
            return fake_connector
        if name == "mysql.connector.abstracts":
            return fake_abstracts
        return real_import(name)

    monkeypatch.setattr(importlib.metadata, "version", fake_version)
    monkeypatch.setattr(importlib, "import_module", fake_import)
    with pytest.raises(routing.RoutingError, match="unsupported_driver_version"):
        routing.install(profiles={"app": PROFILE}, drivers=("pymysql", "mysql.connector"))
    assert pymysql.connections.Connection.connect is original_connect


def _make_fake_mysqldb(monkeypatch, *, version="2.2.7", fail_connect=None):
    import types
    calls = []

    class ProgrammingError(Exception):
        pass

    class FakeMySQLdbConnection:
        def __init__(self, *args, **kwargs):
            # Mimic mysqlclient's _mysql.c: self.open becomes True before mysql_real_connect.
            self.open = True
            self.close_calls = 0
            if fail_connect is not None and fail_connect(args, kwargs):
                raise OSError("connect failed")
            calls.append((args, dict(kwargs)))
            self.connected_kwargs = dict(kwargs)

        def close(self):
            self.close_calls += 1
            if not self.open:
                raise ProgrammingError("closing a closed connection")
            self.open = False

        def cursor(self):
            return None

    def Connect(*args, **kwargs):
        return FakeMySQLdbConnection(*args, **kwargs)

    mod = types.ModuleType("MySQLdb")
    conns = types.ModuleType("MySQLdb.connections")
    conns.Connection = FakeMySQLdbConnection
    mod.connections = conns
    mod.ProgrammingError = ProgrammingError
    mod.Connect = mod.connect = mod.Connection = Connect
    mod.paramstyle = "format"
    mod.apilevel = "2.0"
    mod.threadsafety = 1
    mod.BINARY = mod.STRING = mod.NUMBER = mod.DATETIME = mod.ROWID = object()
    mod.Error = Exception
    mod.DatabaseError = Exception
    mod.OperationalError = OSError
    mod.InterfaceError = Exception
    mod.IntegrityError = Exception
    mod.DataError = Exception
    mod.InternalError = Exception
    mod.NotSupportedError = Exception
    mod.Warning = Warning

    monkeypatch.setitem(sys.modules, "MySQLdb", mod)
    monkeypatch.setitem(sys.modules, "MySQLdb.connections", conns)
    real_version = importlib.metadata.version
    monkeypatch.setattr(
        importlib.metadata,
        "version",
        lambda pkg: version if pkg == "mysqlclient" else real_version(pkg),
    )
    return mod, FakeMySQLdbConnection, calls


@pytest.mark.parametrize("bad_version", ["2.1.1", "3.0.0", "2.2.7rc1", "1!2.2.7"])
def test_mysqldb_version_range_rejects_and_rolls_back(monkeypatch, bad_version):
    original_connect = pymysql.connections.Connection.connect
    _make_fake_mysqldb(monkeypatch, version=bad_version)
    with pytest.raises(routing.RoutingError, match="unsupported_driver_version"):
        routing.install(profiles={"app": PROFILE}, drivers=("pymysql", "MySQLdb"))
    assert pymysql.connections.Connection.connect is original_connect


def test_mysqldb_routing_positional_aliases_passthrough_and_hook_restore(monkeypatch):
    mod, cls, calls = _make_fake_mysqldb(monkeypatch, version="2.3.2")
    saved_alias = mod.connect
    original_init = cls.__init__
    with routing.install(profiles={"app": PROFILE}, drivers=("MySQLdb",)) as reg:
        assert cls.__init__ is not original_init
        # Unregistered endpoint passes through untouched
        other = mod.connect(host="127.0.0.1", port=3308, database="other", user="u", password="p")
        assert calls[-1][1]["port"] == 3308 and other.open

        # Registered endpoint before bind refuses
        with pytest.raises(routing.RoutingError, match="missing_target"):
            mod.connect(host="127.0.0.1", port=3307, database="app", user="u", password="unit-private-value")

        with reg.bind("app", DB()):
            raw_kw = dict(host="127.0.0.1", port=3307, db="app", user="orig", passwd="unit-private-value")
            c1 = mod.connect(**raw_kw)
            assert raw_kw["host"] == "127.0.0.1" and raw_kw["port"] == 3307
            c2 = saved_alias("127.0.0.1", "orig", "unit-private-value", "app", 3307)
            c3 = mod.Connect(host="127.0.0.1", port=3307, database="app", ssl_mode="PREFERRED")
            c4 = mod.connect(host="127.0.0.1", port=3307, database="app", ssl=False)
            c5 = mod.connect(host="127.0.0.1", port=3307, database="app", ssl_mode="DISABLED", ssl={"ca": "/ignored"})
            for c in (c1, c2, c3, c4, c5):
                assert c.connected_kwargs["host"] == "127.0.0.1"
                assert c.connected_kwargs["port"] == 12345
                assert c.connected_kwargs["user"] == "child"
                assert c.connected_kwargs["password"] == "private-child-value"
                assert c.connected_kwargs["database"] == "app"
            # Double close by user before lease exit is tolerated cleanly
            c1.close()
        for c in (c1, c2, c3, c4, c5):
            assert not c.open
    assert cls.__init__ is original_init


@pytest.mark.parametrize(
    "extra,code",
    [
        ({"database": "other"}, "schema_mismatch"),
        ({"read_default_file": "/tmp/my.cnf"}, "option_file"),
        ({"read_default_group": "client"}, "option_file"),
        ({"unix_socket": "/tmp/mysql.sock"}, "transport_conflict"),
        ({"named_pipe": True}, "transport_conflict"),
        ({"ssl": True}, "tls_unavailable"),
        ({"ssl": {}}, "tls_unavailable"),
        ({"ssl": {"ca": "/tmp/ca.pem"}}, "tls_unavailable"),
        ({"ssl_mode": "REQUIRED"}, "tls_unavailable"),
        ({"ssl_mode": "VERIFY_CA"}, "tls_unavailable"),
        ({"ssl_mode": "VERIFY_IDENTITY"}, "tls_unavailable"),
        ({"ssl_mode": "preferred"}, "tls_unavailable"),
        ({"compress": True}, "unsupported_options"),
        ({"local_infile": True}, "unsupported_options"),
        ({"local_infile_dir": "/tmp"}, "unsupported_options"),
        ({"server_public_key_path": "/tmp/pub.pem"}, "unsupported_options"),
        ({"auth_plugin": "caching_sha2_password"}, "unsupported_options"),
    ],
)
def test_mysqldb_refuses_unsupported_options_before_dial(monkeypatch, extra, code):
    mod, _, calls = _make_fake_mysqldb(monkeypatch, version="2.2.7")
    base = dict(host="127.0.0.1", port=3307, database="app", user="u", password="unit-private-value")
    base.update(extra)
    with routing.install(profiles={"app": PROFILE}, drivers=("MySQLdb",)) as reg:
        with pytest.warns(routing.UnusedRoutingWarning):
            with reg.bind("app", DB()):
                with pytest.raises(routing.RoutingError, match=code) as err:
                    mod.connect(**base)
                assert "unit-private-value" not in json.dumps(err.value.diagnostics)
    assert calls == []


def test_mysqldb_connect_failure_cleans_up_open_handle_without_secondary_error(monkeypatch):
    mod, _, _ = _make_fake_mysqldb(monkeypatch, version="2.2.7", fail_connect=lambda a, kw: True)
    with routing.install(profiles={"app": PROFILE}, drivers=("MySQLdb",)) as reg:
        with pytest.warns(routing.UnusedRoutingWarning):
            with reg.bind("app", DB()):
                with pytest.raises(OSError, match="connect failed") as err:
                    mod.connect(host="127.0.0.1", port=3307, database="app", user="u", password="p")
                assert not getattr(err.value, "cleanup_errors", ())


def test_mysqldb_hook_conflict_and_sqlalchemy_mysqldb_adapter(monkeypatch):
    from sqlalchemy import create_engine
    mod, cls, _ = _make_fake_mysqldb(monkeypatch, version="2.2.7")
    # Enrolling mysql+mysqldb without "MySQLdb" routing driver fails
    engine = create_engine("mysql+mysqldb://original@127.0.0.1:3307/app")
    try:
        with routing.install(profiles={"app": PROFILE}, drivers=("pymysql",)) as py_only:
            with pytest.raises(routing.RoutingError, match="unsupported_adapter"):
                py_only.register_engine(engine, profile="app", ownership="test")
        with routing.install(profiles={"app": PROFILE}, drivers=("MySQLdb",)) as reg:
            reg.register_engine(engine, profile="app", ownership="test")
            with reg.bind("app", DB()):
                a = connect(reg)
                ar = Record(a)
                engine.pool.dispatch.checkout(a, ar, None)
                engine.pool.dispatch.checkin(a, ar)
            assert a.closed
            installed = cls.__init__
            monkeypatch.setattr(cls, "__init__", lambda self, *a, **k: None)
            with pytest.raises(routing.RoutingError, match="hook_conflict"):
                reg.close()
            monkeypatch.setattr(cls, "__init__", installed)
    finally:
        engine.dispose()
