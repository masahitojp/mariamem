"""Run ownership using only the public mariamem SDK; no Django imports."""
from contextlib import contextmanager


@contextmanager
def preserving_cleanup(cleanup):
    """Keep the triggering failure when cleanup also fails."""
    try:
        yield
    except BaseException as original:
        try:
            cleanup()
        except BaseException as failure:
            raise BaseExceptionGroup('mariamem operation and cleanup failed',
                                     [original, failure]) from None
        raise
    else:
        cleanup()


class Owners:
    """Retain live handles and failed closes; forget successfully retired owners."""
    def __init__(self, *, max_forks=None, fork_timeout=30):
        self.handles = []
        self.debt = False
        self.max_forks, self.fork_timeout = max_forks, fork_timeout

    def own(self, handle):
        self.handles.append(handle)
        return handle

    def guard(self):
        if self.debt:
            raise RuntimeError('mariamem cleanup failed; further test admission stopped')

    def capture(self, database):
        database.wait_disconnected(timeout=5)
        baseline = self.own(database.snapshot(timeout=30, max_forks=self.max_forks))
        self._forget(database)  # A successful capture consumes its source.
        return baseline

    def fork(self, baseline):
        self.guard()
        return self.own(baseline.fork(timeout=self.fork_timeout))

    def _forget(self, handle):
        self.handles[:] = [owned for owned in self.handles if owned is not handle]

    def retire(self, handle):
        try:
            # Consumed sources may be closed again; the SDK makes this safe.
            handle.close()
            self._forget(handle)
        except BaseException:
            self.debt = True
            raise

    def close(self, *, keep=None):
        errors = []
        for handle in reversed(tuple(self.handles)):
            if handle is keep:
                continue
            try:
                self.retire(handle)
            except BaseException as error:
                errors.append(error)
        if errors:
            raise BaseExceptionGroup('mariamem owner cleanup failed', errors)
