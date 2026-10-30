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
    assert len(calls) == 3
    build = calls[0][0]
    host = build[build.index('-o')+1]
    assert calls[1][0][-3:] == ['tests/live_acceptance/smoke.py', '--host', host]
    assert calls[2][0] == ['go', 'run', './tests/live_acceptance/go_consumer', '-source-smoke']
    assert all(kw['env']['PYTHONPATH'] == str(ROOT/'python') for _, kw in calls)


def test_full_integration_retains_regressions_without_duplicate_routing(monkeypatch):
    import verify
    calls = []
    monkeypatch.setattr(verify, 'run', lambda argv, **kw: calls.append(argv))
    verify.integration()
    assert any('-run=TestWorkerTrapActualGuest' in a for a in calls)
    assert any('scripts/check_prepared_consumers.py' in a for a in calls)
    assert any('./internal/live' in a and '-race' in a for a in calls)
    assert any('tests/test_python_wire.py' in a and 'tests/test_owned_snapshot.py' in a for a in calls)
    assert not any('tests/routing_acceptance/run.py' in a for a in calls)
