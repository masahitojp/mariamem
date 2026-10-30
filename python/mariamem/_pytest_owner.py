"""Worker-local entry ownership, leaving ordinary pytest failures untouched."""
from ._prepare import _add_note, _attach_cleanup


class _Operation:
    def __init__(self, owner, stage, cleanup):
        self.owner, self.stage, self.cleanup = owner, stage, cleanup

    def __enter__(self):
        return self

    def __exit__(self, kind, error, traceback):
        if error is not None:
            self.owner.fail(self.stage, error, cleanup=self.cleanup,
                            uncertain=self.stage == 'capture')
        return False


class _Context:
    def __init__(self, owner, factory, stage):
        self.owner, self.factory, self.stage = owner, factory, stage
        self.manager = None

    def __enter__(self):
        try:
            self.manager = self.factory()
            value = self.manager.__enter__()
        except BaseException as primary:
            self.owner.fail(self.stage, primary, uncertain=True)
            # A returned public owner can still owe Close after failed entry.
            close = getattr(self.manager, 'close', None)
            if callable(close):
                try:
                    close()
                except BaseException as cleanup:
                    self.owner.fail(self.stage + ' cleanup', cleanup, cleanup=True)
                    if isinstance(primary, Exception) and not isinstance(cleanup, Exception):
                        raise cleanup from primary
                    if not _attach_cleanup(primary, cleanup):
                        raise primary from cleanup
            raise
        self.owner.active += 1
        return value

    def __exit__(self, kind, primary, traceback):
        if primary is not None:
            self.owner.fail(self.stage, primary)
        try:
            self.manager.__exit__(kind, primary, traceback)
            self.owner.active -= 1
        except BaseException as cleanup:
            self.owner.fail(self.stage + ' cleanup', cleanup, cleanup=True)
            if primary is not None:
                if isinstance(primary, Exception) and not isinstance(cleanup, Exception):
                    raise cleanup from primary
                if not _attach_cleanup(primary, cleanup):
                    raise primary from cleanup
                raise primary
            raise
        # Public entry owners never suppress an operation failure.
        return False


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
        new = not any(s == stage and e is error for s, e in self.records)
        if new:
            self.records.append((stage, error))
        if cleanup:
            self.uncertain = True
            if self.debt is None:
                self.debt = error
            if self.stopped is not None and self.stopped is not error:
                _attach_cleanup(self.stopped, error)
        self.uncertain |= uncertain
        # Stop admission before optional/possibly immutable diagnostic metadata.
        if self.stopped is None:
            self.stopped = error
        try:
            self.uncertain |= (bool(getattr(error, 'cleanup_errors', ()))
                               or getattr(error, 'process_cleanup', None) == 'unconfirmed')
        except Exception:
            self.uncertain = True
        if new:
            action = ('retire preparation connections before capture' if stage == 'disconnect'
                      else 'inspect the original error; application cause may be unknown')
            _add_note(error, f'mariamem {stage}: dependent admission stopped for this worker; '
                            f'cleanup=pending; next: {action}')

    def operation(self, stage, *, cleanup=False):
        # Class-based contexts avoid contextlib assigning __traceback__ on
        # rethrow, which replaces frozen/read-only callback exceptions.
        return _Operation(self, stage, cleanup)

    def context(self, factory, stage):
        return _Context(self, factory, stage)


def _owner(config):
    return config._mariamem_entry_owner
