"""Disposable independent MariaDB instances and process-local prepared baselines."""
import math
import shutil
from pathlib import Path
import threading
import time
import uuid

from ._artifacts import ArtifactError, resolve
from ._version import PYTHON_VERSION

__version__ = PYTHON_VERSION


class HostError(RuntimeError):
    def __init__(self, message, *, code=None, stage=None, closed=False):
        super().__init__(message)
        self.code = code
        self.stage = stage
        self.closed = closed


class Busy(HostError):
    pass


class TransactionActive(HostError):
    pass


def _positive(value):
    if not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise ValueError("timeouts must be positive and finite")
    return value


class Database:
    def __init__(self, *, host_binary=None, runtime=None, module=None, log_path=None,
                 wasmer_dir=None, query_timeout=30, startup_timeout=120,
                 shutdown_timeout=30, snapshot=None):
        if wasmer_dir is not None:
            raise ValueError("wasmer_dir is retired; generated-Go requires no Wasmer cache")
        for v in (query_timeout, startup_timeout, shutdown_timeout):
            _positive(v)
        requested_log = Path(log_path).absolute() if log_path is not None else None
        if snapshot is not None and not isinstance(snapshot, Snapshot):
            raise TypeError("snapshot must be a live Snapshot handle; saved snapshots are no longer supported")
        try:
            resolved = resolve(host_binary, runtime, module)
        except ArtifactError as exc:
            raise HostError(str(exc), code=exc.code,
                            stage="platform" if exc.code == "unsupported_platform" else "artifact_validation") from exc
        self._options = dict(host_binary=resolved["host_binary"], query_timeout=query_timeout,
                             startup_timeout=startup_timeout, shutdown_timeout=shutdown_timeout)
        self._shutdown_timeout = shutdown_timeout
        self._lock = threading.RLock()
        self._closed = False
        self._logs = ""
        self._session = None
        self._handle = None
        from ._session import Session
        transfer = None
        source_session = None
        if snapshot is None:
            session = Session(resolved["host_binary"])
            try:
                session.retain()
            except BaseException:
                session._finish(force=True)
                raise
        else:
            # Reserve while parent Close is excluded; the host pins backing
            # through admission/startup independently of the parent Python object.
            with snapshot._lock:
                if snapshot._closed:
                    raise ValueError("Snapshot is closed")
                session = snapshot._session
                session.retain()
                if str(Path(resolved["host_binary"]).absolute()) != session.binary:
                    source_session = session
                    try:
                        replacement = Session(resolved["host_binary"])
                        try:
                            replacement.retain()
                        except BaseException:
                            replacement._finish(force=True)
                            raise
                        session = replacement
                        if session.guest_identity != source_session.guest_identity:
                            raise HostError("Snapshot guest identity mismatch", code="snapshot_failed", closed=False)
                        transfer = source_session.root / ("handoff-" + uuid.uuid4().hex)
                        source_session.request("handoff", handle=snapshot._handle, transfer_path=str(transfer))
                    except BaseException:
                        if transfer is not None:
                            shutil.rmtree(transfer, ignore_errors=True)
                        if session is not source_session:
                            session.release()
                        source_session.release()
                        raise
        self._session = session
        self._owned_log = log_path is None
        self.log_path = requested_log if requested_log is not None else session.root / ("db-" + uuid.uuid4().hex + ".log")
        try:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            fields = dict(log_path=str(self.log_path), query_timeout=f"{query_timeout}s",
                          startup_timeout=f"{startup_timeout}s", shutdown_timeout=f"{shutdown_timeout}s")
            if snapshot is None or transfer is not None:
                if transfer is not None:
                    fields["transfer_path"] = str(transfer)
                reply = session.request("start", response_timeout=startup_timeout+15, **fields)
            else:
                reply = session.request("fork", handle=snapshot._handle, response_timeout=startup_timeout+15, **fields)
            ready = reply["database"]
            self._handle = ready["handle"]
            self.id = ready["id"]
            self.capabilities = tuple(ready["capabilities"])
            self.diagnostics = {key: ready[key] for key in ("pid", "runtime_pid")}
            self.diagnostics["host_pid"] = self.diagnostics.pop("pid")
            self._connection_info = {key: ready[key] for key in ("host", "port", "user", "password", "database")}
        except BaseException:
            try:
                if self._handle is not None and not session.failed:
                    try:
                        session.request("db_close", handle=self._handle, response_timeout=shutdown_timeout+25)
                    except Exception:
                        pass
            finally:
                self._dispose()
            raise
        finally:
            if transfer is not None:
                shutil.rmtree(transfer)
            if source_session is not None:
                source_session.release()

    def _request(self, op, response_timeout=10, **fields):
        if self._closed:
            raise HostError("Database is closed", code="closed", closed=True)
        return self._session.request(op, response_timeout=response_timeout, handle=self._handle, **fields)

    def status(self):
        with self._lock:
            reply = self._request("status")
            self._logs = reply.pop("logs", self._logs)
            return reply

    @property
    def closed(self):
        if self._closed or self._session.failed:
            return True
        try:
            self.status()
        except HostError as exc:
            if exc.closed:
                return True
            raise
        return False

    @property
    def logs(self):
        with self._lock:
            if not self._closed and not self._session.failed:
                self._logs = self._request("logs").get("logs", self._logs)
            return self._logs

    def connection_info(self):
        if self.closed:
            raise HostError("Database is closed", code="unusable", closed=True)
        return self._connection_info.copy()

    def wait_disconnected(self, timeout=5):
        _positive(timeout)
        deadline = time.monotonic() + timeout
        while self.status()["active_connections"]:
            if time.monotonic() >= deadline:
                raise TimeoutError("SQL connections are still active")
            time.sleep(0.005)

    def close(self):
        with self._lock:
            if self._closed:
                return
            try:
                if not self._session.failed:
                    self._logs = self._request("db_close", self._shutdown_timeout+25).get("logs", self._logs)
            except HostError as exc:
                if not exc.closed:
                    raise
            finally:
                self._dispose()

    def snapshot(self, *, rollback=False, timeout=120):
        """Consume this DB and own a fixed in-memory baseline for independent Forks."""
        _positive(timeout)
        if not isinstance(rollback, bool):
            raise ValueError("rollback must be a bool")
        with self._lock:
            try:
                reply = self._request("snapshot", response_timeout=None, rollback=rollback, timeout=f"{timeout}s")
            except HostError as exc:
                if exc.closed:
                    self._dispose()
                raise
            self._logs = reply.get("logs", self._logs)
            baseline = Snapshot._from_host(self._session, reply["snapshot"], self._options)
            self._dispose()
            return baseline

    def _dispose(self):
        if self._closed:
            return
        self._closed = True
        try:
            self._logs = self.log_path.read_text(errors="replace")[-16384:]
        except OSError:
            pass
        if self._owned_log:
            self.log_path.unlink(missing_ok=True)
        self._session.release()

    def __enter__(self):
        if self.closed:
            raise HostError("Database is closed", code="closed", closed=True)
        return self

    def __exit__(self, *exc):
        self.close()


def start(**options):
    return Database(**options)


from .snapshot import Snapshot
from .live import Live
from .dump import DumpImportError, import_dump
