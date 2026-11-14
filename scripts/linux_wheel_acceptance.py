#!/usr/bin/env python3
"""Accept one CPU's immutable wheel in native glibc and musl containers."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--target', choices=('linux-x86_64', 'linux-aarch64'), required=True)
    parser.add_argument('--arch', choices=('x86_64', 'aarch64'), required=True)
    args = parser.parse_args()
    if args.target != 'linux-' + args.arch or os.uname().machine != args.arch:
        raise ValueError('acceptance requires the native target CPU')
    wheel = json.loads((ROOT/'tests/evidence/alpha-wheel.json').read_text())
    path = ROOT/wheel['wheel']
    if hashlib.sha256(path.read_bytes()).hexdigest() != wheel['sha256']:
        raise ValueError('wheel changed after packaging')
    source = json.loads((ROOT/'build/linux-receipts/source.json').read_text())['source_commit']
    if wheel.get('source_commit') != source:
        raise ValueError('source identity differs')
    output = ROOT/'build/linux-receipts'
    for family in ('manylinux_2_28', 'musllinux_1_2'):
        image = f'quay.io/pypa/{family}_{args.arch}:latest'
        subprocess.run(['docker', 'pull', image], check=True)
        image_info = json.loads(subprocess.check_output(['docker', 'image', 'inspect', image], text=True))[0]
        if image_info['Architecture'] != {'x86_64': 'amd64', 'aarch64': 'arm64'}[args.arch]:
            raise ValueError('container CPU differs')
        record = dict(result='FAIL', target=args.target, family=family, source_commit=source,
                      wheel=path.name, sha256=wheel['sha256'], image_id=image_info['Id'],
                      image_digests=image_info['RepoDigests'])
        receipt = output/(family+'.json')
        receipt.write_text(json.dumps(record, indent=2)+'\n')
        with tempfile.TemporaryDirectory(prefix='linux-wheel-') as scratch:
            scratch = Path(scratch)
            # Only installed-package consumer inputs cross into the container.
            # Neither repo package nor a Go compiler is mounted.
            for src, name in ((path, path.name), (ROOT/'tests/consumer/test_database.py', 'test_database.py'),
                              (ROOT/'scripts/pypi_smoke.py', 'smoke.py')):
                (scratch/name).write_bytes(src.read_bytes())
            script = f'''set -eu
P=/opt/python/cp311-cp311/bin/python
$P -m venv /tmp/accepted
P=/tmp/accepted/bin/python
$P -m pip install --only-binary=:all: /input/{path.name} PyMySQL==1.1.1 pytest==8.4.2
cd /tmp
$P -I /input/smoke.py {wheel['manifest']['package_version']} {args.target}
$P -I -m pytest /input/test_database.py -q -k 'test_defaults_and_cleanup or test_snapshot_defaults'
$P -c 'import json,platform; print(json.dumps(dict(python=platform.python_version(),machine=platform.machine(),libc=platform.libc_ver(),kernel=platform.release())))'
'''
            try:
                result = subprocess.run(['docker', 'run', '--rm', '--network', 'bridge',
                                         '-v', f'{scratch}:/input:ro', image_info['Id'], 'sh', '-c', script],
                                        check=True, text=True, stdout=subprocess.PIPE, timeout=600)
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
                # Keep the original assertion/SQL failure visible in CI, not in a committed dump.
                if exc.stdout:
                    print(exc.stdout, flush=True)
                raise
            # Keep only small machine-readable observations; routine logs stay in CI.
            print(result.stdout, end='')
            record.update(result='PASS', environment=json.loads(result.stdout.strip().splitlines()[-1]))
            receipt.write_text(json.dumps(record, indent=2)+'\n')


if __name__ == '__main__':
    main()
