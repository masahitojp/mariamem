"""Real subprocess controls for the bounded public preparation descriptor."""
from dataclasses import FrozenInstanceError
import json
import os
from pathlib import Path
import signal
import subprocess
import sys

import pytest

from mariamem import PrepareCommand
from mariamem import _prepare as runner


class DB:
    def connection_info(self):
        return dict(host='127.0.0.1', port=12345, user='root', password='private-target', database='app')


def execute(tmp_path, code, **options):
    return runner._run_command(PrepareCommand([sys.executable, '-c', code], **options), DB(), tmp_path)


@pytest.mark.parametrize('argv', ['echo hi', b'echo', [], [''], [1], ['echo', '\0']])
def test_invalid_argv_rejected(argv):
    with pytest.raises((ValueError, TypeError)):
        PrepareCommand(argv)


@pytest.mark.parametrize('value', [True, False, 0, -1, float('nan'), float('inf'), '1'])
def test_timeout_is_finite_positive_not_boolean(value):
    with pytest.raises((ValueError, TypeError)):
        PrepareCommand(['echo'], timeout=value)


@pytest.mark.parametrize('env', [[], {'': 'v'}, {'a=b': 'v'}, {'a': 1}, {'a': '\0'}, {1: 'v'},
                                {runner._CONNECTION_ENV: 'wrong'}])
def test_invalid_env_never_launches(env):
    with pytest.raises((ValueError, TypeError)):
        PrepareCommand(['echo'], env=env)


def test_descriptor_copy_and_parent_overlay_at_execution(tmp_path, monkeypatch):
    argv = [sys.executable, '-c', '''
import os,json,pathlib
pathlib.Path('info.json').write_text(json.dumps({'keep':os.environ['P1_KEEP'],
 'overlay':os.environ['P1_OVERLAY'], 'connection':json.loads(os.environ['MARIAMEM_PREPARE_CONNECTION_INFO']),
 'path':os.environ['PATH'], 'cwd':str(pathlib.Path.cwd())}))
''']
    env = {'P1_OVERLAY': 'declared'}
    command = PrepareCommand(argv, env=env)
    argv[0] = 'must-not-execute'
    env['P1_OVERLAY'] = 'mutated'
    monkeypatch.setenv('P1_KEEP', 'parent-at-execution')
    monkeypatch.setenv('P1_OVERLAY', 'parent-loses')
    monkeypatch.setenv(runner._CONNECTION_ENV, 'inherited-wrong')
    result = runner._run_command(command, DB(), tmp_path)
    info = json.loads((tmp_path/'info.json').read_text())
    assert info['keep'] == 'parent-at-execution' and info['overlay'] == 'declared'
    assert info['connection'] == DB().connection_info()
    assert info['path'] == os.environ['PATH'] and info['cwd'] == str(tmp_path)
    assert os.environ[runner._CONNECTION_ENV] == 'inherited-wrong'
    assert result.process_cleanup == 'completed'
    with pytest.raises(FrozenInstanceError):
        command.timeout = 1
    with pytest.raises(TypeError):
        command.env['new'] = 'value'
    assert 'declared' not in repr(command) and 'info.json' not in repr(command)


def test_cwd_relative_to_root_and_no_shell_expansion(tmp_path, monkeypatch):
    (tmp_path/'sub').mkdir()
    monkeypatch.setenv('P1_LITERAL', 'must-not-expand')
    command = PrepareCommand([sys.executable, '-c', 'import sys,pathlib;pathlib.Path("arg").write_text(sys.argv[1])',
                              '$P1_LITERAL; echo nope'], cwd='sub')
    before = Path.cwd()
    runner._run_command(command, DB(), tmp_path)
    assert (tmp_path/'sub/arg').read_text() == '$P1_LITERAL; echo nope'
    assert Path.cwd() == before


@pytest.mark.parametrize('exit_code', [0, 23])
def test_output_is_continuously_drained_and_bounded(tmp_path, exit_code):
    code = f'import sys;sys.stdout.buffer.write(b"o"*4194304+b"OUT_END");sys.stderr.buffer.write(b"e"*4194304+b"ERR_END");sys.exit({exit_code})'
    if exit_code:
        with pytest.raises(subprocess.CalledProcessError) as caught:
            execute(tmp_path, code)
        value = caught.value
        assert value.returncode == 23
        assert '4194304' not in str(value)  # No raw argv disclosure.
    else:
        value = execute(tmp_path, code)
    assert value.stdout == value.output if exit_code else value.stdout.endswith(b'OUT_END')
    for name, marker in [('stdout', b'OUT_END'), ('stderr', b'ERR_END')]:
        assert len(getattr(value, name)) == 16384
        assert getattr(value, name).endswith(marker)
        assert getattr(value, name+'_truncated')
        assert getattr(value, name+'_dropped_bytes') == 4194304 + len(marker) - 16384
    if exit_code:
        assert any('application output; truncated;' in note for note in value.__notes__)


def test_missing_executable_keeps_original_os_error(tmp_path):
    with pytest.raises(FileNotFoundError) as caught:
        runner._run_command(PrepareCommand([str(tmp_path/'missing')]), DB(), tmp_path)
    assert caught.value.process_cleanup == 'not started'
    assert caught.value.stdout == caught.value.stderr == b''


def test_timeout_reaps_group_and_retains_bounded_partial_output(tmp_path):
    code = '''
import sys,subprocess,signal,pathlib,time,os
child = subprocess.Popen([sys.executable, '-c', 'import time;time.sleep(60)'])
def stop(*args):
    child.wait(timeout=1)
    sys.exit(0)
signal.signal(signal.SIGTERM, stop)
pathlib.Path('pids').write_text(str(os.getpid())+' '+str(child.pid))
sys.stderr.write('e'*1048576+'partial-before-timeout');sys.stderr.flush()
while True: time.sleep(.05)
'''
    with pytest.raises(subprocess.TimeoutExpired) as caught:
        execute(tmp_path, code, timeout=1)
    assert len(caught.value.stderr) == 16384 and caught.value.stderr.endswith(b'partial-before-timeout')
    assert caught.value.stderr_truncated and caught.value.stderr_dropped_bytes > 0
    assert caught.value.process_cleanup == 'completed'
    for pid in (tmp_path/'pids').read_text().split():
        with pytest.raises(ProcessLookupError):
            os.kill(int(pid), 0)


def test_interrupt_keeps_identity_and_reaps_process(tmp_path, monkeypatch):
    original = runner._read_ready
    interrupt = KeyboardInterrupt()
    fired = False
    def read(*args):
        nonlocal fired
        original(*args)
        if not fired and (tmp_path/'pid').exists():
            fired = True
            raise interrupt
    monkeypatch.setattr(runner, '_read_ready', read)
    with pytest.raises(KeyboardInterrupt) as caught:
        execute(tmp_path, 'import os,pathlib,time;pathlib.Path("pid").write_text(str(os.getpid()));time.sleep(60)')
    assert caught.value is interrupt and caught.value.process_cleanup == 'completed'
    with pytest.raises(ProcessLookupError):
        os.kill(int((tmp_path/'pid').read_text()), 0)


def test_cleanup_error_does_not_replace_primary(tmp_path, monkeypatch):
    primary = KeyboardInterrupt()
    cleanup = OSError('controlled process cleanup failure')
    fired = False
    read = runner._read_ready
    retire = runner._retire
    def fail_read(*args):
        nonlocal fired
        if not fired:
            fired = True
            raise primary
        return read(*args)
    def fail_retire(*args):
        retire(*args)  # Real child is retired; simulate failure to confirm status.
        raise cleanup
    monkeypatch.setattr(runner, '_read_ready', fail_read)
    monkeypatch.setattr(runner, '_retire', fail_retire)
    with pytest.raises(KeyboardInterrupt) as caught:
        execute(tmp_path, 'import time;time.sleep(60)')
    assert caught.value is primary and cleanup in primary.cleanup_errors
    assert primary.process_cleanup == 'unconfirmed'


def test_ignored_term_escalates_to_kill_without_losing_timeout(tmp_path):
    with pytest.raises(subprocess.TimeoutExpired) as caught:
        execute(tmp_path, 'import signal,os,pathlib,time;signal.signal(signal.SIGTERM,signal.SIG_IGN);pathlib.Path("pid").write_text(str(os.getpid()));time.sleep(60)', timeout=1)
    assert caught.value.process_cleanup == 'completed'
    with pytest.raises(ProcessLookupError):
        os.kill(int((tmp_path/'pid').read_text()), 0)


def test_transient_group_query_denial_never_becomes_false_absence(tmp_path, monkeypatch):
    original = runner._group_exists
    calls = 0
    def transient(pid):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise PermissionError('controlled transient group query denial')
        return original(pid)
    monkeypatch.setattr(runner, '_group_exists', transient)
    value = execute(tmp_path, 'pass')
    assert calls >= 2 and value.process_cleanup == 'completed'


def test_persistent_group_query_denial_stays_unconfirmed_and_keeps_errno(tmp_path, monkeypatch):
    primary = KeyboardInterrupt()
    denied = PermissionError(1, 'controlled persistent group query denial')
    original = runner._read_ready
    fired = False
    def read(*args):
        nonlocal fired
        if not fired:
            fired = True
            raise primary
        return original(*args)
    def query(pid):
        raise denied
    monkeypatch.setattr(runner, '_read_ready', read)
    monkeypatch.setattr(runner, '_group_exists', query)
    with pytest.raises(KeyboardInterrupt) as caught:
        execute(tmp_path, 'import time;time.sleep(60)')
    assert caught.value is primary and primary.process_cleanup == 'unconfirmed'
    assert denied in primary.cleanup_errors and denied.errno == 1
