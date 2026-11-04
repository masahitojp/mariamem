"""Deterministic ownership failure oracles; no Django or host dependency."""
import pytest
from mariamem.django._lifecycle import Owners, preserving_cleanup


class Handle:
    def __init__(self, *, fail=None):
        self.fail = fail
        self.closed = False
        self.calls = []
        self.capture_options = []
        self.fork_timeouts = []

    def close(self):
        self.calls.append('close')
        if self.fail == 'close':
            raise OSError('close failed')
        self.closed = True

    def wait_disconnected(self, *, timeout):
        self.calls.append('disconnect')
        if self.fail == 'disconnect':
            raise TimeoutError('active connection')

    def snapshot(self, *, timeout, max_forks=None):
        self.calls.append('snapshot')
        self.capture_options.append(max_forks)
        if self.fail == 'capture-preserve':
            raise RuntimeError('busy source preserved')
        self.closed = True
        if self.fail == 'capture-consume':
            raise RuntimeError('source consumed before error')
        return Handle()

    def fork(self, *, timeout=None):
        self.fork_timeouts.append(timeout)
        if self.fail == 'fork':
            raise OSError('fork failed')
        return Handle()


def test_capture_disconnect_then_consume():
    owners = Owners()
    source = owners.own(Handle())
    baseline = owners.capture(source)
    child = owners.fork(baseline)
    assert source.calls == ['disconnect', 'snapshot']
    assert source.closed and not baseline.closed and not child.closed
    owners.close()
    assert all(handle.closed for handle in (source, baseline, child))


@pytest.mark.parametrize('failure,consumed', [('disconnect', False),
    ('capture-preserve', False), ('capture-consume', True)])
def test_failed_capture_retains_source_for_finalization(failure, consumed):
    owners = Owners()
    source = owners.own(Handle(fail=failure))
    with pytest.raises((RuntimeError, TimeoutError)):
        owners.capture(source)
    assert source.closed is consumed
    assert owners.handles == [source]
    owners.close()
    assert source.closed


def test_close_failure_blocks_admission_and_still_finalizes_siblings():
    owners = Owners()
    good = owners.own(Handle())
    bad = owners.own(Handle(fail='close'))
    with pytest.raises(BaseExceptionGroup, match='owner cleanup'):
        owners.close()
    assert good.closed
    with pytest.raises(RuntimeError, match='admission stopped'):
        owners.fork(good)
    bad.fail = None
    owners.close()
    assert bad.closed
    # Successful later cleanup must not silently reopen this failed run.
    with pytest.raises(RuntimeError, match='admission stopped'):
        owners.guard()


def test_fork_failure_does_not_lose_baseline():
    owners = Owners()
    base = owners.own(Handle(fail='fork'))
    with pytest.raises(OSError, match='fork failed'):
        owners.fork(base)
    owners.close()
    assert base.closed


def test_primary_and_cleanup_errors_both_preserved():
    original, cleanup = ValueError('seed'), OSError('cleanup')
    def close():
        raise cleanup
    with pytest.raises(BaseExceptionGroup) as caught:
        with preserving_cleanup(close):
            raise original
    assert caught.value.exceptions == (original, cleanup)


def test_cleanup_after_success_and_unchanged_primary():
    calls = []
    with preserving_cleanup(lambda: calls.append('closed')):
        calls.append('body')
    original = KeyboardInterrupt()
    with pytest.raises(KeyboardInterrupt) as caught:
        with preserving_cleanup(lambda: calls.append('closed')):
            raise original
    assert caught.value is original
    assert calls == ['body', 'closed', 'closed']


def test_keep_only_final_teardown_owner():
    owners = Owners()
    base, final = owners.own(Handle()), owners.own(Handle())
    owners.close(keep=final)
    assert base.closed and not final.closed
    owners.close()
    assert final.closed


def test_import_and_invalid_settings_do_not_start_host(monkeypatch):
    import mariamem
    from mariamem.django import prepared_database
    def forbidden(**options):
        raise AssertionError('unexpected acquisition')
    monkeypatch.setattr(mariamem, 'start', forbidden)
    with pytest.raises(ValueError, match='test_name'):
        prepared_database(test_name='application')


def test_settings_declaration_is_lazy_and_explicit_start_is_owned(monkeypatch):
    import copy
    import mariamem
    from mariamem.django import prepared_database
    source = Handle()
    source.connection_info = lambda: dict(host='127.0.0.1', port=123, user='root', password='')
    monkeypatch.setattr(mariamem, 'start', lambda **options: source)
    settings = prepared_database()
    config = settings['MARIAMEM_PREPARED']
    assert config.source is None
    assert copy.deepcopy(settings)['MARIAMEM_PREPARED'] is config
    assert config.start() is source
    assert not source.closed
    config.close()
    config.close()
    assert source.closed


@pytest.mark.parametrize('options', [dict(max_forks=0), dict(max_forks=True),
    dict(max_forks=2**100), dict(fork_timeout=None), dict(fork_timeout=0),
    dict(fork_timeout=float('inf')), dict(fork_timeout=2**100)])
def test_capacity_declaration_rejects_invalid_values_without_acquisition(monkeypatch, options):
    import mariamem
    from mariamem.django import prepared_database
    monkeypatch.setattr(mariamem, 'start', lambda **kw: pytest.fail('unexpected host'))
    with pytest.raises(ValueError):
        prepared_database(**options)


def test_declaration_settings_are_not_forwarded_to_root_start(monkeypatch):
    import mariamem
    from mariamem.django import prepared_database
    seen = []
    monkeypatch.setattr(mariamem, 'start', lambda **kw: seen.append(kw) or Handle())
    config = prepared_database(options={'startup_timeout': 7}, max_forks=1,
                               fork_timeout=.5)['MARIAMEM_PREPARED']
    assert config.source is None
    assert (config.max_forks, config.fork_timeout) == (1, .5)
    config.start()
    assert seen == [{'startup_timeout': 7}]
    config.close()


def test_successfully_retired_handles_are_not_retained_for_entire_run():
    owners = Owners()
    source = owners.own(Handle())
    base = owners.capture(source)
    assert owners.handles == [base]
    for _ in range(100):
        child = owners.fork(base)
        owners.retire(child)
        assert owners.handles == [base]
    owners.close()
    assert owners.handles == []


@pytest.fixture
def manager(monkeypatch):
    import sys
    from types import SimpleNamespace
    from mariamem.django._database import Configuration, Manager
    connection = SimpleNamespace(settings_dict=dict(NAME='original', HOST='old'), in_atomic_block=False)
    closes = []
    class Connections:
        def __getitem__(self, alias):
            assert alias == 'default'
            return connection
        def close_all(self):
            closes.append(True)
    monkeypatch.setitem(sys.modules, 'django.db', SimpleNamespace(connections=Connections()))
    monkeypatch.setitem(sys.modules, 'django.core.exceptions',
                        SimpleNamespace(ImproperlyConfigured=ValueError))
    monkeypatch.setitem(sys.modules, 'django.conf', SimpleNamespace(settings=SimpleNamespace()))
    monkeypatch.setattr(Handle, 'connection_info', lambda self: dict(host='new', port=123, user='root', password=''), raising=False)
    config = Configuration({})
    config.source = Handle()
    return Manager(config), connection, config


def test_manager_restores_settings_and_closes_all_handles(manager):
    m, connection, config = manager
    assert connection.settings_dict['HOST'] == 'new'
    m.prepare()
    base = m.base
    m.finish_databases()
    final = m.teardown
    assert base.closed and not final.closed
    config.close()
    assert final.closed
    assert connection.settings_dict == dict(NAME='original', HOST='old')
    assert config.source is None and config.manager is None


def test_class_capture_failure_releases_source_without_admitting_body(manager):
    from mariamem.django._database import Scope
    m, connection, config = manager
    m.prepare()
    scope = Scope(m)
    scope.source.fail = 'capture-preserve'
    with pytest.raises(RuntimeError, match='source preserved'):
        scope.acquire()
    assert scope.child is None
    scope.close()
    assert scope.source.closed
    config.close()


def test_child_disconnect_failure_stops_next_body_but_final_close_reaps(manager):
    from mariamem.django._database import Scope
    m, connection, config = manager
    m.prepare()
    scope = Scope(m)
    scope.acquire()
    child = scope.child
    child.fail = 'disconnect'
    with pytest.raises(TimeoutError, match='active connection'):
        scope.release()
    with pytest.raises(RuntimeError, match='admission stopped'):
        scope.acquire()
    config.close()
    assert child.closed


def test_cleanup_error_keeps_original_and_attempts_other_handles(manager):
    m, connection, config = manager
    m.prepare()
    m.base.fail = 'close'
    child = m.owners.fork(m.base)
    with pytest.raises(BaseExceptionGroup):
        config.close()
    assert child.closed
    assert connection.settings_dict == dict(NAME='original', HOST='old')
    m.base.fail = None
    config.close()


def test_atomic_switch_refusal_then_final_retirement(manager):
    m, connection, config = manager
    connection.in_atomic_block = True
    with pytest.raises(RuntimeError, match='atomic block'):
        m.quiesce()
    with pytest.raises(RuntimeError, match='atomic block'):
        config.close()
    assert m.source.closed
    connection.in_atomic_block = False
    config.close()


def bounded_run(manager, max_forks):
    """Controlled SDK model: a retained source really occupies its parent slot."""
    m, _, config = manager
    captures, forks = [], []
    auto = iter((2, 3, 4))

    class Bounded(Handle):
        def __init__(self, parent=None, limit=None):
            super().__init__()
            self.parent, self.limit, self.occupied = parent, limit, 0

        def close(self):
            was_closed = self.closed
            super().close()
            if not was_closed and self.parent is not None:
                self.parent.occupied -= 1

        def snapshot(self, *, timeout, max_forks):
            if self.fail == 'capture-preserve':
                raise RuntimeError('preserved class source')
            self.close()
            if self.fail == 'capture-consume':
                raise RuntimeError('consumed class source')
            limit = next(auto) if max_forks is None else max_forks
            base = Bounded(limit=limit)
            captures.append((max_forks, limit))
            return base

        def fork(self, *, timeout):
            forks.append((self, timeout))
            assert not self.closed
            assert self.occupied < self.limit, 'teardown requested before child retirement'
            self.occupied += 1
            return Bounded(parent=self)

    m.owners.handles.clear()
    m.source = config.source = m.owners.own(Bounded())
    config.max_forks = m.owners.max_forks = max_forks
    config.fork_timeout = m.owners.fork_timeout = .5
    return m, config, captures, forks


@pytest.mark.parametrize('max_forks', [None, 1])
def test_bounded_class_children_and_final_drop_with_independent_capture_policy(manager, max_forks):
    from mariamem.django._database import Scope
    m, config, captures, forks = bounded_run(manager, max_forks)
    try:
        m.prepare()
        run_base = m.base
        scope = Scope(m)
        for _ in range(2):
            scope.acquire()
            assert scope.child.parent is scope.base
            scope.release()
        scope.close()
        m.finish_databases()
        assert captures == ([(None, 2), (None, 3)] if max_forks is None else [(1, 1), (1, 1)])
        assert all(timeout == .5 for _, timeout in forks)
        assert m.teardown.parent is run_base and run_base.occupied == 1
        assert run_base.closed and not m.teardown.closed
    finally:
        config.close()
    assert run_base.occupied == 0


@pytest.mark.parametrize('failure', [None, 'capture-preserve', 'capture-consume'])
def test_final_drop_retires_retained_class_source_before_reacquiring_cap1(manager, failure):
    from mariamem.django._database import Scope
    m, config, _, _ = bounded_run(manager, 1)
    try:
        m.prepare()
        scope = Scope(m)
        scope.source.fail = failure
        if failure is not None:
            with pytest.raises(RuntimeError, match='class source'):
                scope.acquire()
        # Simulate class setup/capture abort before its ordinary close hook.
        m.finish_databases()
        assert scope.source.closed
        assert m.teardown is not None and not m.teardown.closed
    finally:
        config.close()


def test_unconfirmed_child_cleanup_aborts_drop_and_still_retires_other_owners(manager):
    from mariamem.django._database import Scope
    m, config, _, forks = bounded_run(manager, 1)
    m.prepare()
    scope = Scope(m)
    scope.source.fail = 'close'
    try:
        with pytest.raises(BaseExceptionGroup, match='operation and cleanup'):
            m.finish_databases()
        assert len(forks) == 1  # Only class preparation, no emergency DROP child.
        assert m.teardown is None and m.base.closed
        assert scope.source in m.owners.handles
        assert m.owners.debt
    finally:
        scope.source.fail = None
        config.close()


@pytest.mark.parametrize('shadow_marker,fixtures', [(True, []), (False, ['mariamem_app_db'])])
def test_collection_exclusion_without_optional_framework_dependency(monkeypatch, shadow_marker, fixtures):
    import sys
    from types import SimpleNamespace
    from mariamem.django import pytest_plugin
    # Keep the ordinary daily policy check independent of optional Django/C.
    base = type('Case', (), {})
    monkeypatch.setitem(sys.modules, 'django.test', SimpleNamespace(SimpleTestCase=base))
    monkeypatch.setitem(sys.modules, 'django.core.exceptions', SimpleNamespace(ImproperlyConfigured=ValueError))
    monkeypatch.setitem(sys.modules, 'mariamem.django._cases', SimpleNamespace(validate_case=lambda cls: None))
    monkeypatch.setattr(pytest_plugin, '_entry', lambda config: None)
    item = SimpleNamespace(cls=base, fixturenames=fixtures,
        get_closest_marker=lambda name: object() if shadow_marker and name == 'shadow_maria' else None)
    with pytest.raises(pytest.UsageError, match='cannot share a run'):
        pytest_plugin.pytest_collection_modifyitems(None, [item])
