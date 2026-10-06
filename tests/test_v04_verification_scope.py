"""v0.4 retains focused race gates without suppressing full-guest diagnostics."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('v04_verify', ROOT/'scripts/verify.py')
verify = importlib.util.module_from_spec(spec)
spec.loader.exec_module(verify)


def commands(monkeypatch, native=None):
    calls = []
    monkeypatch.setattr(verify, 'run', lambda argv, env=None: calls.append((argv, env)))
    monkeypatch.delenv('MARIAMEM_NATIVE_DIR', raising=False)
    if native:
        monkeypatch.setenv('MARIAMEM_NATIVE_DIR', str(native))
    verify.integration()
    return calls


def test_default_acceptance_preserves_focused_runtime_race_gate(monkeypatch):
    calls = commands(monkeypatch)
    focused = calls[0][0]
    assert '-race' in focused
    assert './internal/generatedgo/code/base' in focused
    assert './internal/generatedgo' in focused
    for package in ('./tests/gointegration', './tests/godefault', './tests/generatedmemory'):
        argv, env = next(c for c in calls if package in c[0])
        assert '-race' not in argv
        assert env['MARIAMEM_TEST_DEFAULT'] == '1'
    assert any('tests/test_python_multiclient.py' in c[0] for c in calls)
    assert any('tests/test_python_timeout.py::test_normal_close_is_idempotent' in c[0] for c in calls)


def test_retired_overrides_do_not_change_integration_gate(monkeypatch, tmp_path):
    calls = commands(monkeypatch, tmp_path)
    for package in ('./tests/gointegration', './tests/godefault', './tests/generatedmemory'):
        argv, env = next(c for c in calls if package in c[0])
        assert '-race' not in argv
        assert env['MARIAMEM_TEST_DEFAULT'] == '1'
        assert 'MARIAMEM_NATIVE_DIR' not in env
