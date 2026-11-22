"""Windows preparation commands owned by one kill-on-close Job Object."""
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import tempfile
import time

from ._prepare import (_Tail, _outputs, _attach_cleanup, _add_note,
                       _CommandFailure, _CommandTimeout, _CONNECTION_ENV)

_kernel = ctypes.WinDLL('kernel32', use_last_error=True)


def _api(name, args, result=wintypes.BOOL):
    value = getattr(_kernel, name)
    value.argtypes = args
    value.restype = result
    return value


_create = _api('CreateJobObjectW', [ctypes.c_void_p, wintypes.LPCWSTR], wintypes.HANDLE)
_set = _api('SetInformationJobObject', [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD])
_query = _api('QueryInformationJobObject', [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD, ctypes.c_void_p])
_assign = _api('AssignProcessToJobObject', [wintypes.HANDLE, wintypes.HANDLE])
_terminate = _api('TerminateJobObject', [wintypes.HANDLE, wintypes.UINT])
_close = _api('CloseHandle', [wintypes.HANDLE])
_open_process = _api('OpenProcess', [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD], wintypes.HANDLE)


class _BasicLimit(ctypes.Structure):
    _fields_ = [('process_time', ctypes.c_int64), ('job_time', ctypes.c_int64),
                ('flags', wintypes.DWORD), ('minimum_working_set', ctypes.c_size_t),
                ('maximum_working_set', ctypes.c_size_t), ('active_process_limit', wintypes.DWORD),
                ('affinity', ctypes.c_size_t), ('priority', wintypes.DWORD), ('scheduling', wintypes.DWORD)]


class _ExtendedLimit(ctypes.Structure):
    _fields_ = [('basic', _BasicLimit), ('io', ctypes.c_uint64 * 6),
                ('process_memory', ctypes.c_size_t), ('job_memory', ctypes.c_size_t),
                ('peak_process_memory', ctypes.c_size_t), ('peak_job_memory', ctypes.c_size_t)]


class _Accounting(ctypes.Structure):
    _fields_ = [('times', ctypes.c_int64 * 4), ('page_faults', wintypes.DWORD),
                ('total', wintypes.DWORD), ('active', wintypes.DWORD), ('terminated', wintypes.DWORD)]


def _checked(ok):
    if not ok:
        raise ctypes.WinError(ctypes.get_last_error())


class _Job:
    def __init__(self):
        self.handle = _create(None, None)
        _checked(self.handle)
        limits = _ExtendedLimit()
        limits.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE; no breakaway.
        try:
            _checked(_set(self.handle, 9, ctypes.byref(limits), ctypes.sizeof(limits)))
        except BaseException:
            _close(self.handle)
            self.handle = None
            raise

    def assign(self, pid):
        # Only the library launcher exists yet. No user executable is allowed
        # to run until assignment succeeds, so there is no descendant race.
        process = _open_process(0x0100 | 0x0001, False, pid)  # SET_QUOTA | TERMINATE
        _checked(process)
        try:
            _checked(_assign(self.handle, process))
        finally:
            _checked(_close(process))

    def active(self):
        state = _Accounting()
        _checked(_query(self.handle, 1, ctypes.byref(state), ctypes.sizeof(state), None))
        return state.active

    def terminate(self):
        _checked(_terminate(self.handle, 1))

    def close(self):
        if self.handle is not None:
            _checked(_close(self.handle))
            self.handle = None


# This controlled launcher waits for the parent's gate before creating a user
# process. Parent death before assignment closes stdin; afterwards closing the
# parent's sole Job Object handle retires the whole command tree.
_LAUNCHER = '''import json, subprocess, sys
line = sys.stdin.buffer.readline()
if not line:
    sys.exit(1)
request = json.loads(line)
try:
    process = subprocess.Popen(request['argv'], stdin=subprocess.DEVNULL)
except OSError as error:
    with open(request['status'], 'w', encoding='utf-8') as stream:
        json.dump({'errno': error.errno, 'winerror': getattr(error, 'winerror', None),
                   'strerror': error.strerror, 'filename': error.filename}, stream)
    sys.exit(1)
sys.exit(process.wait())
'''


def _drain(stream, tail, failures):
    try:
        while True:
            block = stream.read(4096)
            if not block:
                return
            tail.add(block)
    except BaseException as error:
        failures.append(error)


def _retire(job, process, assigned, readers):
    if assigned:
        job.terminate()
    elif process.poll() is None:
        process.kill()  # Gate never opened; the unassigned launcher has no children.
    process.wait(timeout=2)
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        if job.active() == 0 and not any(reader.is_alive() for reader in readers):
            return
        time.sleep(.01)
    raise RuntimeError('preparation command Job Object cleanup unconfirmed')


def run_command(command, database, rootpath):
    env = {key.upper(): value for key, value in os.environ.items()}
    env.update({key.upper(): value for key, value in command.env.items()})
    env[_CONNECTION_ENV] = json.dumps(database.connection_info())
    cwd = Path(rootpath) if command.cwd is None else Path(rootpath) / command.cwd
    tails = {'stdout': _Tail(), 'stderr': _Tail()}
    process = job = primary = None
    readers, failures = [], []
    assigned = False
    gate_opened = launch_error = False
    cleanup = 'unconfirmed'
    control = None
    try:
        control = tempfile.TemporaryDirectory(prefix='mariamem-prepare-control-')
        status = Path(control.name) / 'launch.json'
        job = _Job()
        process = subprocess.Popen([sys.executable, '-c', _LAUNCHER], cwd=cwd, env=env,
                                   stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, bufsize=0)
        job.assign(process.pid)
        assigned = True
        for name in tails:
            reader = threading.Thread(target=_drain, args=(getattr(process, name), tails[name], failures), daemon=True)
            readers.append(reader)
            reader.start()
        data = memoryview((json.dumps({'argv': command.argv, 'status': str(status)}) + '\n').encode('utf-8'))
        gate_opened = True
        while data:
            count = process.stdin.write(data)
            if not count:
                raise BrokenPipeError('preparation launch gate closed')
            data = data[count:]
        process.stdin.close()
        deadline = time.monotonic() + command.timeout
        while True:
            if time.monotonic() >= deadline:
                raise _CommandTimeout(command.argv, command.timeout)
            code = process.poll()
            if code is not None:
                if code:
                    if status.exists():
                        if status.stat().st_size > 65536:
                            raise RuntimeError('invalid preparation launch error')
                        launch = json.loads(status.read_text(encoding='utf-8'))
                        launch_error = True
                        error = OSError(launch['errno'], launch['strerror'], launch['filename'], launch['winerror'])
                        raise error
                    raise _CommandFailure(code, command.argv)
                if job.active():
                    raise RuntimeError('preparation command left background processes')
                if not any(reader.is_alive() for reader in readers):
                    if failures:
                        raise failures[0]
                    break
            time.sleep(.01)
        cleanup = 'completed'
        return _outputs(subprocess.CompletedProcess(command.argv, code), tails, cleanup)
    except BaseException as error:
        primary = error
        if process is not None:
            try:
                _retire(job, process, assigned, readers)
                cleanup = 'not started' if launch_error or not gate_opened else 'completed'
            except BaseException as close_error:
                if isinstance(error, Exception) and not isinstance(close_error, Exception):
                    primary = close_error
                    _outputs(error, tails, 'unconfirmed')
                    _outputs(close_error, tails, 'unconfirmed')
                    raise close_error from error
                _attach_cleanup(error, close_error)
        else:
            cleanup = 'not started'
        _outputs(error, tails, cleanup)
        for name, tail in tails.items():
            if tail.data:
                preview = tail.data[-2048:].decode('utf-8', errors='replace')
                status = f'truncated; {tail.dropped} earlier bytes dropped' if tail.dropped else 'not truncated'
                _add_note(error, f'mariamem {name} (application output; {status}; last 2048 bytes shown):\n{preview}')
        raise
    finally:
        close_errors = []
        if job is not None:
            try:
                job.close()
            except BaseException as error:
                close_errors.append(error)
        if process is not None:
            # Closing a buffered stream under a live reader can itself block.
            # Failed retirement stays explicitly unconfirmed; never hide it as
            # a successful close merely because the command leader has exited.
            for reader in readers:
                reader.join(timeout=2)
            if any(reader.is_alive() for reader in readers):
                close_errors.append(RuntimeError('preparation output reader cleanup unconfirmed'))
            else:
                for stream in (process.stdin, process.stdout, process.stderr):
                    if stream is not None and not stream.closed:
                        try:
                            stream.close()
                        except BaseException as error:
                            close_errors.append(error)
        if control is not None:
            try:
                control.cleanup()
            except BaseException as error:
                close_errors.append(error)
        if close_errors:
            if primary is not None:
                control = next((e for e in close_errors if not isinstance(e, Exception)), None)
                if isinstance(primary, Exception) and control is not None:
                    for error in close_errors:
                        if error is not control:
                            _attach_cleanup(control, error)
                    _outputs(primary, tails, 'unconfirmed')
                    _outputs(control, tails, 'unconfirmed')
                    raise control from primary
                for error in close_errors:
                    _attach_cleanup(primary, error)
                primary.process_cleanup = 'unconfirmed'
            else:
                error = next((e for e in close_errors if not isinstance(e, Exception)), None)
                if error is None and len(close_errors) == 1:
                    error = close_errors[0]
                if error is None:
                    error = ExceptionGroup('preparation cleanup failed', close_errors)
                else:
                    for other in close_errors:
                        if other is not error:
                            _attach_cleanup(error, other)
                _outputs(error, tails, 'unconfirmed')
                raise error
