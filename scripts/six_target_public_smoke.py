#!/usr/bin/env python3
"""Verify and exercise the accepted wheel served by GitHub Release."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import venv

from common import digest
from consumer_acceptance import bind_remote_origin, isolated_env, verify_module_files
from consumer_module import MODULE
from generated_release import checkout, wheel_name
from native_target import UBUNTU, target_metadata
from published_assets import require, verify_six_target_publication
from pypi_release import checksums
from release_candidate_preview import LIBCS, TARGETS

SMOKE_SCRIPT = Path(__file__).with_name('pypi_smoke.py')


def public_go_smoke(root, source, tag, work):
    checkout(root, source)
    env = isolated_env(work)
    (work / 'go.mod').write_text(f'module example.com/public-smoke\n\ngo 1.26.0\n\n'
                                f'require (\n {MODULE} {tag}\n github.com/go-sql-driver/mysql v1.10.1\n)\n')
    shutil.copyfile(root / 'scripts/guest_smoke/main.go', work / 'main.go')

    def go(*args, environment=env):
        return subprocess.check_output(['go', *args], cwd=work, env=environment, text=True)

    go('mod', 'download', MODULE)
    resolved = json.loads(go('list', '-m', '-json', MODULE))
    remote = json.loads(go('list', '-m', '-json', f'{MODULE}@{tag}', environment={**env, 'GOPROXY': 'direct'}))
    bind_remote_origin(resolved, remote, source, tag)
    verify_module_files(resolved, root)
    go('mod', 'tidy')
    print(go('run', '.'), end='')


def wheel_smoke(work, wheel, package, target):
    platform = 'linux-x86_64' if target == UBUNTU else target
    if target.startswith('linux-'):
        arch = target_metadata(target)['architecture']
        shutil.copyfile(SMOKE_SCRIPT, work / 'smoke.py')
        for family in LIBCS:
            image = f'quay.io/pypa/{family}_{arch}:latest'
            subprocess.run(['docker', 'pull', image], check=True)
            subprocess.run(['docker', 'run', '--rm', '-v', f'{work}:/input:ro', image, 'sh', '-ec',
                            'python=/opt/python/cp311-cp311/bin/python; '
                            '"$python" -m venv /tmp/smoke; '
                            '/tmp/smoke/bin/python -m pip install --only-binary=:all: "/input/$1" PyMySQL==1.1.1; '
                            '/tmp/smoke/bin/python -I /input/smoke.py "$2" "$3"',
                            'smoke', wheel.name, package, platform], check=True)
        return
    venv.EnvBuilder(with_pip=True).create(work / 'venv')
    python = work / 'venv' / ('Scripts/python.exe' if os.name == 'nt' else 'bin/python')
    subprocess.run([python, '-I', '-m', 'pip', 'install', '--only-binary=:all:', wheel, 'PyMySQL==1.1.1'],
                   cwd=work, check=True)
    subprocess.run([python, '-I', SMOKE_SCRIPT, package, platform], cwd=work, check=True)


def smoke(record, target, source, repository, go_source=None):
    package, tag = record['python_version'], record['git_tag']
    name = wheel_name(package, target)
    provenance_name = f'mariamem-{package}-provenance.json'
    with tempfile.TemporaryDirectory() as scratch:
        work = Path(scratch)
        release = json.loads(subprocess.check_output(['gh', 'api', f'repos/{repository}/releases/tags/{tag}'],
                                                     text=True))
        names = [asset['name'] for asset in release['assets']]
        require(release.get('tag_name') == tag and release.get('draft') is False
                and release.get('prerelease') == record['prerelease'] and len(names) == len(record['assets'])
                and set(names) == set(record['assets']), 'public release inventory differs')
        subprocess.run(['gh', 'release', 'download', tag, '--repo', repository, '--dir', work,
                        '--pattern', 'SHA256SUMS', '--pattern', provenance_name, '--pattern', name], check=True)
        for filename in ('SHA256SUMS', provenance_name, name):
            require(digest(work / filename) == record['assets'][filename], 'public asset digest differs: ' + filename)
        provenance = json.loads((work / provenance_name).read_text())
        sums = checksums((work / 'SHA256SUMS').read_text())
        verify_six_target_publication(record, provenance, sums, source,
                                      {'GIT_TAG': tag, 'PYTHON_VERSION': package}, repository)
        wheel_smoke(work, work / name, package, target)
        if go_source is not None:
            project = work / 'go'
            project.mkdir()
            public_go_smoke(go_source, source, tag, project)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--publication', type=Path, required=True)
    parser.add_argument('--target', choices=TARGETS, required=True)
    parser.add_argument('--source', required=True)
    parser.add_argument('--repository', required=True)
    parser.add_argument('--go-source', type=Path)
    args = parser.parse_args()
    smoke(json.loads(args.publication.read_text()), args.target, args.source, args.repository, args.go_source)


if __name__ == '__main__':
    main()
