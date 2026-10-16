"""Experiment-only Python adapter; caller uses start/snapshot/fork/close as before.

One lazily launched host owns one root DB and its descendants. This is deliberately
not a packaged API or a process shared across unrelated starts/pytest workers.
"""
import json
import math
import os
import queue
import subprocess
import threading
import time
import mariamem

GUEST = '7d1330e67b06eb810d0fafd649df0944dbca1b20cd7e49f8e5ecdde7f5ac8c09'
SESSIONS = []
MODE = None


def positive(value):
    if not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise ValueError('timeout must be positive and finite')
    return value


class Session:
    def __init__(self, binary, mode):
        from mariamem._artifacts import resolve
        binary = resolve(host_binary=binary)['host_binary']
        env = os.environ.copy()
        env.pop('MARIAMEM_HEAP_FAULT', None)
        env.pop('MARIAMEM_HEAP_KIND', None)
        env['MARIAMEM_HEAP'] = '1' if mode == 'heap' else '0'
        self.lock = threading.Lock()
        self.seq = 0
        self.messages = queue.Queue()
        self.log = ''
        self.done = False
        self.proc = subprocess.Popen([binary], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE, text=True, bufsize=1, env=env)
        self.reader = threading.Thread(target=self._read, daemon=True)
        self.logger = threading.Thread(target=self._log, daemon=True)
        self.reader.start()
        self.logger.start()
        SESSIONS.append(self)
        try:
            ready = self.receive(15)
            if ready.get('event') != 'ready' or ready.get('protocol') != 1 or ready.get('guest_sha256') != GUEST:
                raise mariamem.HostError('broker greeting identity mismatch', code='artifact_mismatch')
        except BaseException:
            self.dispose()
            raise

    def _read(self):
        try:
            for line in self.proc.stdout:
                self.messages.put(json.loads(line))
        except Exception as exc:
            self.messages.put(exc)
        finally:
            self.messages.put(mariamem.HostError('shared host exited', code='unusable', closed=True))

    def _log(self):
        for line in self.proc.stderr:
            self.log = (self.log + line)[-16384:]

    def receive(self, timeout):
        try:
            value = self.messages.get(timeout=timeout)
        except queue.Empty as exc:
            raise TimeoutError('experiment broker response deadline') from exc
        if isinstance(value, BaseException):
            raise value
        return value

    def dispose(self):
        if self.done:
            return
        self.done = True
        try:
            self.proc.stdin.close()  # owner EOF closes every resource in this lineage
        except (BrokenPipeError, OSError):
            pass
        try:
            self.proc.wait(timeout=40)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait(timeout=5)
            raise RuntimeError('experiment broker did not shut down cooperatively')
        finally:
            self.reader.join(timeout=5)
            self.logger.join(timeout=5)
            self.proc.stdout.close()
            self.proc.stderr.close()

    def rpc(self, op, handle=0, timeout=120, **fields):
        with self.lock:
            if self.done or self.proc.poll() is not None:
                self.dispose()
                raise mariamem.HostError('shared host exited', code='unusable', closed=True)
            self.seq += 1
            try:
                self.proc.stdin.write(json.dumps(dict(id=self.seq, op=op, handle=handle, timeout=timeout, **fields))+'\n')
                self.proc.stdin.flush()
                reply = self.receive(timeout+15)
                if reply.get('id') != self.seq:
                    raise RuntimeError('response identity mismatch')
            except BaseException:
                self.dispose()
                raise
            if reply.get('idle'):
                self.dispose()
                if self.proc.returncode:
                    raise mariamem.HostError('broker cleanup failed', code='unusable', closed=True)
            if not reply.get('ok'):
                e = reply['error']
                cls = {'busy': mariamem.Busy, 'transaction_active': mariamem.TransactionActive}.get(e['code'], mariamem.HostError)
                raise cls(e['message'], code=e['code'], closed=reply.get('closed', False))
            return reply


class Database:
    def __init__(self, *, host_binary=None, query_timeout=30, startup_timeout=120,
                 shutdown_timeout=30, **unsupported):
        if unsupported:
            raise NotImplementedError('spike options: '+', '.join(unsupported))
        for t in (query_timeout, startup_timeout, shutdown_timeout):
            positive(t)
        session = Session(host_binary, MODE)
        try:
            reply = session.rpc('start', query_timeout=query_timeout, startup_timeout=startup_timeout,
                                shutdown_timeout=shutdown_timeout, timeout=startup_timeout)
            self.adopt(session, reply['database'])
        except BaseException:
            session.dispose()
            raise

    def adopt(self, session, data):
        self._session = session
        self.id = data['handle']
        self._info = {k: data[k] for k in ('host', 'port', 'user', 'password', 'database')}
        self.diagnostics = {'host_pid': data['pid'], 'runtime_pid': data['pid']}
        self._closed = False
        self._lock = threading.Lock()

    @property
    def closed(self):
        return self._closed or self._session.proc.poll() is not None

    @property
    def logs(self):
        return self._session.log

    def connection_info(self):
        if self.closed:
            raise mariamem.HostError('Database is closed', code='closed', closed=True)
        return self._info.copy()

    def wait_disconnected(self, timeout=5):
        positive(timeout)
        self._session.rpc('wait_disconnected', self.id, timeout=timeout)

    def snapshot(self, *, rollback=False, timeout=120):
        positive(timeout)
        if not isinstance(rollback, bool):
            raise ValueError('rollback must be bool')
        with self._lock:
            if self.closed:
                raise mariamem.HostError('Database is closed', code='closed', closed=True)
            try:
                reply = self._session.rpc('snapshot', self.id, timeout=timeout, rollback=rollback)
            except mariamem.HostError as exc:
                if exc.closed:
                    self._closed = True
                raise
            self._closed = True
            return Snapshot(self._session, reply['snapshot'], reply.get('heap_stats'))

    def close(self):
        with self._lock:
            if self._closed:
                return
            try:
                if self._session.proc.poll() is None:
                    self._session.rpc('db_close', self.id)
                else:
                    self._session.dispose()
            finally:
                self._closed = True

    def __enter__(self):
        if self.closed:
            raise mariamem.HostError('Database is closed', code='closed', closed=True)
        return self

    def __exit__(self, *exc):
        self.close()


class Snapshot:
    def __init__(self, session, handle, stats):
        self._session, self.id, self.heap_stats = session, handle, stats
        self._closed = False
        self._lock = threading.Lock()

    def fork(self, **options):
        if options:
            raise NotImplementedError('spike fork option overrides')
        with self._lock:
            if self._closed:
                raise ValueError('Snapshot is closed')
            data = self._session.rpc('fork', self.id)['database']
            child = object.__new__(Database)
            child.adopt(self._session, data)
            return child

    def close(self):
        with self._lock:
            if self._closed:
                return
            try:
                if self._session.proc.poll() is None:
                    self._session.rpc('snapshot_close', self.id)
                else:
                    self._session.dispose()
            finally:
                self._closed = True

    def __enter__(self):
        if self._closed:
            raise ValueError('Snapshot is closed')
        return self

    def __exit__(self, *exc):
        self.close()


def install(mode):
    global MODE
    assert mode in ('file', 'heap')
    MODE = mode
    mariamem.Database, mariamem.Snapshot = Database, Snapshot
