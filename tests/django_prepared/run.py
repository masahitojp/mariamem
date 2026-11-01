"""Bounded public-entry campaign; Release can reuse its existing built host.

Local use may explicitly name a published host's source commit. That is a
Python-adapter check on a reused host, not qualification of a newly built host.
"""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'scripts'))
from git_identity import require_commit


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_host(path, commit):
    require_commit(ROOT, commit)
    info = subprocess.check_output(['go', 'version', '-m', str(path)], text=True)
    if f'vcs.revision={commit}' not in info or 'vcs.modified=false' not in info:
        raise ValueError('Host identity does not match declared clean source_commit')
    return dict(source_commit=commit, sha256=digest(path), build_info=info)


def alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def run_case(host, out, runner, mode, *, installed=False):
    directory = out / f'{runner}-{mode}'
    directory.mkdir()
    events = directory / 'events.jsonl'
    python_paths = [HERE, ROOT / 'tests/e2e_native_control/pythonapp', ROOT / 'tests/django_lifecycle']
    if not installed:
        python_paths.insert(0, ROOT / 'python')
    env = dict(os.environ, DJANGO_SETTINGS_MODULE='prepared_settings',
               MARIAMEM_PREPARED_HOST=str(host), MARIAMEM_PREPARED_EVENTS=str(events),
               MARIAMEM_PREPARED_MODE=mode, PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',
               PYTHONPATH=os.pathsep.join(map(str, python_paths)))
    classes = ['AtomicCases', 'TransactionalCases']
    if mode in ('body-failure', 'prepare-failure'):
        classes = ['TransactionalCases']
    elif mode == 'class-failure':
        classes = ['SetupFailure', 'TransactionalCases']
    elif mode == 'class-skip':
        classes = ['SetupSkip', 'TransactionalCases']
    if runner == 'manage':
        command = [sys.executable, '-m', 'django', 'test',
                   *['cases.' + cls for cls in classes], '--noinput', '-v', '2']
        if mode == 'reverse':
            command.append('--reverse')
    else:
        command = [sys.executable, '-m', 'pytest', '-p', 'pytest_django.plugin',
                   '-p', 'mariamem.django.pytest_plugin', str(HERE / 'cases.py'),
                   '-k', ' or '.join(classes), '-v', '-rs', '-o', 'addopts=']
    if mode == 'repeat':
        if runner == 'manage':
            code = ('import django; django.setup(); '
                    'from django.core.management import call_command; '
                    "[call_command('test','cases.AtomicCases','cases.TransactionalCases',interactive=False,verbosity=2) for _ in range(2)]")
        else:
            argv = command[3:]  # arguments after python -m pytest
            code = 'import pytest; results=[pytest.main(' + repr(argv) + ') for _ in range(2)]; raise SystemExit(any(results))'
        command = [sys.executable, '-c', code]
    process = subprocess.Popen(command, cwd=ROOT, env=env, text=True,
                               stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               start_new_session=True)
    timed_out = False
    try:
        stdout, _ = process.communicate(timeout=180)
    except subprocess.TimeoutExpired:
        timed_out = True
        os.killpg(process.pid, signal.SIGKILL)
        stdout, _ = process.communicate()
    except BaseException:
        os.killpg(process.pid, signal.SIGKILL)
        process.communicate()
        raise
    result = subprocess.CompletedProcess(command, process.returncode, stdout)
    (directory / 'stdout.txt').write_text(result.stdout)
    records = [json.loads(line) for line in (events.read_text() if events.exists() else '').splitlines()]
    pids = {r['pid'] for r in records if r['event'] == 'host'}
    deadline = time.monotonic() + 5
    while any(alive(pid) for pid in pids) and time.monotonic() < deadline:
        time.sleep(.02)
    count = lambda name: sum(r['event'] == name for r in records)
    expected_bodies = 0 if mode in ('prepare-failure', 'busy-source', 'migration-failure') else 8 if mode == 'repeat' else 4 if mode in ('healthy', 'reverse') else 2
    runs = 2 if mode == 'repeat' else 1
    marker = dict(**{'body-failure': 'PREPARED_BODY_FAILURE',
                     'prepare-failure': 'PREPARED_SEED_FAILURE',
                     'busy-source': 'SQL connections are still active',
                     'migration-failure': 'w3_missing_migration_table',
                     'class-failure': 'PREPARED_CLASS_FAILURE',
                     'class-skip': 'PREPARED_CLASS_SKIP'}).get(mode)
    expected_exit = 1 if mode in ('body-failure', 'prepare-failure', 'class-failure', 'busy-source', 'migration-failure') else 0
    # Django's CLI reports startup failures as 1; pytest setup errors also use 1.
    checks = dict(within_timeout=not timed_out, exit_code=result.returncode == expected_exit,
                  bodies=count('body') == expected_bodies,
                  prepare_once=count('prepare') == (0 if mode == 'migration-failure' else runs),
                  no_bad_body=count('BAD_BODY') == 0,
                  marker=marker is None or marker in result.stdout,
                  class_data=count('class-data') == (runs if mode in ('healthy', 'reverse', 'repeat') else 0),
                  class_commit=count('class-commit') == (runs if mode in ('healthy', 'reverse', 'repeat') else 0),
                  independent_commit=count('commit-observed') == (0 if mode in ('prepare-failure', 'busy-source', 'migration-failure') else runs),
                  host_reaped=len(pids) == runs and not any(alive(pid) for pid in pids))
    if any(alive(pid) for pid in pids):
        # Preserve the failed cleanup observation, then stop this owned process
        # group rather than leaving a failed probe's server running.
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    observation = dict(runner=runner, mode=mode, exit_code=result.returncode,
                       checks=checks, result='PASS' if all(checks.values()) else 'FAIL')
    (directory / 'assessment.json').write_text(json.dumps(observation, indent=2) + '\n')
    print(runner, mode, observation['result'], flush=True)
    return observation


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', type=Path, required=True)
    parser.add_argument('--host-source-commit', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--installed', action='store_true', help='Import the installed candidate wheel, never repository python/')
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    host = args.host.resolve()
    identity = check_host(host, args.host_source_commit)
    inputs = list((ROOT / 'python/mariamem/django').glob('*.py')) + list(HERE.glob('*.py'))
    inputs += list((ROOT / 'tests/e2e_native_control/pythonapp/orders').rglob('*.py'))
    inputs += list((ROOT / 'tests/django_lifecycle/failure_migrations').glob('*.py'))
    report = dict(installed=args.installed, host=identity, system=platform.system(), machine=platform.machine(),
                  python=sys.version, packages={p: importlib.metadata.version(p) for p in
                      ['Django', 'pytest', 'pytest-django', 'mysqlclient']},
                  adapter_source_commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                  adapter_dirty=bool(subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT)),
                  inputs={str(p.relative_to(ROOT)): digest(p) for p in inputs})
    (out / 'inputs.json').write_text(json.dumps(report, indent=2) + '\n')
    observations = [run_case(host, out, runner, mode, installed=args.installed) for runner in ('manage', 'pytest')
                    for mode in ('healthy', 'reverse', 'body-failure', 'class-failure',
                                 'class-skip', 'prepare-failure', 'busy-source', 'migration-failure', 'repeat')]
    result = dict(result='PASS' if all(o['result'] == 'PASS' for o in observations) else 'FAIL',
                  observations=observations)
    (out / 'assessment.json').write_text(json.dumps(result, indent=2) + '\n')
    return 0 if result['result'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
