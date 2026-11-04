"""An immutable, process-local baseline. Persistence is intentionally absent."""
import threading
import time


class Snapshot:
    def __init__(self, *args, **kwargs):
        raise TypeError("Create a Snapshot with Database.snapshot(); saved snapshots are no longer supported")

    @classmethod
    def _from_host(cls, session, handle, options, max_forks):
        from ._forklimit import capacity
        capacity(max_forks)
        self = cls.__new__(cls)
        self._lock = threading.RLock()
        self._session = session
        self._handle = handle
        self._options = options.copy()
        self._closed = False
        self._close_done = threading.Event()
        self._close_error = None
        self._admission_closed = threading.Event()
        self._admission_error = None
        self._debt_version = 0
        self._max_forks = max_forks
        session.retain()
        return self

    @property
    def max_forks(self):
        return self._max_forks

    def fork(self, *, timeout=None, **options):
        from . import Database
        if "fork_timeout" in options:
            raise TypeError("Snapshot.fork uses timeout; fork_timeout belongs to Database(snapshot=...)")
        return Database(**{**self._options, **options, "snapshot": self, "fork_timeout": timeout})

    def _reserve(self, session, handle, timeout):
        from . import HostError
        from ._forklimit import wait_nanoseconds
        wait_nanoseconds(timeout)
        deadline = None if timeout is None else time.monotonic()+timeout
        occupied = 'unknown'  # No responsive capacity observation yet.
        while True:
            if self._admission_closed.is_set():
                raise HostError("Snapshot is closed", code="closed", stage="fork_wait", closed=False)
            if self._admission_error is not None:
                raise self._admission_error
            left = None if deadline is None else deadline-time.monotonic()
            if left is not None and left <= 0:
                raise HostError(f"Fork capacity wait timed out (max_forks={self._max_forks}, "
                                f"occupied_slots={occupied}; close owned children or increase max_forks)",
                                code="pool_timeout", stage="fork_wait", closed=False)
            reply = session.request("fork_reserve", handle=handle,
                                    response_timeout=5 if left is None else min(5,left))
            if reply["full"]:
                occupied = reply.get("occupied_slots", "unknown")
            if not reply["full"]:
                reservation = reply["reservation"]
                if self._admission_closed.is_set() or self._admission_error is not None:
                    session.request("fork_cancel", handle=handle, reservation=reservation,
                                    response_timeout=5, _cleanup=False)
                    if self._admission_error is not None:
                        raise self._admission_error
                    raise HostError("Snapshot is closed", code="closed", stage="fork_wait", closed=False)
                return reservation
            left = .25 if deadline is None else min(.25,max(0,deadline-time.monotonic()))
            self._admission_closed.wait(left)

    def live(self):
        """Borrow this open baseline for a host-owned stable endpoint."""
        from .live import Live
        return Live._from_snapshot(self)

    def close(self):
        from . import HostError
        with self._lock:
            first = not self._closed
            self._closed = True
            self._admission_closed.set()
        if not first:
            self._close_done.wait()
            if self._close_error is not None:
                raise self._close_error
            return
        try:
            if not self._session.failed:
                try:
                    self._session.request("snapshot_close", handle=self._handle, response_timeout=60)
                except HostError as exc:
                    if not exc.closed:
                        raise
        except BaseException as exc:
            self._close_error = exc
            raise
        finally:
            try:
                with self._session._lock:
                    owners = [o for o in self._session._handoffs if o.parent() is self]
                try:
                    for owner in owners:
                        owner.parent_closed()
                finally:
                    self._session.release()
            finally:
                self._close_done.set()

    def __enter__(self):
        from . import HostError
        if self._closed or self._session.failed:
            raise ValueError("Snapshot is closed")
        return self

    def __exit__(self, *exc):
        self.close()
