"""Disposable routing prototype. No public API or production import.

One enrolled logical profile; original endpoint is a test sentinel. The pinned
SQLAlchemy default creator and PyMySQL/Connector connect paths are the boundary.
"""
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
import threading
import uuid

import pymysql
try:
    import mysql.connector as connector
    from mysql.connector.abstracts import MySQLConnectionAbstract
except (ImportError, AttributeError) as error:
    connector = None
    connector_import_error = repr(error)
from sqlalchemy import event, exc
from sqlalchemy.pool import QueuePool


class RouteError(RuntimeError):
    def __init__(self, code, action):
        self.code, self.stage = code, 'connection_binding'
        super().__init__(f'{code}: {action}')


@dataclass(eq=False)
class Lease:
    db: object
    generation: str = field(default_factory=lambda: uuid.uuid4().hex)
    live: bool = True
    connections: list = field(default_factory=list)
    lock: object = field(default_factory=threading.RLock)


class Router:
    def __init__(self, host, port, *, mutation=None):
        self.endpoint = (host, port)
        self.mutation = mutation
        self.current = ContextVar('mariamem_spike_scope', default=None)
        self.global_target = None
        self.engines = []
        self.patches = []
        self.events = []
        self.observations = {'physical_connects': 0, 'pool_rejected': 0}
        self.lock = threading.RLock()

    def target(self):
        lease = self.global_target if self.mutation == 'global_target' else self.current.get()
        if lease is None:
            raise RouteError('missing_target', 'Enter the test fixture before opening this profile.')
        if not lease.live and self.mutation != 'ignore_retired':
            raise RouteError('expired_target', 'Join background work before leaving its test fixture.')
        if lease.db.closed:
            raise RouteError('closed_target', 'Acquire a new child before opening a connection.')
        return lease

    def match(self, host, port):
        return (host or 'localhost', int(port or 3306)) == self.endpoint

    def tag(self, conn, lease):
        conn._mariamem_route = lease
        with lease.lock:
            lease.connections.append(conn)
        with self.lock:
            self.observations['physical_connects'] += 1

    def patch(self, owner, name, method):
        self.patches.append((owner, name, getattr(owner, name)))
        setattr(owner, name, method)

    def install(self):
        router = self
        init = pymysql.connections.Connection.__init__
        connect = pymysql.connections.Connection.connect
        connector_connect = MySQLConnectionAbstract.connect if connector else None
        factory = connector.connect if connector else None

        def py_init(conn, *args, **kw):
            if router.match(kw.get('host'), kw.get('port')):
                if kw.get('read_default_file') or kw.get('read_default_group'):
                    raise RouteError('option_file', 'Resolve this profile to explicit test connection settings.')
                if kw.get('unix_socket'):
                    raise RouteError('transport_conflict', 'Use the registered TCP profile explicitly.')
            conn._mariamem_explicit_tls = any(kw.get(k) for k in ('ssl', 'ssl_ca', 'ssl_cert', 'ssl_key', 'ssl_verify_cert', 'ssl_verify_identity'))
            return init(conn, *args, **kw)

        def py_connect(conn, sock=None):
            prior = getattr(conn, '_mariamem_route', None)
            if not prior and not router.match(conn.host, conn.port):
                return connect(conn, sock)
            if router.mutation == 'fallback' and router.current.get() is None:
                return connect(conn, sock)
            lease = router.target()
            with lease.lock:
                if not lease.live and router.mutation != 'ignore_retired':
                    raise RouteError('expired_target', 'Join background work before leaving its test fixture.')
                if prior is not None and prior is not lease:
                    raise RouteError('held_connection', 'Close the old connection; create one for this child.')
                if sock is not None or conn.unix_socket:
                    raise RouteError('transport_conflict', 'Use the registered TCP profile explicitly.')
                if conn._ssl_required or getattr(conn, '_mariamem_explicit_tls', False):
                    raise RouteError('tls_unavailable', 'This local target has no TLS; select an explicit test profile.')
                info = lease.db.connection_info()
                conn.host, conn.port = info['host'], info['port']
                conn.user, conn.password = info['user'], info['password'].encode()
                result = connect(conn, sock)
                router.tag(conn, lease)
                return result

        def my_connect(conn, **kw):
            prior = getattr(conn, '_mariamem_route', None)
            host, port = kw.get('host', getattr(conn, '_host', None)), kw.get('port', getattr(conn, '_port', None))
            if not prior and not router.match(host, port):
                return connector_connect(conn, **kw)
            lease = router.target()
            with lease.lock:
                if not lease.live and router.mutation != 'ignore_retired':
                    raise RouteError('expired_target', 'Join background work before leaving its test fixture.')
                if prior is not None and prior is not lease:
                    raise RouteError('held_connection', 'Close the old connection; create one for this child.')
                forbidden = ('unix_socket', 'option_files', 'read_default_file', 'ssl_ca', 'ssl_cert',
                             'ssl_key', 'ssl_verify_cert', 'ssl_verify_identity', 'dns_srv', 'failover')
                if any(kw.get(key) for key in forbidden):
                    raise RouteError('unsupported_options', 'Use an explicit local TCP test profile.')
                info = lease.db.connection_info()
                kw.update({key: info[key] for key in ('host', 'port', 'user', 'password')})
                result = connector_connect(conn, **kw)
                router.tag(conn, lease)
                return result

        def my_factory(*args, **kw):
            if router.match(kw.get('host'), kw.get('port')) and any(kw.get(k) for k in
                    ('pool_name', 'pool_size', 'option_files', 'read_default_file', 'dns_srv', 'failover')):
                raise RouteError('unsupported_factory', 'Use the enrolled unpooled factory or an explicit adapter.')
            return factory(*args, **kw)

        self.patch(pymysql.connections.Connection, '__init__', py_init)
        self.patch(pymysql.connections.Connection, 'connect', py_connect)
        if connector:
            self.patch(MySQLConnectionAbstract, 'connect', my_connect)
            self.patch(connector, 'connect', my_factory)
        return self

    def enroll(self, engine):
        # Pinned-source seam, deliberately not a general custom-pool detector.
        pool = engine.pool
        if not isinstance(pool, QueuePool):
            raise RouteError('custom_pool', 'Use the supported QueuePool adapter or explicit injection.')
        if pool.checkedout():
            raise RouteError('active_pool', 'Return existing connections before enrolling this engine.')
        creator = pool._creator
        if (getattr(creator, '__module__', None) != 'sqlalchemy.engine.create'
                or getattr(creator, '__name__', None) != 'connect'
                or list(engine.dialect.dispatch.do_connect)):
            raise RouteError('custom_creator', 'Provide an explicit test-owned factory adapter.')
        if not self.match(engine.url.host, engine.url.port):
            raise RouteError('unknown_profile', 'Register the intended logical profile explicitly.')
        # User explicitly enrolled this idle engine; discard its old idle sessions.
        engine.dispose()

        def checkout(conn, record, proxy):
            lease = self.target()
            conn._mariamem_pool_record = record
            owner = getattr(conn, '_mariamem_route', None)
            if self.mutation != 'no_pool_check' and owner is not lease:
                with self.lock:
                    self.observations['pool_rejected'] += 1
                record.invalidate()
                raise exc.DisconnectionError('Connection belongs to another test generation')

        event.listen(engine, 'checkout', checkout)
        self.events.append((engine, 'checkout', checkout))
        self.engines.append(engine)

    @contextmanager
    def bind(self, db, *, cleanup=True):
        lease = Lease(db)
        token = self.current.set(lease)
        previous = self.global_target
        self.global_target = lease
        primary = None
        try:
            yield lease
        except BaseException as error:
            primary = error
            raise
        finally:
            failures = []
            with lease.lock:
                lease.live = False
                if cleanup:
                    for conn in lease.connections:
                        try:
                            record = getattr(conn, '_mariamem_pool_record', None)
                            if record is not None and record.dbapi_connection is conn:
                                record.invalidate()
                            elif getattr(conn, 'open', True):
                                conn.close()
                        except pymysql.err.Error as error:
                            # Repeated close is already closed; other failures retained.
                            if str(error) != 'Already closed':
                                failures.append(error)
                        except BaseException as error:
                            failures.append(error)
            self.current.reset(token)
            self.global_target = previous
            if failures:
                if primary is not None:
                    primary.add_note('routing cleanup also failed: ' + type(failures[0]).__name__)
                else:
                    raise RouteError('cleanup_failed', 'Inspect the owned connection close failure.') from failures[0]

    def uninstall(self):
        for engine, name, fn in reversed(self.events):
            event.remove(engine, name, fn)
            engine.dispose()
        for owner, name, original in reversed(self.patches):
            setattr(owner, name, original)
