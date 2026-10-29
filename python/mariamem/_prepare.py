"""Bounded execution for declarative preparation; no framework routing."""
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import json
import math
import os
from pathlib import Path
import selectors
import signal
import subprocess
import time
from types import MappingProxyType

_CONNECTION_ENV = 'MARIAMEM_PREPARE_CONNECTION_INFO'
_OUTPUT_LIMIT = 16 * 1024


@dataclass(frozen=True, init=False)
class PrepareCommand:
    """Declare one preparation executable; env overlays the parent at execution.

    argv is copied; no shell interpolation. cwd defaults to pytest's rootpath.
    Output retains only the last 16 KiB per stream, with explicit truncation.
    """
    argv: tuple
    timeout: float
    cwd: object
    env: object

    def __init__(self, argv, *, timeout=120, cwd=None, env=None):
        if isinstance(argv, (str, bytes)) or not isinstance(argv, Sequence):
            raise TypeError('PrepareCommand argv must be a sequence of strings')
        argv = tuple(argv)
        if not argv or any(not isinstance(v, str) or '\0' in v for v in argv) or not argv[0]:
            raise ValueError('PrepareCommand requires a nonempty executable and NUL-free string arguments')
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
            raise ValueError('PrepareCommand timeout must be positive and finite')
        if cwd is not None:
            cwd = Path(cwd)
            if '\0' in str(cwd):
                raise ValueError('PrepareCommand cwd must not contain NUL')
        if env is None:
            env = {}
        if not isinstance(env, Mapping):
            raise TypeError('PrepareCommand env must be a mapping of strings')
        env = dict(env)
        if any(not isinstance(k, str) or not k or '=' in k or '\0' in k
               or not isinstance(v, str) or '\0' in v for k, v in env.items()):
            raise ValueError('PrepareCommand env requires NUL-free string keys and values')
        if _CONNECTION_ENV in env:
            raise ValueError('PrepareCommand env must not override its reserved connection variable')
        object.__setattr__(self, 'argv', argv)
        object.__setattr__(self, 'timeout', float(timeout))
        object.__setattr__(self, 'cwd', cwd)
        object.__setattr__(self, 'env', MappingProxyType(env))

    def __repr__(self):
        # Neither pytest locals nor accidental repr should expose argv/env secrets.
        return f'PrepareCommand(argc={len(self.argv)}, timeout={self.timeout}, env_keys={len(self.env)})'


class _CommandFailure(subprocess.CalledProcessError):
    def __str__(self):
        return f'preparation command exited {self.returncode}; bounded stdout/stderr retained'


class _CommandTimeout(subprocess.TimeoutExpired):
    def __str__(self):
        return f'preparation command exceeded {self.timeout}s; bounded stdout/stderr retained'


class _Tail:
    def __init__(self):
        self.data = b''
        self.dropped = 0

    def add(self, block):
        data = self.data + block
        self.dropped += max(0, len(data) - _OUTPUT_LIMIT)
        self.data = data[-_OUTPUT_LIMIT:]


def _add_note(primary, text):
    # Diagnostic enrichment must not replace a user's read-only exception.
    try:
        BaseException.add_note(primary, text)
    except Exception:
        return False
    return True


def _attach_cleanup(primary, error):
    try:
        previous = getattr(primary, 'cleanup_errors', ())
        if not isinstance(previous, tuple):
            return False
        if not any(item is error for item in previous):
            primary.cleanup_errors = previous + (error,)
    except Exception:
        return False
    _add_note(primary, 'mariamem cleanup also failed: ' + type(error).__name__)
    return True


def _group_exists(pid):
    try:
        os.killpg(pid, 0)
        return True
    except ProcessLookupError:
        return False


def _signal_group(pid, sig):
    try:
        os.killpg(pid, sig)
    except ProcessLookupError:
        pass


def _read_ready(selector, tails, wait):
    for key, _ in selector.select(wait):
        try:
            block = os.read(key.fd, 4096)
        except BlockingIOError:
            continue
        if block:
            tails[key.data].add(block)
        else:
            selector.unregister(key.fileobj)
            key.fileobj.close()


def _retire(process, selector, tails):
    """Bounded group termination; never call process exit alone group cleanup."""
    last_permission = None
    for sig in (signal.SIGTERM, signal.SIGKILL):
        try:
            _signal_group(process.pid, sig)
        except PermissionError as error:
            last_permission = error
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            process.poll()  # Reap the leader before deciding group liveness.
            try:
                exists = _group_exists(process.pid)
            except PermissionError as error:
                # A dying group may be temporarily unqueryable on Darwin.
                # Unknown is never absence: keep reaping/querying within budget.
                last_permission = error
                exists = True
            if not exists and not selector.get_map():
                return
            _read_ready(selector, tails, 0.02)
    process.poll()
    if last_permission is not None:
        raise last_permission
    raise RuntimeError('preparation command process-group cleanup unconfirmed')


def _outputs(value, tails, cleanup):
    value.stdout = tails['stdout'].data
    value.stderr = tails['stderr'].data
    if isinstance(value, (subprocess.CalledProcessError, subprocess.TimeoutExpired)):
        value.output = value.stdout
    for name, tail in tails.items():
        setattr(value, name + '_truncated', tail.dropped > 0)
        setattr(value, name + '_dropped_bytes', tail.dropped)
    value.process_cleanup = cleanup
    return value


def _run_command(command, database, rootpath):
    env = os.environ.copy()
    env.update(command.env)
    env[_CONNECTION_ENV] = json.dumps(database.connection_info())
    cwd = Path(rootpath) if command.cwd is None else Path(rootpath) / command.cwd
    selector = selectors.DefaultSelector()
    tails = {'stdout': _Tail(), 'stderr': _Tail()}
    process = None
    primary = None
    cleanup = 'unconfirmed'
    try:
        process = subprocess.Popen(command.argv, cwd=cwd, env=env, shell=False,
                                   start_new_session=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        for name in tails:
            stream = getattr(process, name)
            os.set_blocking(stream.fileno(), False)
            selector.register(stream, selectors.EVENT_READ, name)
        deadline = time.monotonic() + command.timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise _CommandTimeout(command.argv, command.timeout)
            _read_ready(selector, tails, min(remaining, 0.02))
            code = process.poll()
            if code is not None:
                if code:
                    raise _CommandFailure(code, command.argv)
                # A completed leader must not leave background group members.
                try:
                    exists = _group_exists(process.pid)
                except PermissionError:
                    continue  # Await an actual absence result, bounded by deadline.
                if exists:
                    raise RuntimeError('preparation command left background processes')
                if not selector.get_map():
                    break
        cleanup = 'completed'
        return _outputs(subprocess.CompletedProcess(command.argv, code), tails, cleanup)
    except BaseException as error:
        primary = error
        if process is not None:
            try:
                _retire(process, selector, tails)
                cleanup = 'completed'
            except BaseException as close_error:
                if isinstance(error, Exception) and not isinstance(close_error, Exception):
                    _outputs(error, tails, 'unconfirmed')
                    _outputs(close_error, tails, 'unconfirmed')
                    primary = close_error
                    raise close_error from error
                _attach_cleanup(error, close_error)
        else:
            cleanup = 'not started'
        _outputs(error, tails, cleanup)
        for name in tails:
            tail = tails[name]
            if tail.data:
                status = f'truncated; {tail.dropped} earlier bytes dropped' if tail.dropped else 'not truncated'
                # Preview is smaller than the retained tail; original bounded bytes remain inspectable.
                preview = tail.data[-2048:].decode('utf-8', errors='replace')
                _add_note(error, f'mariamem {name} (application output; {status}; last 2048 bytes shown):\n{preview}')
        raise
    finally:
        close_errors = []
        for key in list(selector.get_map().values()):
            try:
                selector.unregister(key.fileobj)
            except BaseException as error:
                close_errors.append(error)
        if process is not None:
            for stream in (process.stdout, process.stderr):
                if stream is not None and not stream.closed:
                    try:
                        stream.close()
                    except BaseException as error:
                        close_errors.append(error)
        try:
            selector.close()
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
                # Interrupt/SystemExit must stay that original BaseException,
                # including when they arrive only in the finalizer.
                error = next((e for e in close_errors if not isinstance(e, Exception)), None)
                if error is None and len(close_errors) == 1:
                    error = close_errors[0]
                if error is None:
                    error = ExceptionGroup('preparation output cleanup failed', close_errors)
                else:
                    for other in close_errors:
                        if other is not error:
                            _attach_cleanup(error, other)
                _outputs(error, tails, 'unconfirmed')
                raise error
