"""Worker-local entry ownership, leaving ordinary pytest failures untouched."""
from contextlib import contextmanager

from ._prepare import _attach_cleanup


class _Owner:
    def __init__(self):
        self.stopped = None
        self.debt = None
        self.records = []
        self.active = 0
        self.uncertain = False

    def summary(self):
        return {'records': [(stage, type(error).__name__) for stage, error in self.records],
                'uncertain': self.uncertain, 'active': self.active}

    def guard(self):
        if self.stopped is not None:
            import pytest
            error = pytest.UsageError('mariamem acquire: dependent admission stopped for this worker; inspect the original entry/cleanup failure')
            raise error from self.debt or self.stopped

    def fail(self, stage, error, *, cleanup=False, uncertain=False):
        if not any(s == stage and e is error for s, e in self.records):
            self.records.append((stage, error))
            action = ('retire preparation connections before capture' if stage == 'disconnect'
                      else 'inspect the original error; application cause may be unknown')
            error.add_note(f'mariamem {stage}: dependent admission stopped for this worker; '
                           f'cleanup=pending; next: {action}')
        if cleanup:
            self.uncertain = True
            if self.debt is None:
                self.debt = error
            if self.stopped is not None and self.stopped is not error:
                _attach_cleanup(self.stopped, error)
        self.uncertain |= (uncertain or bool(getattr(error, "cleanup_errors", ()))
                           or getattr(error, "process_cleanup", None) == "unconfirmed")
        if self.stopped is None:
            self.stopped = error

    @contextmanager
    def operation(self, stage, *, cleanup=False):
        try:
            yield
        except BaseException as error:
            self.fail(stage, error, cleanup=cleanup, uncertain=stage == 'capture')
            raise

    @contextmanager
    def context(self, factory, stage):
        manager = None
        try:
            manager = factory()
            value = manager.__enter__()
        except BaseException as error:
            self.fail(stage, error, uncertain=True)
            # A returned public owner can still owe Close after failed entry.
            close = getattr(manager, 'close', None)
            if callable(close):
                try:
                    close()
                except BaseException as cleanup:
                    self.fail(stage + ' cleanup', cleanup, cleanup=True)
            raise
        self.active += 1
        try:
            yield value
        except BaseException as primary:
            self.fail(stage, primary)
            try:
                manager.__exit__(type(primary), primary, primary.__traceback__)
                self.active -= 1
            except BaseException as cleanup:
                self.fail(stage + ' cleanup', cleanup, cleanup=True)
                if isinstance(primary, Exception) and not isinstance(cleanup, Exception):
                    raise cleanup from primary
                if cleanup is not primary and cleanup not in getattr(primary, 'cleanup_errors', ()):
                    _attach_cleanup(primary, cleanup)
            raise
        else:
            try:
                manager.__exit__(None, None, None)
                self.active -= 1
            except BaseException as error:
                self.fail(stage + ' cleanup', error, cleanup=True)
                raise


def _owner(config):
    return config._mariamem_entry_owner
