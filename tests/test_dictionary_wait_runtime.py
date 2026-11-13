"""The actual guest regression must reject either removed notification."""
from pathlib import Path
import sys
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import check_dictionary_wait_runtime as guard


def test_actual_guest_fixture_binding():
    guard.validate(ROOT)


@pytest.mark.parametrize('call', ['Fn16583(m)', 'Fn16584(m)', 'Fn17733(m)'])
def test_removed_guest_notification_or_lock_is_rejected(call):
    pins = guard.validate(ROOT)
    entry = pins['functions']['Fn17744']
    original = guard.body((ROOT/entry['file']).read_text(), 'Fn17744')
    assert original.count(call) == 1
    changed = original.replace(call, '/* removed */')
    with pytest.raises(ValueError, match='body changed'):
        guard.validate_body(changed, entry['normalized_sha256'])


def test_notification_order_and_real_guest_owner():
    pins = guard.validate(ROOT)
    entry = pins['functions']['Fn17744']
    original = guard.body((ROOT/entry['file']).read_text(), 'Fn17744')
    assert original.index('Fn16583(m)') < original.index('Fn17733(m)') < original.index('Fn16584(m)')
    test = (ROOT/'internal/generatedgo/dictionary_wait_integration_test.go').read_text()
    assert 'p6.Fn17744(c, 0)' in test
    assert 'Fn16583(' not in test and 'Fn16584(' not in test
    assert "'dictionary_wait_integration_test.go'" in (ROOT/'scripts/generate_runtime.py').read_text()
    assert 'tests/test_dictionary_wait_runtime.py' in (ROOT/'scripts/verify.py').read_text()


def test_normal_integration_selects_actual_dictionary_guest(monkeypatch):
    import re
    import verify
    commands = []
    monkeypatch.setattr(verify, 'run', lambda command, **kwargs: commands.append(command))
    verify.integration()
    selected = [command for command in commands
                if './internal/generatedgo' in command and '-tags=integration' in command]
    assert len(selected) == 1
    pattern = next(arg.removeprefix('-run=') for arg in selected[0] if arg.startswith('-run='))
    assert re.search(pattern, 'TestDictionaryWaitActualGuest')
    assert re.search(pattern, 'TestWorkerTrapActualGuest')
