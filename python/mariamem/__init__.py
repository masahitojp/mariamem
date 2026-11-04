"""Disposable independent MariaDB instances and process-local prepared baselines."""
import math
from pathlib import Path
import threading
import time
import uuid

from ._artifacts import ArtifactError, resolve
from ._version import PYTHON_VERSION

__version__ = PYTHON_VERSION
_STARTUP_REPLY_MARGIN = 15


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
                 shutdown_timeout=30, snapshot=None, fork_timeout=None):
        if wasmer_dir is not None:
            raise ValueError("wasmer_dir is retired; generated-Go requires no Wasmer cache")
        for v in (query_timeout, startup_timeout, shutdown_timeout):
            _positive(v)
        requested_log = Path(log_path).absolute() if log_path is not None else None
        if snapshot is not None and not isinstance(snapshot, Snapshot):
            raise TypeError("snapshot must be a live Snapshot handle; saved snapshots are no longer supported")
        from ._forklimit import wait_nanoseconds
        wait_nanoseconds(fork_timeout)
        if snapshot is None and fork_timeout is not None:
            raise ValueError("fork_timeout requires a Snapshot")
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
        self._remote = None
        self._close_error = None
        from ._session import Session
        transfer = None
        source_session = None
        reservation = None
        source_handle = None
        if snapshot is None:
            session = Session(resolved["host_binary"])
            try:
                session.retain()
            except BaseException:
                session._finish(force=True)
                raise
        else:
            # Only copy immutable input and retain under the parent lock.
            # Capacity/transfer waits and releases must not exclude Close.
            with snapshot._lock:
                if snapshot._closed:
                    raise ValueError("Snapshot is closed")
                session = snapshot._session
                session.retain()
                source_handle = snapshot._handle
            try:
                reservation = snapshot._reserve(session, source_handle, fork_timeout)
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
                        if "fork-limit-v1" not in session.capabilities:
                            raise HostError("Target host lacks fork-limit-v1", code="unsupported", stage="fork_capability")
                        transfer = source_session.root / ("handoff-" + uuid.uuid4().hex)
                        from ._handoff import RemoteLease
                        self._remote = RemoteLease(snapshot, source_session, source_handle, reservation, transfer, session)
                        reply = source_session.request("handoff", handle=source_handle, reservation=reservation,
                                                       transfer_path=str(transfer), response_timeout=startup_timeout+_STARTUP_REPLY_MARGIN,
                                                       _cleanup=self._remote.late_export)
                        self._remote.exported = True
                        transfer = Path(reply["transfer_path"])
                    except BaseException:
                        raise
            except BaseException:
                if self._remote is None:
                    if reservation is not None:
                        try: snapshot._session.request("fork_cancel", handle=source_handle, reservation=reservation, response_timeout=5, _cleanup=False)
                        finally:
                            if session is not snapshot._session: session.release()
                            snapshot._session.release()
                    else:
                        session.release()
                else:
                    if session is not source_session: session.release()
                raise
        self._session = session
        self._owned_log = log_path is None
        self.log_path = requested_log if requested_log is not None else session.root / ("db-" + uuid.uuid4().hex + ".log")
        if self._remote is not None:
            self._remote.log_path, self._remote.owned_log = self.log_path, self._owned_log
        target_request_started = False
        try:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            fields = dict(log_path=str(self.log_path), query_timeout=f"{query_timeout}s",
                          startup_timeout=f"{startup_timeout}s", shutdown_timeout=f"{shutdown_timeout}s", owned_log=self._owned_log)
            if snapshot is None or transfer is not None:
                if transfer is not None:
                    fields["transfer_path"] = str(transfer)
                target_request_started = True
                reply = session.request("start", response_timeout=startup_timeout+_STARTUP_REPLY_MARGIN,
                                        _cleanup=None if self._remote is None else self._remote.late_start, **fields)
            else:
                reply = session.request("fork", handle=source_handle, reservation=reservation,
                                        response_timeout=startup_timeout+_STARTUP_REPLY_MARGIN, **fields)
            ready = reply["database"]
            self._handle = ready["handle"]
            if self._remote is not None:
                self._remote.target_handle = self._handle
            self.id = ready["id"]
            self.capabilities = tuple(ready["capabilities"])
            self.diagnostics = {key: ready[key] for key in ("pid", "runtime_pid")}
            self.diagnostics["host_pid"] = self.diagnostics.pop("pid")
            self._connection_info = {key: ready[key] for key in ("host", "port", "user", "password", "database")}
            if self._remote is not None:
                self._remote.remove_scratch()
        except BaseException:
            try:
                if self._remote is not None and not target_request_started:
                    # No target request exists to own a late result. Exported
                    # source state must still be acknowledged and reclaimed.
                    self._remote.finish({"disposed": True})
                if self._handle is not None and not session.failed:
                    try:
                        cleanup = session.request("db_close", handle=self._handle, response_timeout=shutdown_timeout+25,
                                                  _cleanup=False if self._remote is None else self._remote.late_close)
                        if self._remote is not None: self._remote.finish(cleanup)
                    except Exception:
                        pass
            finally:
                try:
                    if reservation is not None and self._remote is None:
                        session.request("fork_cancel", handle=source_handle, reservation=reservation, response_timeout=5, _cleanup=False)
                finally:
                    self._dispose()
            raise

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
                if self._remote is not None and self._remote.error is not None:
                    self._remote.retry()
                if self._close_error is not None:
                    raise self._close_error
                return
            try:
                if not self._session.failed:
                    reply = self._request("db_close", self._shutdown_timeout+25,
                                          _cleanup=None if self._remote is None else self._remote.late_close,
                                          _cleanup_errors=False)
                    self._logs = reply.get("logs", self._logs)
                    if self._remote is not None:
                        self._remote.finish(reply)
                elif self._remote is not None:
                    self._remote.finish({"disposed": False})
            except HostError as exc:
                reply = getattr(exc, "response", {})
                if self._remote is not None and reply:
                    self._remote.finish(reply)
                if not exc.closed or reply.get("disposed") is False or (self._remote is not None and not reply):
                    self._close_error = exc
                    raise
            except BaseException as exc:
                self._close_error = exc
                raise
            finally:
                self._dispose()

    def snapshot(self, *, max_forks=None, rollback=False, timeout=120):
        """Consume this DB and own a fixed in-memory baseline for independent Forks."""
        _positive(timeout)
        from ._forklimit import capacity
        limit = capacity(max_forks)
        if not isinstance(rollback, bool):
            raise ValueError("rollback must be a bool")
        if "fork-limit-v1" not in self._session.capabilities:
            raise HostError("Host lacks fork-limit-v1; use the matching new host binary/wheel",
                            code="unsupported", stage="fork_capability", closed=False)
        with self._lock:
            try:
                reply = self._request("snapshot", response_timeout=None, rollback=rollback, timeout=f"{timeout}s", max_forks=limit,
                                      _cleanup=None if self._remote is None else self._remote.late_capture,
                                      _cleanup_errors=False)
            except HostError as exc:
                if exc.closed:
                    try:
                        if self._remote is not None and hasattr(exc, "response"):
                            self._remote.finish(exc.response)
                    finally:
                        self._dispose()
                raise
            self._logs = reply.get("logs", self._logs)
            baseline = None
            try:
                baseline = Snapshot._from_host(self._session, reply["snapshot"], self._options, reply["max_forks"])
                if self._remote is not None:
                    self._remote.finish(reply)
            except BaseException:
                try:
                    if baseline is not None:
                        baseline.close()
                    else:
                        self._session.request("snapshot_close", handle=reply["snapshot"], response_timeout=60, _cleanup=False)
                finally:
                    self._dispose()
                raise
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
        try:
            if self._owned_log and (self._remote is None or self._remote.target_done):
                self.log_path.unlink(missing_ok=True)
        finally:
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

from ._prepare import PrepareCommand
