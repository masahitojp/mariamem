"""An immutable, process-local baseline. Persistence is intentionally absent."""
import threading


class Snapshot:
    def __init__(self, *args, **kwargs):
        raise TypeError("Create a Snapshot with Database.snapshot(); saved snapshots are no longer supported")

    @classmethod
    def _from_host(cls, session, handle, options):
        self = cls.__new__(cls)
        self._lock = threading.RLock()
        self._session = session
        self._handle = handle
        self._options = options.copy()
        self._closed = False
        self._close_done = threading.Event()
        self._close_error = None
        session.retain()
        return self

    def fork(self, **options):
        from . import Database
        return Database(**{**self._options, **options, "snapshot": self})

    def live(self):
        """Borrow this open baseline for a host-owned stable endpoint."""
        from .live import Live
        return Live._from_snapshot(self)

    def close(self):
        from . import HostError
        with self._lock:
            first = not self._closed
            self._closed = True
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
