"""Daily runtime checks reuse one host and do not invoke release campaigns."""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))


def test_daily_smoke_is_bounded_and_reuses_its_host(monkeypatch):
    import verify
    calls = []
    monkeypatch.setattr(verify, 'run', lambda argv, **kw: calls.append((argv, kw)))
    verify.smoke()
    assert len(calls) == 5
    build = calls[0][0]
    host = build[build.index('-o')+1]
    assert calls[1][0][-3:] == ['tests/live_acceptance/smoke.py', '--host', host]
    assert calls[2][0] == ['go', 'run', './tests/live_acceptance/go_consumer', '-source-smoke']
    assert calls[3][0] == ['go', 'test', '-p', '1', '-vet=off', '-tags', 'integration', './tests/godefault', '-run', '^TestInProcess', '-count=1']
    assert calls[4][0] == ['go', 'test', '-p', '1', '-vet=off', '-tags', 'integration', './tests/gointegration', '-run', '^TestShutdownModeSnapshotAndResnapshot$', '-count=1']
    assert all(kw['env']['PYTHONPATH'] == str(ROOT/'python') for _, kw in calls)


def test_full_integration_retains_regressions_without_duplicate_routing(monkeypatch):
    import verify
    calls = []
    monkeypatch.setattr(verify, 'run', lambda argv, **kw: calls.append(argv))
    verify.integration()
    assert any('-run=TestWorkerTrapActualGuest' in a for a in calls)
    assert any('scripts/check_prepared_consumers.py' in a for a in calls)
    race = next(a for a in calls if a[:3] == ['go', 'test', '-race'])
    assert {'./internal/live', './internal/generatedgo', './internal/generatedgo/code/base'} <= set(race)
    for package in ('./tests/gointegration', './tests/godefault', './tests/generatedmemory'):
        assert '-race' not in next(a for a in calls if package in a)
    assert any('tests/test_python_wire.py' in a and 'tests/test_owned_snapshot.py' in a for a in calls)
    assert not any('tests/routing_acceptance/run.py' in a for a in calls)


def test_release_integration_reuses_verified_host_without_build(monkeypatch, tmp_path):
    import verify
    import git_identity
    host = tmp_path/'host'
    checked = []
    monkeypatch.setattr(git_identity, 'verify_go_binary', lambda *args: checked.append(args))
    monkeypatch.setattr(verify.subprocess, 'check_output', lambda *a, **kw: 'a'*40+'\n')
    calls = []
    monkeypatch.setattr(verify, 'run', lambda argv, **kw: calls.append(argv))
    verify.integration(host)
    assert checked == [(ROOT, host, 'a'*40)]
    assert not any(a[:2] == ['go', 'build'] for a in calls)
    assert any('tests/live_acceptance/smoke.py' in a and host in a for a in calls)
    assert any('scripts/check_prepared_consumers.py' in a and host in a for a in calls)


def test_unverified_shared_host_stops_before_any_integration(monkeypatch, tmp_path):
    import pytest
    import verify
    import git_identity
    monkeypatch.setattr(verify.subprocess, 'check_output', lambda *a, **kw: 'a'*40+'\n')
    def reject(*args): raise ValueError('wrong source')
    monkeypatch.setattr(git_identity, 'verify_go_binary', reject)
    monkeypatch.setattr(verify, 'run', lambda *a, **kw: pytest.fail('must reject before executing'))
    with pytest.raises(ValueError, match='wrong source'): verify.integration(tmp_path/'host')


def test_retired_native_override_cannot_change_integration(monkeypatch, tmp_path):
    import verify
    calls = []
    monkeypatch.setenv('MARIAMEM_NATIVE_DIR', str(tmp_path))
    monkeypatch.setattr(verify, 'run', lambda argv, **kw: calls.append((argv, kw['env'])))
    verify.integration()
    assert all('MARIAMEM_NATIVE_DIR' not in env for _, env in calls)
    assert all(env['MARIAMEM_TEST_DEFAULT'] == '1' for _, env in calls)
