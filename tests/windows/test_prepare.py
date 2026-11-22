"""Native Job Object ownership: normal, failed, timed out and orphaned commands."""
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import re
import subprocess
import sys

import pytest

pytestmark = pytest.mark.skipif(os.name != 'nt', reason='native Windows Job Object contract')


class DB:
    def connection_info(self):
        return {'host': '127.0.0.1', 'port': 12345, 'user': 'root', 'password': 'private'}


def execute(tmp_path, code, **kwargs):
    from mariamem import PrepareCommand
    from mariamem._prepare import _run_command
    return _run_command(PrepareCommand([sys.executable, '-c', code], **kwargs), DB(), tmp_path)


def alive(pid):
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.OpenProcess(0x100000, False, pid)
    if not handle:
        if ctypes.get_last_error() == 87:  # ERROR_INVALID_PARAMETER: no such PID.
            return False
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return kernel.WaitForSingleObject(handle, 0) == 258
    finally:
        assert kernel.CloseHandle(handle)


def test_windows_job_abi_and_success(tmp_path):
    from mariamem import _windows_prepare as runner
    assert ctypes.sizeof(runner._BasicLimit) == 64
    assert ctypes.sizeof(runner._ExtendedLimit) == 144
    assert ctypes.sizeof(runner._Accounting) == 48
    result = execute(tmp_path, "import json,os; print(json.dumps({'cwd':os.getcwd(),'target':json.loads(os.environ['MARIAMEM_PREPARE_CONNECTION_INFO'])}))")
    value = json.loads(result.stdout)
    assert Path(value['cwd']) == tmp_path
    assert value['target'] == DB().connection_info()
    assert result.process_cleanup == 'completed'


@pytest.mark.parametrize('code', [0, 7])
def test_windows_job_drains_bounded_output(tmp_path, code):
    program = f"import sys; sys.stdout.buffer.write(b'o'*100000); sys.stderr.buffer.write(b'e'*100000); sys.exit({code})"
    if code:
        with pytest.raises(subprocess.CalledProcessError) as raised:
            execute(tmp_path, program)
        result = raised.value
        assert result.returncode == code
    else:
        result = execute(tmp_path, program)
    assert result.stdout == b'o' * 16384 and result.stderr == b'e' * 16384
    assert result.stdout_truncated and result.stderr_truncated
    assert result.process_cleanup == 'completed'


@pytest.mark.parametrize('timeout', [False, True])
def test_windows_job_reaps_descendants(tmp_path, timeout):
    program = ("import subprocess,sys,time; p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(60)']); "
               "print('CHILD='+str(p.pid),flush=True); " + ('time.sleep(60)' if timeout else 'time.sleep(.1)'))
    expected = subprocess.TimeoutExpired if timeout else RuntimeError
    with pytest.raises(expected) as raised:
        execute(tmp_path, program, timeout=2)
    error = raised.value
    assert error.process_cleanup == 'completed'
    pid = int(re.search(rb'CHILD=(\d+)', error.stdout).group(1))
    assert not alive(pid)


def test_windows_missing_command_preserves_os_error(tmp_path):
    from mariamem import PrepareCommand
    from mariamem._prepare import _run_command
    with pytest.raises(FileNotFoundError) as raised:
        _run_command(PrepareCommand([str(tmp_path / 'missing.exe')]), DB(), tmp_path)
    assert raised.value.process_cleanup == 'not started'


def test_windows_command_never_runs_before_assignment(tmp_path, monkeypatch):
    from mariamem import _windows_prepare as runner
    def reject(self, pid):
        raise PermissionError('injected assignment failure')
    monkeypatch.setattr(runner._Job, 'assign', reject)
    marker = tmp_path / 'unexpected'
    with pytest.raises(PermissionError) as raised:
        execute(tmp_path, f"from pathlib import Path; Path({str(marker)!r}).write_text('ran')")
    assert raised.value.process_cleanup == 'not started'
    assert not marker.exists()


def test_windows_query_denial_never_claims_cleanup(tmp_path, monkeypatch):
    from mariamem import _windows_prepare as runner
    def denied(self):
        raise PermissionError('injected query failure')
    monkeypatch.setattr(runner._Job, 'active', denied)
    with pytest.raises(PermissionError) as raised:
        execute(tmp_path, "print('done')")
    assert raised.value.process_cleanup == 'unconfirmed'
    assert raised.value.cleanup_errors


def test_windows_env_overlay_is_case_insensitive(tmp_path, monkeypatch):
    monkeypatch.setenv('P1_MIXED_CASE', 'parent')
    result = execute(tmp_path, "import os; print(os.environ['P1_MIXED_CASE'])", env={'p1_mixed_case': 'overlay'})
    assert result.stdout.strip() == b'overlay'
    from mariamem import PrepareCommand
    with pytest.raises(ValueError, match='reserved'):
        PrepareCommand([sys.executable], env={'mariamem_prepare_connection_info': 'wrong'})


def test_windows_cleanup_interrupt_preserves_primary(tmp_path, monkeypatch):
    from mariamem import _windows_prepare as runner
    original = runner._Job.close
    interrupt = KeyboardInterrupt('injected finalization interrupt')
    def interrupted(self):
        original(self)
        raise interrupt
    monkeypatch.setattr(runner._Job, 'close', interrupted)
    with pytest.raises(KeyboardInterrupt) as raised:
        execute(tmp_path, 'import sys; sys.exit(7)')
    assert raised.value is interrupt
    assert isinstance(interrupt.__cause__, subprocess.CalledProcessError)
    assert interrupt.process_cleanup == interrupt.__cause__.process_cleanup == 'unconfirmed'
