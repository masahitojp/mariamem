"""Finite settings on supplied entries, including actual pytest reports."""
from pathlib import Path

import pytest

from test_owned_snapshot_unit import fake_host  # noqa: F401
from test_routing_pytest import run, fake_suite


@pytest.mark.parametrize("fixture,value", [
    ("mariamem_max_forks", "0"), ("mariamem_max_forks", "2**100"),
    ("mariamem_fork_timeout", "None"), ("mariamem_fork_timeout", "True"),
    ("mariamem_fork_timeout", "float('nan')"), ("mariamem_fork_timeout", "0"),
])
def test_invalid_fixture_setting_rejects_before_preparation(tmp_path, fixture, value):
    conf = f'''
@pytest.fixture(scope='session')
def {fixture}(): return {value}
@pytest.fixture(scope='session')
def mariamem_prepare():
    return lambda db: record('MUST_NOT_PREPARE')
'''
    result, events = fake_suite(tmp_path, conf, 'def test_body(mariamem_fork): pass', False)
    assert result.returncode == 1
    assert 'MUST_NOT_PREPARE' not in events
    assert 'snapshot' not in events and 'fork' not in events


def test_fixture_settings_reach_snapshot_and_every_fork(tmp_path):
    result, events = fake_suite(tmp_path, '''
_capture, _fork = DB.snapshot, Baseline.fork
def capture(self, **options):
    assert options == {'max_forks': 1}
    return _capture(self, **options)
def fork(self, **options):
    assert options == {'timeout': .5}
    return _fork(self, **options)
DB.snapshot, Baseline.fork = capture, fork
@pytest.fixture(scope='session')
def mariamem_max_forks(): return 1
@pytest.fixture(scope='session')
def mariamem_fork_timeout(): return .5
''', 'def test_first(mariamem_fork): pass\ndef test_second(mariamem_fork): pass', False)
    assert result.returncode == 0, result.stdout + result.stderr
    assert events.count('snapshot') == 1 and events.count('fork') == 2


def test_held_child_fails_with_finite_deadline_and_stops_next_admission(tmp_path, fake_host):
    (tmp_path/'conftest.py').write_text(f'''
import pytest
from pathlib import Path
@pytest.fixture(scope='session')
def mariamem_options(): return {{'host_binary': {str(fake_host)!r}}}
@pytest.fixture(scope='session')
def mariamem_max_forks(): return 1
@pytest.fixture(scope='session')
def mariamem_fork_timeout(): return .05
@pytest.fixture(scope='session')
def mariamem_snapshot(mariamem_snapshot):
    assert mariamem_snapshot.max_forks == 1
    held = mariamem_snapshot.fork(timeout=1)
    try:
        yield mariamem_snapshot
    finally:
        assert held.status()['state'] == 'ready'
        Path('held-child-still-ready').touch()
        held.close()
''')
    (tmp_path/'test_wait.py').write_text('''
from pathlib import Path
def test_first(mariamem_fork): Path('BAD_BODY').touch()
def test_second(mariamem_fork): Path('BAD_BODY').touch()
''')
    result = run(tmp_path)
    assert result.returncode == 1, result.stdout + result.stderr
    assert 'Fork capacity wait timed out' in result.stdout
    assert 'dependent admission stopped for this worker' in result.stdout
    assert 'mariamem acquire:' in result.stdout
    assert not (tmp_path/'BAD_BODY').exists()
    assert (tmp_path/'held-child-still-ready').exists()
