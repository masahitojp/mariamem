#!/usr/bin/env python3
"""ORM and release-like zero-setup acceptance against exact current native/wheel bytes."""
import argparse
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile

from common import ROOT, digest
from native_target import manifest_target
from package_native import payload
from runtime_notices import verify as macos_notices
from linux_runtime_notices import verify as ubuntu_notices


def run(args):
    native, wheel, output = args.native_dir.resolve(), args.wheel.resolve(), args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    manifest = json.loads((native / 'manifest.json').read_text())
    target = manifest_target(manifest, ROOT)['platform']
    inventory = {p.name: digest(p) for p in native.iterdir() if p.is_file()}
    wheel_sha = digest(wheel)
    report = {'result': 'FAIL', 'stage': 'native_integrity', 'target': target,
              'source_sha': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
              'environment': {'os': platform.platform(), 'architecture': platform.machine(), 'python': platform.python_version(),
                              'go': subprocess.check_output(['go', 'version'], text=True).strip()},
              'native_files': inventory, 'wheel': {'filename': wheel.name, 'sha256': wheel_sha}, 'steps': {}}
    clean_env = {k: v for k, v in os.environ.items()
                 if not k.startswith(('MARIAMEM_', 'MYSQLMEM_', 'PYTHON', 'PYTEST'))}

    def execute(stage, command, env=None):
        report['stage'] = stage
        print('+', ' '.join(map(str, command)), flush=True)
        with (output / f'{stage}.log').open('w') as log:
            subprocess.run(list(map(str, command)), cwd=ROOT, env=env or clean_env,
                           stdout=log, stderr=subprocess.STDOUT, check=True)
        report['steps'][stage] = 'PASS'

    try:
        # Reuse canonical packaging/integrity checks without mutating these inputs.
        payload(ROOT, native)
        notices = macos_notices() if target == 'darwin-arm64' else ubuntu_notices()
        if not notices['complete'] or notices['runtime_sha256'] != inventory['wasmer-headless']:
            raise ValueError('runtime differs from the complete reviewed notices')
        report['steps']['native_integrity'] = 'PASS'
        execute('zero_setup', [sys.executable, 'tests/consumer/run_zero_setup.py', '--native-dir', native,
                               '--output', output / 'zero-setup'])
        execute('gorm', [sys.executable, 'tests/consumer/run_gorm.py', '--native-dir', native,
                         '--source-dir', ROOT, '--zero-options', '--output', output / 'gorm'])
        with tempfile.TemporaryDirectory(prefix='mariamem-v03-wheel-') as temporary:
            python = Path(temporary) / 'venv/bin/python'
            execute('wheel_install', [sys.executable, '-m', 'venv', python.parents[1]])
            execute('wheel_dependencies', [python, '-m', 'pip', 'install', wheel,
                                           '-r', ROOT / 'tests/consumer/sqlalchemy-requirements.txt'])
            # No override: SQLAlchemy consumes the installed wheel's own native bundle.
            execute('sqlalchemy', [python, 'tests/consumer/run_sqlalchemy.py', '--output', output / 'sqlalchemy'])
        execute('lifecycle', [sys.executable, 'scripts/verify.py', 'integration'],
                {**clean_env, 'MARIAMEM_NATIVE_DIR': str(native)})
        # This suite includes actual FOUND_ROWS 0/1 plus generic schema discovery.
        with tempfile.TemporaryDirectory(prefix='mariamem-v03-wire-') as temporary:
            host = Path(temporary) / 'mariamem-host'
            execute('wire_host', ['go', 'build', '-race', '-o', host, './cmd/mariamem-host'])
            execute('wire', [sys.executable, 'tests/integration.py'],
                    {**clean_env, 'MARIAMEM_NATIVE_DIR': str(native), 'MARIAMEM_TEST_HOST': str(host)})
            execute('snapshot_integrity', [sys.executable, 'tests/snapshots.py'],
                    {**clean_env, 'MARIAMEM_NATIVE_DIR': str(native), 'MARIAMEM_TEST_HOST': str(host)})
        if inventory != {p.name: digest(p) for p in native.iterdir() if p.is_file()} or digest(wheel) != wheel_sha:
            raise ValueError('native/wheel bytes changed during acceptance')
        sqlalchemy = json.loads((output / 'sqlalchemy/summary.json').read_text())
        gorm = json.loads((output / 'gorm/summary.json').read_text())
        # Fail closed on the required suite counts, not merely runner exit status.
        if sum(int(suite['tests']) for run in sqlalchemy['runs'] for suite in run['junit']) != 44 or not sqlalchemy['passed']:
            raise ValueError('SQLAlchemy did not demonstrate 44/44')
        records = [json.loads(path.read_text()) for path in (output / 'gorm').glob('[1-4]-*.json')]
        if len(records) != 4 or sum(len(record['cases']) for record in records) != 32 or any(run['exit_code'] for run in gorm) or not all(record['passed'] for record in records):
            raise ValueError('GORM did not demonstrate 32/32')
        report['sqlalchemy_cases'] = 44
        report['gorm_cases'] = 32
        report['result'] = 'PASS'
        report['stage'] = 'complete'
    except Exception as exc:
        report['error'] = str(exc)
        raise
    finally:
        (output / 'acceptance.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native-dir', type=Path, required=True)
    parser.add_argument('--wheel', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    report = run(parser.parse_args())
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
