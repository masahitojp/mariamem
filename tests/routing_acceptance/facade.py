"""Test-only adapter of the approved real-guest oracle matrix to the public API.

Fault injection lives here, never in production routing. Kept-idle sessions are
deliberately outside normal teardown so checkout validation is independently
exercised. All injected resources are drained during fixture cleanup.
"""
from contextlib import contextmanager
from mariamem import routing
from sqlalchemy import event, exc


class Router:
    def __init__(self, host, port, *, mutation=None):
        self.host, self.port, self.mutation = host, port, mutation
        self.observations = {"physical_connects": 0, "pool_rejected": 0}
        self.kept = set()
        self.leases = []
        self.global_target = None

    def install(self):
        try:
            import mysql.connector
            drivers = ("pymysql", "mysql.connector")
        except (ImportError, AttributeError):
            drivers = ("pymysql",)
        self.registry = routing.install(profiles={"app": routing.Profile(self.host, self.port, "app")}, drivers=drivers)
        self.current = self.registry._current
        original_target = self.registry._target
        original_validate = self.registry._validate
        original_connect = self.registry._connect
        original_drain = self.registry._drain

        def target():
            if self.mutation == "global_target":
                token = self.current.set(self.global_target)
                try:
                    return original_target()
                finally:
                    self.current.reset(token)
            return original_target()

        def validate(lease, driver=None):
            if self.mutation == "ignore_retired":
                if lease.database.closed:
                    raise self.registry._error("closed_target", "Use a live child.")
                return
            return original_validate(lease, driver)

        def connect(connection, callback, closer, driver):
            if self.mutation == "fallback" and self.current.get() is None:
                return callback(dict(host=self.host, port=self.port, user="application", password="not-a-real-secret"))
            result = original_connect(connection, callback, closer, driver)
            self.observations["physical_connects"] += 1
            return result

        def drain(lease):
            if lease.generation in self.kept:
                lease.live = False
                return
            return original_drain(lease)

        self.registry._target = target
        self.registry._validate = validate
        self.registry._connect = connect
        self.registry._drain = drain
        return self

    def enroll(self, engine):
        dispose = engine.dispose
        if self.mutation == "adopt_unknown":
            engine.dispose = lambda: None
        try:
            result = self.registry.enroll(engine, profile="app", ownership="test")
        finally:
            engine.dispose = dispose
        adapter = self.registry._adapters[engine]
        for index, (name, original) in enumerate(adapter.events):
            if name != "checkout":
                continue
            event.remove(engine, name, original)

            def checkout(connection, record, proxy, original=original):
                resource = getattr(connection, "_mariamem_resource", None)
                skip = (self.mutation in ("no_pool_check", "retain_session")
                        or (self.mutation == "adopt_unknown" and resource is None))
                if skip:
                    if resource is not None:
                        resource.record = record
                        resource.checked_out = True
                        record.info["mariamem_resource"] = resource
                    return
                try:
                    return original(connection, record, proxy)
                except exc.DisconnectionError:
                    self.observations["pool_rejected"] += 1
                    raise

            event.listen(engine, name, checkout)
            adapter.events[index] = (name, checkout)
        return result

    @contextmanager
    def bind(self, db, *, cleanup=True):
        with self.registry.bind("app", db) as lease:
            self.leases.append(lease)
            previous = self.global_target
            self.global_target = lease
            if not cleanup:
                self.kept.add(lease.generation)
            try:
                yield lease
            finally:
                self.global_target = previous

    def inject_cleanup_failure(self, lease):
        class Broken:
            attempts = 0

            def close(self):
                self.attempts += 1
                if self.attempts == 1:
                    raise OSError("injected close failure")
        connection = Broken()
        self.registry._connect(connection, lambda info: None, connection.close, "injected")

    def uninstall(self):
        self.kept.clear()
        # A deliberately reauthorized retired scope may have been removed from
        # the registry before the injected bug opened another session.
        for lease in self.leases:
            if lease.resources:
                self.registry._leases[lease.generation] = lease
        self.registry.close()
