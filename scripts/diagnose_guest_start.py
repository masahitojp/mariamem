#!/usr/bin/env python3
"""Capture the direct guest startup without the host's EOF-triggered SIGKILL."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import selectors
import shutil
import signal
import struct
import subprocess
import tempfile
import time


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for part in iter(lambda: f.read(1024 * 1024), b''):
            h.update(part)
    return h.hexdigest()


def ready_frame(data):
    if len(data) < 4:
        return None
    size = struct.unpack('<I', data[:4])[0]
    if not 0 < size <= 32 << 20 or len(data) < size + 4:
        return None
    try:
        frame = json.loads(data[4:4+size])
    except (ValueError, UnicodeError):
        return None
    if not isinstance(frame, dict) or frame.get('request_id') != 0:
        return None
    r = frame.get('result', {})
    if isinstance(r, dict) and r.get('ready') and r.get('api_version') == 2 and r.get('max_sessions') == 16:
        return frame
    return None


def launch_spec(native, wasmer_dir, transfer, inherited):
    # Matches internal/guest.Start for a fresh Database (restore == "").
    args = [str(native / 'wasmer-headless'), 'run', str(native / 'mariamem.wasmu'),
            '--no-tty', '--volume', str(transfer) + ':/snapshot-out']
    env = dict(inherited)
    env['WASMER_DIR'] = str(wasmer_dir)  # Go exec retains the last duplicate value.
    return args, env


def capture(argv, env, cwd, output, timeout):
    report = {'argv': argv, 'cwd': str(cwd), 'environment_file': 'environment.json',
              'stdin': 'pipe held open; no requests sent', 'process_group': 'new group (setpgid)',
              'natural_exit': False, 'returncode': None, 'exit_code': None, 'signal': None,
              'diagnostic_signals': [], 'ready_frame': None, 'stop_reason': None}
    proc = None
    streams = selectors.DefaultSelector()
    prefix = bytearray()
    end = time.monotonic() + timeout
    terminated_at = None
    try:
        with (output/'stdout.bin').open('wb') as stdout, (output/'stderr.log').open('wb') as stderr:
            proc = subprocess.Popen(argv, env=env, cwd=cwd, stdin=subprocess.PIPE,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    preexec_fn=os.setpgrp)
            report['pid'] = proc.pid
            streams.register(proc.stdout, selectors.EVENT_READ, stdout)
            streams.register(proc.stderr, selectors.EVENT_READ, stderr)
            while True:
                for key, _ in streams.select(0.05):
                    data = os.read(key.fileobj.fileno(), 65536)
                    if not data:
                        streams.unregister(key.fileobj)
                        continue
                    key.data.write(data)
                    key.data.flush()
                    if key.fileobj is proc.stdout and len(prefix) < (32 << 20) + 4:
                        prefix.extend(data)
                        report['ready_frame'] = ready_frame(prefix)
                code = proc.poll()
                if code is not None:
                    if not streams.get_map():
                        break
                    continue
                now = time.monotonic()
                if terminated_at is None and (report['ready_frame'] or now >= end):
                    report['stop_reason'] = 'ready_observed' if report['ready_frame'] else 'timeout'
                    os.killpg(proc.pid, signal.SIGTERM)
                    report['diagnostic_signals'].append('SIGTERM')
                    terminated_at = now
                elif terminated_at is not None and now - terminated_at >= 5:
                    os.killpg(proc.pid, signal.SIGKILL)
                    report['diagnostic_signals'].append('SIGKILL')
                    terminated_at = float('inf')
            report['returncode'] = proc.wait()
            report['natural_exit'] = not report['diagnostic_signals']
            if report['stop_reason'] is None:
                report['stop_reason'] = 'child_exit'
    except (Exception, KeyboardInterrupt) as exc:
        report['diagnostic_error'] = str(exc)
    finally:
        if proc is not None:
            if proc.poll() is None:
                os.killpg(proc.pid, signal.SIGKILL)
                report['diagnostic_signals'].append('SIGKILL')
            report['returncode'] = proc.wait()
            for pipe in (proc.stdin, proc.stdout, proc.stderr):
                pipe.close()
        streams.close()
        code = report['returncode']
        if code is not None:
            if code < 0:
                report['signal'] = signal.Signals(-code).name
            else:
                report['exit_code'] = code
    return report


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--native-dir', required=True, type=Path)
    p.add_argument('--output', required=True, type=Path, help='new diagnostic directory')
    p.add_argument('--cwd', type=Path, default=Path.cwd(), help='caller working directory; child inherits it')
    p.add_argument('--timeout', type=float, default=120)
    mode = p.add_mutually_exclusive_group()
    mode.add_argument('--environment-json', type=Path, help='exact caller environment mapping, if previously captured')
    mode.add_argument('--acceptance-env', action='store_true', help='recreate the acceptance harness environment policy with fresh temporary paths')
    args = p.parse_args()
    if args.timeout <= 0:
        p.error('--timeout must be positive')
    output = args.output.expanduser().resolve()
    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    result = {'diagnostic_only': True, 'platform_acceptance_passed': False}
    owned = []
    try:
        native = args.native_dir.expanduser().resolve(strict=True)
        env = dict(os.environ)
        if args.environment_json:
            env = json.loads(args.environment_json.read_text())
            if not isinstance(env, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in env.items()):
                raise ValueError('environment JSON must map strings to strings')
        if args.acceptance_env:
            base = Path(tempfile.mkdtemp(prefix='mariamem-diag-consumer-')).resolve()
            owned.append(base)
            env = {k:v for k,v in env.items() if not k.startswith(('GO','MARIAMEM_','WASMER_','WASIX_','DYLD_'))}
            env.update(GOWORK='off', GOENV='off', GOFLAGS='-modcacherw', GOTOOLCHAIN='local', CGO_ENABLED='0',
                       GO111MODULE='on', GOPROXY='https://proxy.golang.org,direct', GOSUMDB='sum.golang.org',
                       GOPATH=str(base/'gopath'), GOMODCACHE=str(base/'modcache'), GOCACHE=str(base/'gocache'),
                       TMPDIR=str(base/'runtime-tmp'))
            (base/'runtime-tmp').mkdir()
        # Mirrors os.MkdirTemp("", ...) using the child's effective TMPDIR.
        root = Path(tempfile.mkdtemp(prefix='mariamem-go-', dir=env.get('TMPDIR') or None)).resolve()
        owned.append(root)
        runtime = root/'runtime'
        runtime.mkdir(mode=0o700)
        transfer = Path(tempfile.mkdtemp(prefix='mariamem-transfer-', dir=env.get('TMPDIR') or None)).resolve()
        owned.append(transfer)
        argv, env = launch_spec(native, runtime, transfer, env)
        with (output/'environment.json').open('x') as f:
            os.chmod(f.name, 0o600)
            json.dump(env, f, indent=2)
        result.update(environment_mode='acceptance policy, fresh paths' if args.acceptance_env else 'caller environment',
                      artifact_sha256={n:digest(native/n) for n in ('wasmer-headless','mariamem.wasmu','mariamem.wasmu.json')})
        result.update(capture(argv, env, args.cwd.resolve(strict=True), output, args.timeout))
    except (Exception, KeyboardInterrupt) as exc:
        result['diagnostic_error'] = str(exc)
    finally:
        # Files exist even for a failure before spawning the child.
        for name in ('stdout.bin','stderr.log'):
            (output/name).touch(exist_ok=True)
        result.setdefault('returncode', None)
        result.setdefault('exit_code', None)
        result.setdefault('signal', None)
        for path in reversed(owned):
            shutil.rmtree(path, ignore_errors=True)
        (output/'result.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({k:result.get(k) for k in ('stop_reason','natural_exit','returncode','exit_code','signal','diagnostic_signals','diagnostic_error')}))
    return 1 if result.get('diagnostic_error') or (result.get('stop_reason') != 'ready_observed' and result.get('returncode') != 0) else 0


if __name__ == '__main__':
    raise SystemExit(main())
