#!/usr/bin/env python3
"""Exact frozen candidate/public assets through clean Go and installed-wheel consumers."""
import argparse
import json
import os
from pathlib import Path
import platform
import re
import runpy
import shutil
import subprocess
import sys
import tarfile
import tempfile

from common import ROOT, digest
from consumer_module import MODULE, prepare_proxy, source_identity
from native_target import DARWIN, UBUNTU, target_metadata
from platform_acceptance import bind_remote_origin, isolated_env

STEPS = ('go_zero_setup', 'gorm_schema', 'cached_offline', 'python_sqlalchemy')
HARNESS = ('scripts/release_consumer_smoke.py', 'scripts/consumer_module.py',
           'scripts/release_consumer/main.go.template', 'scripts/release_consumer/python_smoke.py')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def environment(target):
    env = {'system': platform.system(), 'architecture': platform.machine()}
    if target == DARWIN:
        env['product_version'] = subprocess.check_output(['sw_vers', '-productVersion'], text=True).strip()
        require(env['system'] == 'Darwin' and env['architecture'] == 'arm64'
                and int(env['product_version'].split('.')[0]) >= 15, 'smoke requires macOS 15+ arm64')
    else:
        values = dict(line.split('=', 1) for line in Path('/etc/os-release').read_text().splitlines() if '=' in line)
        env.update(distribution=values['ID'].strip('"'), version_id=values['VERSION_ID'].strip('"'))
        require(env['system'] == 'Linux' and env['architecture'] == 'x86_64'
                and env['distribution'] == 'ubuntu' and env['version_id'] == '24.04',
                'smoke requires Ubuntu 24.04 x86_64')
    return env


def verify_go(record, tag, version, target, native_hash, lock_hash):
    require(record.get('result') == 'PASS' and record.get('stage') == 'complete', 'Go smoke failed')
    require(record.get('module_version') == tag and record.get('native_version') == version,
            'Go smoke resolved another module/native version')
    require(record.get('cache_initially_empty') is True and record.get('native_overrides') is False,
            'Go smoke did not start with an empty cache and no overrides')
    receipt = record.get('receipt', {})
    require(receipt.get('tag') == tag and receipt.get('target') == target
            and receipt.get('archive_sha256') == native_hash and receipt.get('inputs_lock_sha256') == lock_hash,
            'Go resolved another candidate bundle/provenance')
    require(set(record.get('steps', {})) == set(STEPS[:-1])
            and all(v == 'PASS' for v in record['steps'].values()), 'Go smoke steps missing/failed')
    prefix = 'https://github.com/masahitojp/mariamem/releases/download/' + tag + '/'
    expected = {prefix + target_metadata(target)['bundle_name'] + '.tar.gz', prefix + 'SHA256SUMS',
                'https://api.github.com/repos/masahitojp/mariamem/releases/tags/' + tag}
    require(expected <= set(record.get('requests', [])), 'automatic exact-tag downloads not observed')


def verify_python(record, version, wheel_hash):
    require(record.get('result') == 'PASS' and record.get('version') == version
            and record.get('wheel_sha256') == wheel_hash, 'SQLAlchemy smoke failed or used another wheel')
    require(record.get('consumer_outside_repository') is True and record.get('native_overrides') is False
            and record.get('matched_rowcount') == 1, 'SQLAlchemy normal FOUND_ROWS semantics not proven')


def verify_smoke(record, root, commit, tag, version, target, native_hash, wheel_hash):
    require(record.get('schema_version') == 1 and record.get('result') == 'PASS'
            and record.get('mode') == 'candidate', 'required candidate consumer smoke missing/failed')
    require((record.get('source_sha'), record.get('git_tag'), record.get('python_version'), record.get('target'))
            == (commit, tag, version, target), 'consumer smoke source/version/platform differs')
    require(record.get('native_sha256') == native_hash and record.get('wheel_sha256') == wheel_hash,
            'consumer smoke artifact hashes differ')
    require(record.get('go_source_sha256') == source_identity(root), 'consumer private module source differs')
    require(record.get('harness_sha256') == {name: digest(root / name) for name in HARNESS},
            'consumer smoke harness differs from candidate')
    require(set(record.get('steps', {})) == set(STEPS) and all(v == 'PASS' for v in record['steps'].values()),
            'required consumer smoke step missing/skipped/failed')
    env = record.get('environment', {})
    if target == DARWIN:
        require(env.get('system') == 'Darwin' and env.get('architecture') == 'arm64'
                and env.get('product_version', '').startswith('15.'), 'consumer smoke platform differs')
    else:
        require(env.get('system') == 'Linux' and env.get('architecture') == 'x86_64'
                and env.get('distribution') == 'ubuntu' and env.get('version_id') == '24.04',
                'consumer smoke platform differs')
    verify_go(record.get('go', {}), tag, version, target, native_hash, digest(root / 'release/inputs.lock.json'))
    verify_python(record.get('python', {}), version, wheel_hash)


def require_candidate_smoke(root, commit, tag, version, target, native_hash, wheel_hash):
    path = root / 'build/release/ci-consumer-smoke.json'
    require(path.is_file(), 'required candidate consumer smoke missing; rerun acceptance')
    verify_smoke(json.loads(path.read_text()), root, commit, tag, version, target, native_hash, wheel_hash)
    return digest(path)


def candidate_distribution(archive, work, tag, expected):
    directory = work / 'distribution'
    directory.mkdir()
    shutil.copyfile(archive, directory / archive.name)
    require(digest(directory / archive.name) == expected, 'candidate distribution bytes changed')
    sums = directory / 'SHA256SUMS'
    sums.write_text(f'{expected}  {archive.name}\n')
    assets = [{'name': p.name, 'browser_download_url':
               f'https://github.com/masahitojp/mariamem/releases/download/{tag}/{p.name}',
               'digest': 'sha256:' + digest(p)} for p in (directory / archive.name, sums)]
    (directory / 'release.json').write_text(json.dumps({'tag_name': tag, 'draft': False, 'assets': assets}))
    return directory


def run(root, commit, archive, wheel, output, *, mode='candidate', tag=None):
    root, archive, wheel, output = (Path(p).resolve() for p in (root, archive, wheel, output))
    output.parent.mkdir(parents=True, exist_ok=True)
    require(not output.exists(), 'consumer evidence already exists; refuse stale reuse')
    report = {'schema_version': 1, 'mode': mode, 'source_sha': commit, 'result': 'FAIL',
              'stage': 'identity', 'steps': {}}
    log = output.with_suffix('.log')
    def execute(command, cwd, env):
        with log.open('a') as stream:
            stream.write(json.dumps(list(map(str, command))) + '\n'); stream.flush()
            subprocess.run(list(map(str, command)), cwd=cwd, env=env, stdout=stream,
                           stderr=subprocess.STDOUT, check=True, timeout=600)
    try:
        require(mode in ('candidate', 'published') and re.fullmatch('[0-9a-f]{40}', commit), 'invalid smoke mode/source')
        version = runpy.run_path(str(root / 'python/mariamem/_version.py'))
        tag = tag or version['GIT_TAG']
        require(tag == version['GIT_TAG'], 'smoke tag differs from candidate version')
        with tarfile.open(archive, 'r:gz') as tar:
            manifests = [m for m in tar.getmembers() if m.name.endswith('/manifest.json')]
            require(len(manifests) == 1, 'native manifest missing/ambiguous')
            manifest = json.load(tar.extractfile(manifests[0]))
        target = manifest['platform']
        require(target in (DARWIN, UBUNTU) and archive.name == target_metadata(target)['bundle_name'] + '.tar.gz',
                'native filename/platform differs')
        require(manifest['package_version'] == version['PYTHON_VERSION'], 'native package version differs')
        require(wheel.name == f"mariamem-{version['PYTHON_VERSION']}-py3-none-{target_metadata(target)['wheel_platform']}.whl",
                'wheel filename/platform/version differs')
        report.update(git_tag=tag, python_version=version['PYTHON_VERSION'], target=target,
                      native_sha256=digest(archive), wheel_sha256=digest(wheel), environment=environment(target),
                      go_source_sha256=source_identity(root), harness_sha256={p: digest(root / p) for p in HARNESS})
        with tempfile.TemporaryDirectory(prefix='mariamem-release-consumer-') as temporary:
            work = Path(temporary).resolve()
            require(not work.is_relative_to(root), 'consumer is inside checkout')
            env = isolated_env(work)
            env = {k: v for k, v in env.items() if k not in ('PYTHONPATH', 'PYTHONHOME', 'PYTEST_ADDOPTS')
                   and not k.startswith(('MYSQLMEM_', 'ZERO_', 'SMOKE_'))}
            go = Path(subprocess.check_output(['go', 'env', 'GOROOT'], env=env, text=True).strip()) / 'bin/go'
            home = work / 'home'; home.mkdir()
            cache = home / 'Library/Caches' if target == DARWIN else work / 'cache'
            cache.mkdir(parents=True)
            require(not list(cache.iterdir()), 'cache must be initially empty')
            env.update(HOME=str(home), XDG_CACHE_HOME=str(cache), CGO_ENABLED="1")
            project = work / 'go-consumer'; project.mkdir()
            (project / 'main.go').write_bytes((root / HARNESS[2]).read_bytes())
            (project / 'go.mod').write_text(f'module example.com/release-consumer\n\ngo 1.26.0\n\nrequire (\n {MODULE} {tag}\n gorm.io/gorm v1.31.1\n gorm.io/driver/mysql v1.6.0\n github.com/go-sql-driver/mysql v1.9.3\n)\n')
            distribution = None
            if mode == 'candidate':
                require(subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip() == commit,
                        'candidate checkout source differs')
                distribution = candidate_distribution(archive, work, tag, report['native_sha256'])
                proxy = prepare_proxy(root, work, tag)
                env.update(GOPROXY=proxy.as_uri()+',https://proxy.golang.org', GONOSUMDB=MODULE)
            report['stage'] = 'go_build'
            if mode == 'candidate':
                # Resolve this module from the private exact-source proxy first;
                # public dependency fallback must never substitute its Go code.
                execute([go, 'mod', 'download', MODULE+'@'+tag], project,
                        {**env, 'GOPROXY': proxy.as_uri()})
            execute([go, 'get', MODULE+'@'+tag, 'gorm.io/gorm@v1.31.1',
                     'gorm.io/driver/mysql@v1.6.0', 'github.com/go-sql-driver/mysql@v1.9.3'], project, env)
            execute([go, 'mod', 'tidy'], project, env)
            if mode == 'published':
                resolved = json.loads(subprocess.check_output([go, 'list', '-m', '-json', MODULE], cwd=project, env=env, text=True))
                remote = json.loads(subprocess.check_output([go, 'list', '-m', '-json', MODULE+'@'+tag], cwd=project,
                                    env={**env, 'GOPROXY':'direct'}, text=True))
                report['module_resolved'] = bind_remote_origin(resolved, remote, commit, tag)
            execute([go, 'build', '-race', '-mod=readonly', '-o', work / 'consumer', '.'], project, env)
            report['stage'] = 'go_zero_setup'
            command = [work / 'consumer', '--tag', tag, '--version', version['PYTHON_VERSION'], '--target', target,
                       '--archive-sha256', report['native_sha256'], '--lock-sha256', digest(root / 'release/inputs.lock.json'),
                       '--cache-root', cache, '--output', work / 'go.json']
            if distribution:
                command += ['--distribution', distribution]
            execute(command, project, env)
            report['go'] = json.loads((work / 'go.json').read_text())
            verify_go(report['go'], tag, version['PYTHON_VERSION'], target, report['native_sha256'], digest(root / 'release/inputs.lock.json'))
            report['steps'].update(report['go']['steps'])
            report['stage'] = 'python_sqlalchemy'
            execute([sys.executable, '-m', 'venv', work / 'venv'], work, env)
            python = work / 'venv/bin/python'
            execute([python, '-m', 'pip', 'install', wheel, 'SQLAlchemy==2.0.54', 'PyMySQL==1.2.3'], work, env)
            program = work / 'python_smoke.py'; program.write_bytes((root / HARNESS[3]).read_bytes())
            execute([python, program, '--version', version['PYTHON_VERSION'], '--wheel-sha256', report['wheel_sha256'],
                     '--output', work / 'python.json'], work, env)
            report['python'] = json.loads((work / 'python.json').read_text())
            verify_python(report['python'], version['PYTHON_VERSION'], report['wheel_sha256'])
            report['steps']['python_sqlalchemy'] = 'PASS'
        require(digest(archive) == report['native_sha256'] and digest(wheel) == report['wheel_sha256'], 'candidate bytes changed')
        report.update(result='PASS', stage='complete')
    except Exception as exc:
        report['error'] = str(exc)
        raise
    finally:
        output.write_text(json.dumps(report, indent=2) + '\n')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--candidate-sha', required=True)
    parser.add_argument('--archive', type=Path, required=True)
    parser.add_argument('--wheel', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.root, args.candidate_sha, args.archive, args.wheel, args.output), indent=2))


if __name__ == '__main__':
    main()
