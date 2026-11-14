#!/usr/bin/env python3
"""Accept one already-built Windows wheel in an independent installed environment."""
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

from release_version import PYTHON_VERSION
from git_identity import inspect_ref
from native_target import WINDOWS_X86, WINDOWS_ARM, target_metadata

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--target', choices=(WINDOWS_X86, WINDOWS_ARM), required=True)
    parser.add_argument('--wheel', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    target = target_metadata(args.target)
    expected_process = 'win-arm64' if target['goarch'] == 'arm64' else 'win-amd64'
    expected_machine = 'ARM64' if target['goarch'] == 'arm64' else 'AMD64'
    if (sysconfig.get_platform() != expected_process
            or platform.machine().upper() != expected_machine):
        raise RuntimeError('acceptance requires the matching native Python CPU')
    wheel = args.wheel.resolve()
    source = inspect_ref(ROOT, 'HEAD').source_commit
    record = {'source_commit': source, 'target': args.target, 'python': sys.version,
              'os': platform.platform(), 'python_platform': sysconfig.get_platform(),
              'version': PYTHON_VERSION, 'wheel': wheel.name, 'wheel_sha256': digest(wheel), 'status': 'FAIL'}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    try:
        if wheel.name != f'mariamem-{PYTHON_VERSION}-py3-none-{target["wheel_platform"]}.whl':
            raise RuntimeError('wheel filename differs from requested CPU')
        with zipfile.ZipFile(wheel) as archive:
            manifest_name = next(n for n in archive.namelist() if n.endswith('mariamem/_native/manifest.json'))
            manifest = json.loads(archive.read(manifest_name))
            host_name = next(n for n in archive.namelist() if n.endswith('mariamem/_native/mariamem-host.exe'))
            host_sha = hashlib.sha256(archive.read(host_name)).hexdigest()
            if host_sha != manifest['sha256']['mariamem-host.exe'] or manifest['platform'] != args.target:
                raise RuntimeError('wheel manifest/host hash differs')
            if manifest.get('package_version') != PYTHON_VERSION:
                raise RuntimeError('wheel package version differs')
            record['host_sha256'] = host_sha
        build = json.loads((ROOT / 'tests/evidence/alpha-wheel.json').read_text(encoding='utf-8'))
        if (build.get('source_commit') != source or build.get('sha256') != record['wheel_sha256']
                or build.get('manifest') != manifest):
            raise RuntimeError('acceptance wheel differs from the source-bound build receipt')
        with tempfile.TemporaryDirectory(prefix='mariamem-windows-acceptance-') as temporary:
            root = Path(temporary)
            environment = root / 'venv'
            venv.EnvBuilder(with_pip=True).create(environment)
            python = environment / 'Scripts/python.exe'
            env = {key: value for key, value in os.environ.items() if key not in ('PYTHONPATH', 'PYTHONHOME', 'PYTEST_ADDOPTS', 'PYTEST_PLUGINS', 'PYTEST_DISABLE_PLUGIN_AUTOLOAD')}
            env['PYTHONUTF8'] = '1'
            subprocess.run([str(python), '-m', 'pip', 'install', '--only-binary', ':all:',
                            '-r', str(ROOT / 'tests/windows/requirements.txt')], env=env, check=True)
            subprocess.run([str(python), '-m', 'pip', 'install', '--no-deps', '--only-binary', ':all:',
                            str(wheel)], env=env, check=True)
            cases = root / 'cases'
            cases.mkdir()
            for filename in ('test_distribution.py', 'test_prepare.py', 'test_control_pipe.py'):
                shutil.copyfile(ROOT / 'tests/windows' / filename, cases / filename)
            shutil.copyfile(ROOT / 'tests/consumer/test_database.py', cases / 'test_database.py')
            selected = [str(cases / 'test_distribution.py'), str(cases / 'test_prepare.py'),
                        str(cases / 'test_control_pipe.py'),
                        str(cases / 'test_database.py') + '::test_defaults_and_cleanup',
                        str(cases / 'test_database.py') + '::test_snapshot_defaults']
            results = root / 'results.xml'
            subprocess.run([str(python), '-m', 'pytest', '-q', '--confcutdir', str(cases),
                            '--junitxml', str(results), *selected],
                           cwd=cases, env=env, check=True, timeout=900)
            suites = list(ET.parse(results).getroot().iter('testsuite'))
            counts = {key: sum(int(s.get(key, '0')) for s in suites)
                      for key in ('tests', 'failures', 'errors', 'skipped')}
            record['cases'] = counts
            if counts != {'tests': 18, 'failures': 0, 'errors': 0, 'skipped': 0}:
                raise RuntimeError('installed Windows acceptance cases missing, skipped or failed')
        if digest(wheel) != record['wheel_sha256']:
            raise RuntimeError('acceptance changed the built wheel bytes')
        record['status'] = 'PASS'
    except BaseException as error:
        record['error'] = type(error).__name__ + ': ' + str(error)
        raise
    finally:
        args.output.write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
