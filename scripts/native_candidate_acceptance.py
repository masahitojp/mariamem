#!/usr/bin/env python3
"""Accept an exact macOS or Windows wheel and external Go module."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import sysconfig
import tempfile
import venv
import zipfile
import xml.etree.ElementTree as ET

from consumer_acceptance import verify_module_files
from consumer_module import MODULE, prepare_proxy
from release_version import GIT_TAG, PYTHON_VERSION
from git_identity import inspect_ref
from native_target import DARWIN, WINDOWS_X86, WINDOWS_ARM, manifest_target, target_metadata

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def accept_go(work, env):
    project = work / 'go-consumer'
    project.mkdir()
    shutil.copyfile(ROOT / 'tests/consumer/gorm/go.mod', project / 'go.mod')
    shutil.copyfile(ROOT / 'scripts/release_consumer/native_go.go.template', project / 'main.go')
    proxy = prepare_proxy(ROOT, work, GIT_TAG).as_uri()
    env = {**env, 'GOWORK': 'off', 'GOENV': 'off', 'GOFLAGS': '', 'GOTOOLCHAIN': 'go1.26.11',
           'CGO_ENABLED': '0', 'GOPROXY': proxy + ',https://proxy.golang.org', 'GONOSUMDB': MODULE,
           'GOMODCACHE': str(work / 'gomodcache')}
    subprocess.run(['go', 'mod', 'edit', '-require', f'{MODULE}@{GIT_TAG}'],
                   cwd=project, env=env, check=True, timeout=60)
    subprocess.run(['go', 'mod', 'download', f'{MODULE}@{GIT_TAG}'],
                   cwd=project, env={**env, 'GOPROXY': proxy}, check=True, timeout=180)
    subprocess.run(['go', 'mod', 'tidy'], cwd=project, env=env, check=True, timeout=180)
    resolved = json.loads(subprocess.check_output(['go', 'list', '-m', '-json', MODULE],
                                                  cwd=project, env=env, timeout=60))
    if resolved.get('Version') != GIT_TAG or 'Replace' in resolved:
        raise RuntimeError('external Go module did not resolve the candidate')
    verified = verify_module_files(resolved, ROOT)
    subprocess.run(['go', 'run', '-mod=readonly', '.'], cwd=project, env=env, check=True, timeout=600)
    return {'result': 'PASS', 'version': GIT_TAG, 'module_files_sha256': verified}


def accept_worker_failure(env):
    name = 'TestWorkerTrapFailsPendingCallsBeforeCompletion'
    result = subprocess.run(['go', 'test', '-json', '-count=1', '-timeout=2m',
                             '-run', '^' + name + '$', './internal/guest'],
                            cwd=ROOT, env=env, text=True, stdout=subprocess.PIPE, timeout=600)
    print(result.stdout, end='')
    result.check_returncode()
    if not any(event.get('Test') == name and event['Action'] == 'pass'
               for event in map(json.loads, result.stdout.splitlines())):
        raise RuntimeError('embedded worker failure test did not run')


def run_installed_cases(python, root, env, name, selected):
    results = root / (name + '.xml')
    subprocess.run([str(python), '-m', 'pytest', '-q', '--confcutdir', str(root),
                    '--junitxml', str(results), *selected],
                   cwd=root, env=env, check=True, timeout=900)
    suites = ET.parse(results).getroot().iter('testsuite')
    counts = dict.fromkeys(('tests', 'failures', 'errors', 'skipped'), 0)
    for suite in suites:
        for key in counts:
            counts[key] += int(suite.get(key, '0'))
    return counts


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--target', choices=(DARWIN, WINDOWS_X86, WINDOWS_ARM), required=True)
    parser.add_argument('--wheel', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    target = target_metadata(args.target, ROOT)
    windows = target['goos'] == 'windows'
    if windows:
        expected_process = 'win-arm64' if target['goarch'] == 'arm64' else 'win-amd64'
        expected_machine = 'ARM64' if target['goarch'] == 'arm64' else 'AMD64'
        if (sysconfig.get_platform() != expected_process
                or platform.machine().upper() != expected_machine):
            raise RuntimeError('acceptance requires the matching native Windows Python CPU')
    elif (platform.system() != 'Darwin' or platform.machine() != 'arm64'
          or int(platform.mac_ver()[0].split('.')[0]) < target['minimum_macos']):
        raise RuntimeError('acceptance requires a supported native macOS arm64 host')
    wheel = args.wheel.resolve()
    source = inspect_ref(ROOT, 'HEAD').source_commit
    record = {'contract': 'native-candidate-v1', 'source_commit': source, 'target': args.target,
              'python': sys.version, 'scenarios': {},
              'os': platform.platform(), 'python_platform': sysconfig.get_platform(),
              'version': PYTHON_VERSION, 'wheel': wheel.name, 'wheel_sha256': digest(wheel), 'status': 'FAIL'}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    try:
        if wheel.name != f'mariamem-{PYTHON_VERSION}-py3-none-{target["wheel_platform"]}.whl':
            raise RuntimeError('wheel filename differs from requested CPU')
        with zipfile.ZipFile(wheel) as archive:
            manifest_name = next(n for n in archive.namelist() if n.endswith('mariamem/_native/manifest.json'))
            manifest = json.loads(archive.read(manifest_name))
            host_name = target.get('host_name', 'mariamem-host')
            host = next(n for n in archive.namelist() if n.endswith('mariamem/_native/' + host_name))
            host_sha = hashlib.sha256(archive.read(host)).hexdigest()
            if host_sha != manifest['sha256'][host_name] or manifest_target(manifest, ROOT) != target:
                raise RuntimeError('wheel manifest/host hash differs')
            if manifest.get('package_version') != PYTHON_VERSION:
                raise RuntimeError('wheel package version differs')
            record['host_sha256'] = host_sha
            pins = json.loads((ROOT / 'release/generated-go-inputs.json').read_text(encoding='utf-8'))
            if manifest['guest_sha256'] != pins['guest_sha256']:
                raise RuntimeError('wheel guest differs from the canonical input')
            record['guest_sha256'] = pins['guest_sha256']
        build = json.loads((ROOT / 'tests/evidence/alpha-wheel.json').read_text(encoding='utf-8'))
        if (build.get('source_commit') != source or build.get('sha256') != record['wheel_sha256']
                or build.get('manifest') != manifest):
            raise RuntimeError('acceptance wheel differs from the source-bound build receipt')
        with tempfile.TemporaryDirectory(prefix='mariamem-native-acceptance-') as temporary:
            root = Path(temporary).resolve()
            if root.is_relative_to(ROOT):
                raise RuntimeError('consumer environment must be outside the candidate checkout')
            environment = root / 'venv'
            venv.EnvBuilder(with_pip=True).create(environment)
            python = environment / ('Scripts/python.exe' if windows else 'bin/python')
            env = {key: value for key, value in os.environ.items()
                   if not key.upper().startswith(('PYTHON', 'PYTEST', 'MARIAMEM_', 'MYSQLMEM_'))}
            env.update(PYTHONUTF8='1', GOTOOLCHAIN='go1.26.11', GOWORK='off', GOENV='off',
                       GOFLAGS='', CGO_ENABLED='0')
            subprocess.run([str(python), '-m', 'pip', 'install', '--only-binary', ':all:',
                            '-r', str(ROOT / 'tests/consumer/sqlalchemy-requirements.txt')],
                           cwd=root, env=env, check=True, timeout=180)
            subprocess.run([str(python), '-m', 'pip', 'install', '--no-deps', '--only-binary', ':all:',
                            str(wheel)], cwd=root, env=env, check=True, timeout=180)
            cases = root / 'cases'
            cases.mkdir()
            shutil.copyfile(ROOT / 'tests/consumer/test_database.py', cases / 'test_database.py')
            shutil.copyfile(ROOT / 'tests/consumer/test_native_candidate.py', cases / 'test_native_candidate.py')
            installed = 'test_database.py::test_defaults_and_cleanup'
            common = run_installed_cases(python, cases, env, 'common', [installed, 'test_native_candidate.py'])
            if common != {'tests': 3, 'failures': 0, 'errors': 0, 'skipped': 0}:
                raise RuntimeError('shared installed cases missing, skipped or failed')
            record['common_cases'] = common
            if windows:
                names = ('test_distribution.py', 'test_prepare.py', 'test_control_pipe.py')
                for filename in names:
                    shutil.copyfile(ROOT / 'tests/windows' / filename, cases / filename)
                record['cases'] = run_installed_cases(python, cases, env, 'windows',
                                                      [*names, installed, 'test_database.py::test_snapshot_defaults'])
                if record['cases'] != {'tests': 18, 'failures': 0, 'errors': 0, 'skipped': 0}:
                    raise RuntimeError('installed Windows cases missing, skipped or failed')
            smoke = root / 'python_smoke.py'
            shutil.copyfile(ROOT / 'scripts/release_consumer/python_smoke.py', smoke)
            smoke_receipt = root / 'sqlalchemy.json'
            subprocess.run([str(python), '-I', str(smoke), '--version', PYTHON_VERSION,
                            '--wheel-sha256', record['wheel_sha256'], '--output', str(smoke_receipt)],
                           cwd=root, env=env, check=True, timeout=180)
            record['sqlalchemy'] = json.loads(smoke_receipt.read_text(encoding='utf-8'))
            if record['sqlalchemy']['result'] != 'PASS' or record['sqlalchemy']['wheel_sha256'] != record['wheel_sha256']:
                raise RuntimeError('SQLAlchemy receipt does not match the installed wheel')
            record['go_consumer'] = accept_go(root, env)
            accept_worker_failure(env)
        if digest(wheel) != record['wheel_sha256']:
            raise RuntimeError('acceptance changed the built wheel bytes')
        record['scenarios'] = dict(installed_wheel='PASS', orm_round_trip='PASS',
                                   parallel_fork_isolation='PASS', failure_cleanup='PASS')
        record['status'] = 'PASS'
    except BaseException as error:
        record['error'] = type(error).__name__ + ': ' + str(error)
        raise
    finally:
        args.output.write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
