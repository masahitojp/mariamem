"""Opt-in observations/env for existing commands, never qualification or a cache manager."""
import errno
import fcntl
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
TRACE = 'MARIAMEM_PHASE_TRACE'
WORKSPACE = 'MARIAMEM_DEV_WORKSPACE'
_TOOLS = {}


def go_environment(env=None, *, root=ROOT):
    """Opt in to an existing active workspace; defaults and release env stay intact."""
    original = os.environ if env is None else env
    if not original.get(WORKSPACE):
        return env
    work = Path(original[WORKSPACE])
    if not work.is_absolute() or work.resolve() != work:
        raise ValueError('development workspace must be an absolute non-symlink path')
    receipt = json.loads((work/'experiment.json').read_text())
    if (receipt.get('owner') != 'mariamem-experiment-v1' or
            receipt.get('state') not in ('prepared', 'running') or
            Path(root).resolve() != work/'worktree'):
        raise ValueError('Go cache requires this checkout\'s active owned workspace')
    result = dict(original)
    for key, relative in [('GOCACHE', 'gocache'), ('GOPATH', 'gopath'),
                          ('GOMODCACHE', 'modcache')]:
        path = work/'temp'/relative
        if path.resolve() != path:
            raise ValueError('development cache path must not contain symlinks')
        if result.get(key) and Path(result[key]) != path:
            raise ValueError('conflicting '+key+'; unset it before selecting task workspace')
        result[key] = str(path)
    result.setdefault('GOTOOLCHAIN', 'go1.26.8')
    # A developer can intentionally select another toolchain/flags. Go keys its
    # own cache accordingly; record the actual compiler, not only this request.
    return result


class _UsagePopen(subprocess.Popen):
    """POSIX Popen wait protocol, with wait4 instead of waitpid.

    These two CPython hooks are intentionally confined here and covered by
    success/pipes/timeout/signal tests. No global patch, extra process, redirect,
    signal handler or process-group change. Unsupported platforms use run().
    """
    usage = None

    def _try_wait(self, wait_flags):
        try:
            pid, status, usage = os.wait4(self.pid, wait_flags)
        except ChildProcessError:
            return self.pid, 0  # Same Popen semantics; resources unavailable.
        except OSError as exc:
            if exc.errno in (errno.ENOSYS, errno.EPERM):
                return super()._try_wait(wait_flags)  # Counters denied, normal wait still works.
            raise
        if pid == self.pid:
            self.usage = usage
        return pid, status

    def _internal_poll(self, _deadstate=None):
        if self.returncode is None and self._waitpid_lock.acquire(False):
            try:
                if self.returncode is None:
                    pid, status = self._try_wait(os.WNOHANG)
                    if pid == self.pid:
                        self._handle_exitstatus(status)
            except OSError as exc:
                if _deadstate is not None:
                    self.returncode = _deadstate
                elif exc.errno == errno.ECHILD:
                    self.returncode = 0
            finally:
                self._waitpid_lock.release()
        return self.returncode


def _resources(usage):
    system = platform.system()
    if usage is None or system not in ('Darwin', 'Linux'):
        return {'status': 'Unavailable', 'reason': 'wait4 resources unavailable',
                'user_seconds': None, 'system_seconds': None, 'peak_rss_bytes': None}
    return {'status': 'Available', 'user_seconds': usage.ru_utime,
            'system_seconds': usage.ru_stime,
            'peak_rss_bytes': usage.ru_maxrss * (1 if system == 'Darwin' else 1024),
            'scope': 'wait4 child rusage; descendant attribution is OS-dependent; '
                     'RSS is a high-water mark, not summed simultaneous tree RSS'}


def _identities(paths):
    result = {}
    for value in paths:
        path = Path(value)
        try:
            h = hashlib.sha256()
            with path.open('rb') as stream:
                for block in iter(lambda: stream.read(1024*1024), b''):
                    h.update(block)
            result[str(path)] = {'sha256': h.hexdigest(), 'bytes': path.stat().st_size}
        except OSError as exc:
            result[str(path)] = {'status': 'Unavailable', 'reason': type(exc).__name__}
    return result


def _context(root, env, argv, tools, cwd):
    result = {'python': sys.version, 'system': platform.system(),
              'architecture': platform.machine(), 'tools': dict(tools or {}),
              'go_environment': {k: env.get(k) for k in
                  ('GOTOOLCHAIN', 'GOCACHE', 'GOMODCACHE', 'GOPATH', 'GOOS', 'GOARCH',
                   'CGO_ENABLED', 'GOFLAGS', 'GOEXPERIMENT', 'GOWORK', 'GOENV')}}
    try:
        result['source_commit'] = subprocess.check_output(
            ['git', 'rev-parse', 'HEAD'], cwd=root, text=True, stderr=subprocess.DEVNULL).strip()
        diff = subprocess.check_output(['git', 'diff', 'HEAD', '--binary'], cwd=root)
        result['tracked_diff_sha256'] = hashlib.sha256(diff).hexdigest()
        result['git_status'] = subprocess.check_output(
            ['git', 'status', '--porcelain'], cwd=root, text=True).splitlines()
    except (OSError, subprocess.CalledProcessError):
        result['source_status'] = 'Unavailable'
    if argv and Path(str(argv[0])).name == 'go':
        key = (str(argv[0]), str(cwd), tuple(result['go_environment'].items()), env.get('PATH'))
        if key not in _TOOLS:
            try:
                _TOOLS[key] = subprocess.check_output([str(argv[0]), 'version'], cwd=cwd,
                    env=env, text=True, stderr=subprocess.STDOUT, timeout=15).strip()
            except (OSError, subprocess.SubprocessError):
                _TOOLS[key] = 'Unavailable'
        result['tools']['go'] = _TOOLS[key]
    return result


def _append(path, record):
    try:
        path = Path(path)
        if not path.is_absolute():
            raise ValueError('phase trace must be an absolute path')
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('a') as stream:
            fcntl.flock(stream, fcntl.LOCK_EX)
            stream.write(json.dumps(record, sort_keys=True)+'\n')
    except (OSError, ValueError, TypeError) as exc:
        # Diagnostic write failure must not replace the command's result.
        print('phase observation unavailable: '+str(exc), file=sys.stderr)


def run(argv, *, phase=None, inputs=(), outputs=(), tools=None, root=ROOT,
        check=False, input=None, capture_output=False, timeout=None, **kwargs):
    """subprocess.run-compatible command boundary with optional JSONL diagnostics."""
    env = os.environ if kwargs.get('env') is None else kwargs['env']
    trace = env.get(TRACE)
    if not trace:
        return subprocess.run(argv, check=check, input=input, capture_output=capture_output,
                              timeout=timeout, **kwargs)
    observing = time.monotonic()
    record = {'version': 1, 'kind': 'diagnostic-not-qualification',
              'phase': phase or str(argv[0]), 'argv': [str(a) for a in argv],
              'cwd': str(kwargs.get('cwd', Path.cwd())), 'pid': os.getpid(),
              'started_at_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
              'context': _context(root, env, argv, tools, kwargs.get('cwd') or Path.cwd()),
              'inputs': _identities(inputs)}
    process = None
    start = time.monotonic()
    try:
        if not (sys.implementation.name == 'cpython' and hasattr(os, 'wait4') and
                hasattr(subprocess.Popen, '_try_wait') and
                platform.system() in ('Darwin', 'Linux')):
            result = subprocess.run(argv, check=check, input=input,
                                   capture_output=capture_output, timeout=timeout, **kwargs)
            record['returncode'] = result.returncode
            return result
        if input is not None:
            if kwargs.get('stdin') is not None:
                raise ValueError('stdin and input arguments may not both be used.')
            kwargs['stdin'] = subprocess.PIPE
        if capture_output:
            if kwargs.get('stdout') is not None or kwargs.get('stderr') is not None:
                raise ValueError('stdout and stderr arguments may not be used with capture_output.')
            kwargs.update(stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        with _UsagePopen(argv, **kwargs) as process:
            try:
                stdout, stderr = process.communicate(input, timeout=timeout)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()  # POSIX communicate already put partial output on the exception.
                raise
            except BaseException:
                process.kill()
                raise  # Popen.__exit__ retains standard wait/KeyboardInterrupt behavior.
            retcode = process.poll()
            record['returncode'] = retcode
            if check and retcode:
                raise subprocess.CalledProcessError(retcode, process.args,
                                                    output=stdout, stderr=stderr)
        return subprocess.CompletedProcess(process.args, retcode, stdout, stderr)
    except BaseException as exc:
        record['exception'] = type(exc).__name__
        if isinstance(exc, subprocess.CalledProcessError):
            record['returncode'] = exc.returncode
        raise
    finally:
        record['wall_seconds'] = time.monotonic()-start
        if process is not None:
            record['returncode'] = process.returncode
        record['resources'] = _resources(getattr(process, 'usage', None))
        record['outputs'] = (_identities(outputs) if record.get('returncode') == 0 and
                             'exception' not in record else {})
        record['observer_seconds_excluding_append'] = time.monotonic()-observing-record['wall_seconds']
        _append(trace, record)
