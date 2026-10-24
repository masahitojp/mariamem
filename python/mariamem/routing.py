"""Opt-in, scoped connection routing for independent test databases.

Importing this module installs no hooks and imports no optional SQL driver.
Install before application connection activity; join application work before
leaving a binding. Only explicitly enrolled profiles/resources are managed.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
import math
import importlib.metadata
import threading
import time
import uuid
from types import MappingProxyType


class RoutingError(RuntimeError):
    """A routing/lifecycle refusal with an actionable, credential-free context."""

    def __init__(self, code, action, *, profile=None, lease=None, driver=None):
        self.code = code
        self.stage = "connection_binding"
        self.action = action
        self.profile = profile
        self.child = getattr(lease, "child_id", None)
        self.generation = getattr(lease, "generation", None)
        self.driver = driver
        super().__init__(code + ": " + action)

    @property
    def diagnostics(self):
        return {key: getattr(self, key) for key in
                ("code", "stage", "action", "profile", "child", "generation", "driver")}


@dataclass(frozen=True)
class Profile:
    """Original TCP endpoint and logical schema, without application credentials."""

    host: str
    port: int
    database: str

    def __post_init__(self):
        if not isinstance(self.host, str) or not self.host:
            raise ValueError("profile host must be a nonempty string")
        if type(self.port) is not int or not 0 < self.port < 65536:
            raise ValueError("profile port must be between 1 and 65535")
        if not isinstance(self.database, str) or not self.database:
            raise ValueError("profile database must be a nonempty string")


class _Lease:
    def __init__(self, name, db):
        self.profile = name
        self.database = db
        self.child_id = db.id
        self.generation = uuid.uuid4().hex
        self.live = True
        self.pending = 0
        self.resources = {}
        self.condition = threading.Condition(threading.RLock())


class _Resource:
    def __init__(self, connection, lease, closer):
        self.connection = connection
        self.lease = lease
        self.closer = closer
        self.record = None
        self.checked_out = False


_install_lock = threading.RLock()
_active = None


def _attach_cleanup(primary, error):
    # add_note is unavailable on the supported Python3.9/3.10 boundary.
    primary.cleanup_errors = getattr(primary, "cleanup_errors", ()) + (error,)
    if hasattr(primary, "add_note"):
        primary.add_note("mariamem routing cleanup also failed: " +
                         (error.code if isinstance(error, RoutingError) else type(error).__name__))


class Registry:
    """Installed profile guard; use install() to acquire it."""

    def __init__(self, profiles, drivers, cleanup_timeout):
        if len(profiles) != 1 or any(not isinstance(k, str) or not k for k in profiles):
            raise ValueError("register exactly one named profile")
        if any(not isinstance(v, Profile) for v in profiles.values()):
            raise TypeError("profile values must be routing.Profile instances")
        if not isinstance(cleanup_timeout, (float, int)) or not math.isfinite(cleanup_timeout) or cleanup_timeout <= 0:
            raise ValueError("cleanup_timeout must be positive and finite")
        if not drivers or len(set(drivers)) != len(drivers):
            raise ValueError("select at least one distinct driver")
        self.profiles = MappingProxyType(dict(profiles))
        self.drivers = tuple(drivers)
        self.cleanup_timeout = cleanup_timeout
        self._current = ContextVar("mariamem_routing", default=None)
        self._lock = threading.RLock()
        self._leases = {}
        self._patches = []
        self._adapters = {}
        self._closed = False
        self._closing = False

    def _error(self, code, action, lease=None, driver=None):
        return RoutingError(code, action, profile=next(iter(self.profiles)),
                            lease=lease, driver=driver)

    def _require_installed(self):
        if self._closed or self._closing:
            raise self._error("closed_registry", "Finish registry.close() and install a new registry.")
        if _active is not self:
            raise self._error("uninstalled_registry", "Use routing.install() before binding or enrolling resources.")

    def _patch(self, owner, name, function):
        original = getattr(owner, name)
        self._patches.append((owner, name, original, function))
        setattr(owner, name, function)

    def _schema(self, value):
        profile = next(iter(self.profiles.values()))
        try:
            if isinstance(value, bytes):
                value = value.decode("utf8")
        except UnicodeError:
            value = None
        if value != profile.database:
            raise self._error("schema_mismatch", "Use the registered schema or explicit child settings.")

    def _match(self, host, port, schema):
        profile = next(iter(self.profiles.values()))
        if (host or "localhost", int(port or 3306)) != (profile.host, profile.port):
            return False
        self._schema(schema)
        return True

    def _target(self):
        lease = self._current.get()
        if lease is None:
            raise self._error("missing_target", "Enter the test binding before opening this profile.")
        self._validate(lease)
        return lease

    def _validate(self, lease, driver=None):
        if not lease.live:
            raise self._error("expired_target", "Join application work before leaving its test binding.", lease, driver)
        if lease.database.closed:
            raise self._error("closed_target", "Acquire a live child before opening a connection.", lease, driver)

    def _connect(self, connection, connect, closer, driver):
        lease = self._target()
        previous = getattr(connection, "_mariamem_lease", None)
        with lease.condition:
            self._validate(lease, driver)
            if previous is not None and previous is not lease:
                raise self._error("held_connection", "Create a new connection for this test binding.", lease, driver)
            connection._mariamem_registry = self
            connection._mariamem_lease = lease
            resource = _Resource(connection, lease, closer)
            connection._mariamem_resource = resource
            lease.resources[id(connection)] = resource
            lease.pending += 1
        try:
            # Do not hold the lease lock across slow network/driver code.
            result = connect(lease.database.connection_info())
            with lease.condition:
                self._validate(lease, driver)
            return result
        except BaseException as primary:
            try:
                closer()
            except BaseException as cleanup:
                _attach_cleanup(primary, cleanup)
            else:
                with lease.condition:
                    lease.resources.pop(id(connection), None)
            raise
        finally:
            with lease.condition:
                lease.pending -= 1
                lease.condition.notify_all()

    def _drain(self, lease):
        deadline = time.monotonic() + self.cleanup_timeout
        with lease.condition:
            lease.live = False
            while lease.pending or any(r.checked_out for r in lease.resources.values()):
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise self._error("drain_timeout", "Release owned checkouts and join work, then retry registry.close().", lease)
                lease.condition.wait(remaining)
            # New admissions have stopped and every pool checkout is returned.
            failures = []
            for key, resource in list(lease.resources.items()):
                try:
                    if resource.record is not None and resource.record.dbapi_connection is resource.connection:
                        resource.record.invalidate()
                    else:
                        resource.closer()
                except BaseException as error:
                    failures.append(error)
                else:
                    del lease.resources[key]
            if failures:
                raise self._error("cleanup_failed", "Inspect the connection close cause and retry registry.close().", lease) from failures[0]
        with self._lock:
            self._leases.pop(lease.generation, None)

    @contextmanager
    def bind(self, profile, database):
        if profile not in self.profiles:
            raise self._error("unknown_profile", "Select a registered profile.")
        with self._lock:
            self._require_installed()
            if database.closed:
                raise self._error("closed_target", "Acquire a live child before binding.")
            lease = _Lease(profile, database)
            self._leases[lease.generation] = lease
        token = self._current.set(lease)
        primary = None
        try:
            yield lease
        except BaseException as error:
            primary = error
            raise
        finally:
            try:
                self._drain(lease)
            except BaseException as error:
                if primary is None:
                    raise
                _attach_cleanup(primary, error)
            finally:
                self._current.reset(token)

    def enroll(self, engine, *, profile, ownership):
        """Hand off a quiescent engine. Only ownership='test' is supported."""
        if ownership != "test":
            raise self._error("ownership_required", "Hand off a quiescent test-owned engine explicitly.")
        if profile not in self.profiles:
            raise self._error("unknown_profile", "Select a registered profile.")
        with self._lock:
            self._require_installed()
            self._sqlalchemy()
            from ._routing_sqlalchemy import Adapter
            if engine in self._adapters:
                self._adapters[engine].ensure_quiet()
                return engine
            adapter = Adapter(self, engine)
            self._adapters[engine] = adapter
        return engine

    def _sqlalchemy(self):
        try:
            version = importlib.metadata.version("SQLAlchemy")
        except importlib.metadata.PackageNotFoundError as error:
            raise self._error("adapter_unavailable", "Install the routing-sqlalchemy extra or pass child settings explicitly.") from error
        if version != "2.0.54":
            raise self._error("unsupported_adapter_version", "Use SQLAlchemy2.0.54 or explicit child configuration.")

    def create_engine(self, url, *, profile, **options):
        self._require_installed()
        self._sqlalchemy()
        from sqlalchemy import create_engine
        engine = create_engine(url, **options)
        try:
            return self.enroll(engine, profile=profile, ownership="test")
        except BaseException:
            engine.dispose()
            raise

    def close(self):
        global _active
        with _install_lock, self._lock:
            if self._closed:
                return
            if any(lease.live for lease in self._leases.values()):
                raise self._error("active_scope", "Leave all test bindings before closing the registry.")
            self._closing = True
            for lease in list(self._leases.values()):
                self._drain(lease)
            for adapter in self._adapters.values():
                adapter.ensure_quiet()
                adapter.check_hooks()
            # Preflight before restoring anything; a later patch is not ours.
            if any(getattr(owner, name) is not installed for owner, name, _, installed in self._patches):
                raise self._error("hook_conflict", "Remove the later driver patch, then retry close().")
            for adapter in self._adapters.values():
                adapter.close()
            for owner, name, original, _ in reversed(self._patches):
                setattr(owner, name, original)
            self._closed = True
            if _active is self:
                _active = None

    def __enter__(self):
        self._require_installed()
        return self

    def __exit__(self, kind, error, traceback):
        try:
            self.close()
        except BaseException as cleanup:
            if error is None:
                raise
            _attach_cleanup(error, cleanup)


def install(*, profiles, drivers=("pymysql",), cleanup_timeout=5):
    """Guard one named profile until close; no original-target fallback."""
    global _active
    with _install_lock:
        if _active is not None:
            raise RoutingError("already_installed", "Reuse the installed registry; nest bindings instead.")
        registry = Registry(profiles, drivers, cleanup_timeout)
        try:
            from ._routing_drivers import install_driver
            for driver in registry.drivers:
                install_driver(registry, driver)
        except BaseException:
            for owner, name, original, _ in reversed(registry._patches):
                setattr(owner, name, original)
            raise
        _active = registry
        return registry
