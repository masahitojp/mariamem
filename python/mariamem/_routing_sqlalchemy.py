"""Explicitly enrolled SQLAlchemy2.0.54 QueuePool ownership adapter."""
import importlib.metadata
from sqlalchemy import event, exc
from sqlalchemy.pool import QueuePool


class Adapter:
    def __init__(self, registry, engine):
        self.registry, self.engine = registry, engine
        self.events = []
        self.closed = False
        if importlib.metadata.version("SQLAlchemy") != "2.0.54":
            raise registry._error("unsupported_adapter_version", "Use SQLAlchemy2.0.54 or explicit child configuration.")
        if engine.dialect.driver != "pymysql" or "pymysql" not in registry.drivers:
            raise registry._error("unsupported_adapter", "Use the enrolled mysql+pymysql adapter or explicit configuration.")
        if not isinstance(engine.pool, QueuePool):
            raise registry._error("custom_pool", "Use the default QueuePool or an explicit factory.")
        self.ensure_quiet()
        creator = getattr(engine.pool, "_creator", None)
        if (getattr(creator, "__module__", None) != "sqlalchemy.engine.create"
                or getattr(creator, "__name__", None) != "connect"
                or list(engine.dialect.dispatch.do_connect)):
            raise registry._error("custom_creator", "Provide an explicit test-owned factory adapter.")
        if not registry._match(engine.url.host, engine.url.port, engine.url.database):
            raise registry._error("unknown_profile", "Enroll an engine for the registered profile.")
        engine.dispose()

        def checkout(connection, record, proxy):
            lease = registry._target()
            resource = getattr(connection, "_mariamem_resource", None)
            if resource is None or resource.lease is not lease:
                record.invalidate()
                raise exc.DisconnectionError("Connection belongs to another test generation")
            with lease.condition:
                registry._validate(lease)
                resource.record = record
                resource.checked_out = True
                record.info["mariamem_resource"] = resource

        def checkin(connection, record):
            resource = getattr(connection, "_mariamem_resource", None) if connection is not None else record.info.get("mariamem_resource")
            if resource is not None:
                with resource.lease.condition:
                    resource.checked_out = False
                    resource.lease.condition.notify_all()
            record.info.pop("mariamem_resource", None)

        def invalidate(connection, record, error):
            # Record.info is cleared on invalidation; retire checkout ownership
            # before checkin(None, record) can lose that association.
            checkin(connection, record)

        try:
            for name, fn in (("checkout", checkout), ("checkin", checkin), ("invalidate", invalidate)):
                event.listen(engine, name, fn)
                self.events.append((name, fn))
        except BaseException:
            for name, fn in reversed(self.events):
                event.remove(engine, name, fn)
            raise

    def ensure_quiet(self):
        if self.closed:
            return
        if self.engine.pool.checkedout():
            raise self.registry._error("active_pool", "Return active connections/transactions before enrollment or close.")

    def check_hooks(self):
        if self.closed:
            return
        if any(not event.contains(self.engine, name, fn) for name, fn in self.events):
            raise self.registry._error("hook_conflict", "Restore the enrolled pool hooks before closing the registry.")

    def close(self):
        if self.closed:
            return
        self.engine.dispose()
        for name, fn in reversed(self.events):
            event.remove(self.engine, name, fn)
        self.closed = True
