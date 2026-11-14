#!/usr/bin/env python3
"""Accept one CPU's immutable wheel in native glibc and musl containers."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import zipfile

from git_identity import inspect_ref
from release_version import PYTHON_VERSION

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
    source = inspect_ref(ROOT, 'HEAD').source_commit
    if source != json.loads((ROOT/'build/linux-receipts/source.json').read_text())['source_commit']:
        raise ValueError('checkout source identity differs')
    if wheel.get('source_commit') != source:
        raise ValueError('source identity differs')
    expected_name = f'mariamem-{PYTHON_VERSION}-py3-none-manylinux_2_28_{args.arch}.musllinux_1_2_{args.arch}.whl'
    if path.name != expected_name or wheel['manifest']['platform'] != args.target:
        raise ValueError('wheel filename/target differs')
    with zipfile.ZipFile(path) as archive:
        manifest = json.loads(archive.read('mariamem/_native/manifest.json'))
        host_sha = hashlib.sha256(archive.read('mariamem/_native/mariamem-host')).hexdigest()
        if (manifest != wheel['manifest'] or manifest.get('package_version') != PYTHON_VERSION
                or host_sha != manifest['sha256']['mariamem-host']):
            raise ValueError('wheel host/manifest differs from build receipt')
    output = ROOT/'build/linux-receipts'
    for family in ('manylinux_2_28', 'musllinux_1_2'):
        image = f'quay.io/pypa/{family}_{args.arch}:latest'
        subprocess.run(['docker', 'pull', image], check=True)
        image_info = json.loads(subprocess.check_output(['docker', 'image', 'inspect', image], text=True))[0]
        if image_info['Architecture'] != {'x86_64': 'amd64', 'aarch64': 'arm64'}[args.arch]:
            raise ValueError('container CPU differs')
        record = dict(result='FAIL', target=args.target, family=family, source_commit=source,
                      wheel=path.name, sha256=wheel['sha256'], host_sha256=host_sha, image_id=image_info['Id'],
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
$P -m pip install --only-binary=:all: /input/{path.name} PyMySQL==1.2.3 pytest==8.4.2
cd /tmp
$P -I /input/smoke.py {wheel['manifest']['package_version']} {args.target} {host_sha}
$P -I -m pytest /input/test_database.py -q --junitxml=/tmp/results.xml -k 'test_defaults_and_cleanup or test_snapshot_defaults'
$P -c 'import json,platform,xml.etree.ElementTree as E; suites=list(E.parse("/tmp/results.xml").getroot().iter("testsuite")); counts={{k:sum(int(s.get(k,"0")) for s in suites) for k in ("tests","failures","errors","skipped")}}; assert counts=={{"tests":2,"failures":0,"errors":0,"skipped":0}}, counts; print(json.dumps(dict(python=platform.python_version(),machine=platform.machine(),libc=platform.libc_ver(),kernel=platform.release(),cases=counts)))'
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
            environment = json.loads(result.stdout.strip().splitlines()[-1])
            if environment['cases'] != {'tests': 2, 'failures': 0, 'errors': 0, 'skipped': 0}:
                raise ValueError('missing installed acceptance cases')
            if hashlib.sha256(path.read_bytes()).hexdigest() != wheel['sha256']:
                raise ValueError('acceptance changed wheel bytes')
            record.update(result='PASS', environment=environment)
            receipt.write_text(json.dumps(record, indent=2)+'\n')


if __name__ == '__main__':
    main()
