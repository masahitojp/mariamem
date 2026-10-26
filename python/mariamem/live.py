"""Stable local endpoint over private children owned by the Go host."""
import threading
import uuid


class Live:
    """Create with Snapshot.live(); quiesce app work/connections before reset."""

    def __init__(self, *args, **kwargs):
        raise TypeError("Create a Live with Snapshot.live()")

    @classmethod
    def _from_snapshot(cls, snapshot):
        from . import HostError
        self = cls.__new__(cls)
        self._lock = threading.RLock()
        self._closed = self._closing = False
        self._close_done = threading.Event()
        self._close_error = None
        self._handle = None
        self._status = {"state": "closed", "generation": 0, "active_connections": 0}
        with snapshot._lock:
            if snapshot._closed:
                raise HostError("Snapshot is closed", code="closed", stage="live_precondition", closed=False)
            session = snapshot._session
            if "live-v1" not in session.capabilities:
                raise HostError("Host lacks live-v1; use the matching new host binary/wheel",
                                code="unsupported", stage="live_capability", closed=False)
            session.retain()
            self._session = session
            self._snapshot = snapshot
            options = snapshot._options.copy()
        try:
            reply = session.request("live_create", handle=snapshot._handle,
                                    log_path=str(session.root / ("live-" + uuid.uuid4().hex)),
                                    response_timeout=options["startup_timeout"] + 15)
            ready = reply["live"]
            self._handle = ready["handle"]
            self._info = {k: ready[k] for k in ("host", "port", "user", "password", "database")}
            self._status = reply["status"]
        except BaseException as original:
            try:
                if self._handle is not None and not session.failed:
                    session.request("live_close", handle=self._handle, response_timeout=None)
            except BaseException as cleanup:
                raise BaseExceptionGroup("Live creation and cleanup failed", [original, cleanup])
            finally:
                session.release()
            raise
        return self

    @property
    def closed(self):
        with self._lock:
            return self._closed or self._session.failed

    def connection_info(self):
        """Endpoint metadata stays readable after Close; then it cannot be used."""
        return self._info.copy()

    def _request(self, op, **fields):
        from . import HostError
        with self._lock:
            if self._closed or self._closing:
                raise HostError("Live is closed", code="closed", stage="live_control", closed=True)
            handle = self._handle
        return self._session.request(op, handle=handle, response_timeout=None, **fields)

    def status(self):
        with self._lock:
            if self._closed:
                return self._status.copy()
        reply = self._request("live_status")
        with self._lock:
            if not self._closed:
                self._status = reply["status"]
            return self._status.copy()

    def reset(self, *, timeout=120, drain_timeout=5):
        """Restore baseline after all physical SQL sessions close.

        Busy preserves the current generation. Replacement failure refuses SQL
        until an explicit successful reset. Any exception stops test admission.
        The host owns the deadline and the reset's authoritative commit outcome;
        compensating cleanup may outlast timeout.
        """
        from . import _positive
        for value in (timeout, drain_timeout):
            if isinstance(value, bool):
                raise ValueError("timeouts must be positive finite numbers")
            _positive(value)
        reply = self._request("live_reset", timeout=f"{timeout}s", drain_timeout=f"{drain_timeout}s")
        with self._lock:
            if not self._closed:
                self._status = reply["status"]

    def close(self):
        with self._lock:
            first = not self._closing
            self._closing = True
        if not first:
            self._close_done.wait()
            if self._close_error is not None:
                raise self._close_error
            return
        try:
            if not self._session.failed:
                reply = self._session.request("live_close", handle=self._handle, response_timeout=None)
                self._status = reply.get("status", self._status)
        except BaseException as exc:
            self._close_error = exc
            raise
        finally:
            with self._lock:
                self._closed = True
                self._status = dict(self._status, state="closed")
            try:
                self._session.release()
            finally:
                self._close_done.set()

    def __enter__(self):
        if self.closed:
            from . import HostError
            raise HostError("Live is closed", code="closed", stage="live_control", closed=True)
        return self

    def __exit__(self, kind, original, traceback):
        try:
            self.close()
        except BaseException as cleanup:
            if original is not None:
                raise BaseExceptionGroup("Application and Live cleanup failed", [original, cleanup])
            raise
