"""Controlled cleanup/ack failures on the private remote-child owner.

These prove ownership ordering, not an actual guest crash or filesystem fault.
Framed transport/real-host behavior has separate tests.
"""
import threading
from types import SimpleNamespace

import pytest

from mariamem import HostError
from mariamem._handoff import RemoteLease


class SessionDouble:
    def __init__(self, root):
        self.root = root
        root.mkdir()
        self._lock = threading.RLock()
        self._handoffs = set()
        self._exited = threading.Event()
        self.failed = False
        self.releases = 0
        self.calls = []
        self.handlers = {}

    def request(self, op, **fields):
        self.calls.append((op, fields))
        if op in self.handlers:
            return self.handlers[op](**fields)
        return {'disposed': True}

    def release(self):
        self.releases += 1
        assert self.releases == 1, 'source retain returned twice'


@pytest.fixture
def remote(tmp_path):
    class Parent:
        def __init__(self):
            self._lock = threading.RLock()
            self._admission_error = None
            self._debt_version = 0
    parent = Parent()
    source, target = (SessionDouble(tmp_path/name) for name in ('source', 'target'))
    scratch = source.root/'handoff'
    scratch.mkdir()
    owner = RemoteLease(parent, source, 7, 'a'*32, scratch, target)
    owner.exported = True
    owner.target_handle = 11
    yield SimpleNamespace(owner=owner, parent=parent, source=source, target=target)
    source.failed = target.failed = True
    source._exited.set()
    target._exited.set()


def test_source_ack_failure_retains_owner_and_explicit_retry_is_idempotent(remote):
    r = remote
    cause = OSError('injected source acknowledgement failure')
    def fail(**fields): raise cause
    r.source.handlers['handoff_release'] = fail
    with pytest.raises(HostError) as error:
        r.owner.finish({'disposed': True})
    assert error.value.__cause__ is cause
    assert not r.owner.done and r.source.releases == 0
    assert r.owner in r.source._handoffs
    assert r.parent._admission_error.stage == 'fork_admission'
    del r.source.handlers['handoff_release']
    r.owner.retry()
    r.owner.retry()
    r.owner.late_close({'disposed': True})
    assert r.owner.done and r.source.releases == 1
    assert not r.source._handoffs
    # Settlement must not silently reopen the failed parent's admission.
    assert r.parent._admission_error is not None


def test_unknown_target_cleanup_cannot_ack_source_until_confirmed(remote):
    r = remote
    r.target.handlers['db_cleanup'] = lambda **kw: {'disposed': False}
    with pytest.raises(HostError, match='target cleanup remains incomplete'):
        r.owner.finish({'disposed': False})
    assert not any(op == 'handoff_release' for op, _ in r.source.calls)
    assert r.owner.scratch.exists() and r.source.releases == 0
    r.target.handlers['db_cleanup'] = lambda **kw: {'disposed': True}
    r.owner.retry()
    assert r.owner.done and not r.owner.scratch.exists()


def test_export_cleanup_token_is_retried_on_source_not_target(remote):
    r = remote
    r.owner.exported = False
    r.owner.target_handle = None  # A late export never starts a target.
    r.source.handlers['cleanup_status'] = lambda **kw: {'disposed': False}
    r.owner.late_export({'closed': True, 'disposed': False, 'cleanup': 'b'*32})
    assert r.owner.error is not None and r.source.releases == 0
    assert not r.target.calls
    r.source.handlers['cleanup_status'] = lambda **kw: {'disposed': True}
    r.owner.retry()
    assert r.owner.done and r.source.releases == 1
    assert not r.target.calls


def test_failed_unreturned_snapshot_close_is_retained_for_retry(remote):
    r = remote
    cause = OSError('injected returned baseline cleanup failure')
    def fail(**fields): raise cause
    r.target.handlers['snapshot_close'] = fail
    r.owner.late_capture({'closed': True, 'disposed': True, 'snapshot': 22})
    assert r.owner.error is not None and r.source.releases == 0
    r.target.handlers['snapshot_close'] = lambda **kw: {'closed': False}
    r.owner.retry()
    assert [kw['handle'] for op, kw in r.target.calls if op == 'snapshot_close'] == [22, 22]
    assert r.owner.done and r.source.releases == 1


@pytest.mark.parametrize('submitted', [False, True])
def test_unsent_start_and_unknown_start_have_different_disposal_requirements(remote, submitted):
    r = remote
    r.owner.target_handle = None
    failure = TimeoutError('injected startup watchdog')
    failure.submitted = submitted
    r.owner.late_start(failure)
    assert r.owner.done is (not submitted)
    assert r.source.releases == int(not submitted)
    if submitted:
        assert r.parent._admission_error is not None
        # A late successful start is closed before the source is acknowledged.
        r.owner.late_start({'database': {'handle': 99}})
        assert any(op == 'db_close' and kw['handle'] == 99 for op, kw in r.target.calls)
        assert r.owner.done and r.source.releases == 1


def test_source_transport_failure_waits_for_actual_exit_before_settlement(remote):
    r = remote
    r.source.failed = True
    with pytest.raises(HostError, match='source process exit is not confirmed'):
        r.owner.finish({'disposed': True})
    assert r.source.releases == 0 and r.owner.scratch.exists()
    r.source._exited.set()
    r.owner.retry()
    assert r.owner.done and r.source.releases == 1
    assert not any(op == 'handoff_release' for op, _ in r.source.calls)
