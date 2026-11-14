#!/usr/bin/env python3
"""Immutable PyPI transfer of accepted GitHub wheels; never build or create tags."""
import argparse
import json
import os
import platform
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import venv
import zipfile

from ci_release_reuse import GitHub, WORKFLOW
from common import ROOT, digest
from git_identity import inspect_ref, require_commit, read_release_pin, verify_release_pin
from published_assets import require, verify_publication

SCHEMA = 'pypi-publication-v1'
SMOKE_ENV = {'runner': 'macos-15', 'python': '3.14', 'driver': 'PyMySQL==1.1.1',
             'pip': 'pip==25.3', 'platform': 'darwin-arm64'}


def run(args, root=ROOT):
    return subprocess.check_output([str(a) for a in args], cwd=root, text=True).strip()


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + '\n')


def output(**values):
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'], 'a') as stream:
            for key, value in values.items():
                stream.write(f'{key}={value}\n')


def stable_version(tag):
    require(isinstance(tag, str) and re.fullmatch(r'v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)', tag),
            'PyPI requires a canonical stable release tag')
    return tag[1:]


def selected_wheels(version):
    # Deliberately explicit. #170/#171 add qualified targets; generic Linux is NOT PyPI-compatible.
    return {f'mariamem-{version}-py3-none-macosx_15_0_arm64.whl'}


def checksums(text):
    result = {}
    for line in text.splitlines():
        match = re.fullmatch(r'([0-9a-f]{64})  ([A-Za-z0-9_.-]+)', line)
        require(match is not None, 'invalid SHA256SUMS line')
        sha, name = match.groups()
        require(name not in result, 'duplicate SHA256SUMS filename')
        result[name] = sha
    return result


def pypi_files(version):
    try:
        with urllib.request.urlopen(f'https://pypi.org/pypi/mariamem/{version}/json', timeout=60) as response:
            data = json.load(response)
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return {}
        raise
    require(data['info']['name'] == 'mariamem' and data['info']['version'] == version,
            'PyPI response identity differs')
    result = {}
    for item in data['urls']:
        name = item['filename']
        require(name not in result, 'duplicate PyPI filename')
        result[name] = {'sha256': item['digests']['sha256'], 'yanked': item.get('yanked', False)}
    return result


def missing_files(expected, actual):
    missing = []
    for name, sha in expected.items():
        if name not in actual:
            missing.append(name)
        else:
            require(actual[name]['sha256'] == sha, 'PyPI hash conflict: ' + name)
            require(not actual[name]['yanked'], 'PyPI file is yanked: ' + name)
    return sorted(missing)


def verify_origin(report, provenance, sums, release, source, tag, repository):
    version = stable_version(tag)
    names = {f'mariamem-{version}-provenance.json', f'mariamem-{version}-corresponding-source.tar.gz',
             f'mariamem-{version}-py3-none-linux_x86_64.whl', *selected_wheels(version)}
    require(set(sums) == names, 'GitHub asset contract differs')
    assets = release['assets']
    require(release.get('tag_name') == tag and release.get('draft') is False
            and release.get('prerelease') is False, 'GitHub release is not published stable')
    require(len(assets) == len(names) + 1 and {a['name'] for a in assets} == names | {'SHA256SUMS'},
            'GitHub release filenames differ')
    # Reuse the existing both-platform final-artifact READY validation, including wheel identities.
    publication = report or {
        'version': 3, 'contract': 'generated-go-v1', 'status': 'PUBLISHED',
        'source_commit': source, 'git_tag': tag, 'python_version': version,
        'repository': repository, 'platforms': provenance['platforms'],
        'assets': {**sums, 'SHA256SUMS': 'checked separately'},
    }
    verify_publication(publication, provenance, source,
                       {'GIT_TAG': tag, 'PYTHON_VERSION': version}, repository)
    require({k: v for k, v in publication['assets'].items() if k != 'SHA256SUMS'} == sums,
            'publication/checksum inventory differs')
    return {name: sums[name] for name in selected_wheels(version)}


def prepare(root, directory, source, tag, operation, repository, publication=None):
    require(operation in {'verify', 'release'}, 'invalid publication operation')
    require(repository == 'masahitojp/mariamem', 'unexpected publication repository')
    require_commit(root, source)
    tooling = inspect_ref(root, 'HEAD').source_commit
    dirty = bool(run(['git', 'status', '--porcelain', '--untracked-files=no'], root))
    require(operation == 'verify' or not dirty, 'publication tooling checkout must be clean')
    record = {'schema': SCHEMA, 'source_commit': source, 'tooling_commit': tooling,
              'repository': repository, 'operation': operation, 'tooling_dirty': dirty,
              'status': 'FAILED', 'stage': 'origin'}
    path = directory / 'ci-pypi-publication.json'
    directory.mkdir(parents=True, exist_ok=True)
    try:
        original = json.loads(publication.read_text()) if publication else None
        if original:
            require(original.get('status') == 'PUBLISHED' and original.get('source_commit') == source,
                    'GitHub publication did not succeed for this source')
            tag = original['git_tag']
            if original.get('prerelease') is True:
                record.update(status='SKIPPED', reason='PyPI stable releases only')
                output(enabled='false', upload='false')
                return record
        version = stable_version(tag)
        record.update(git_tag=tag, python_version=version)
        run(['git', 'fetch', '--no-tags', f'https://github.com/{repository}.git', f'refs/tags/{tag}'], root)
        identity = inspect_ref(root, 'FETCH_HEAD')
        require(identity.object_type == 'tag' and identity.source_commit == source,
                'published tag does not identify the requested source commit')
        record['tag_object_sha'] = identity.object_sha
        pin = root / 'release/baselines' / (tag + '.json')
        if pin.exists():
            pinned = read_release_pin(pin)
            verify_release_pin(root, pinned)
            require(pinned.tag_object_sha == identity.object_sha and pinned.source_commit == source,
                    'published release baseline differs')
        release = json.loads(run(['gh', 'api', f'repos/{repository}/releases/tags/{tag}'], root))
        with tempfile.TemporaryDirectory(prefix='mariamem-pypi-origin-') as temp:
            dest = Path(temp)
            prov_name = f'mariamem-{version}-provenance.json'
            run(['gh', 'release', 'download', tag, '--repo', repository, '--dir', dest,
                 '--pattern', 'SHA256SUMS', '--pattern', prov_name], root)
            sums = checksums((dest / 'SHA256SUMS').read_text())
            require(sums.get(prov_name) == digest(dest / prov_name), 'provenance hash differs')
            if original:
                require(original['assets'].get('SHA256SUMS') == digest(dest / 'SHA256SUMS'),
                        'publication SHA256SUMS hash differs')
            provenance = json.loads((dest / prov_name).read_text())
            expected = verify_origin(original, provenance, sums, release, source, tag, repository)
            record.update(assets=expected, github_status='PUBLISHED',
                          github_release_url=release['html_url'], checksums_sha256=digest(dest / 'SHA256SUMS'),
                          provenance_sha256=digest(dest / prov_name))
            record['stage'] = 'pypi-preflight'
            missing = missing_files(expected, pypi_files(version))
            uploads = directory / 'upload'
            require(not uploads.exists(), 'refuse stale upload directory')
            uploads.mkdir()
            for name in missing:
                run(['gh', 'release', 'download', tag, '--repo', repository, '--dir', uploads,
                     '--pattern', name], root)
                require(digest(uploads / name) == expected[name], 'downloaded wheel hash differs: ' + name)
            record.update(missing=missing, status='VERIFIED' if operation == 'verify' else 'UPLOAD_PENDING',
                          stage='prepared', pypi_status='MISSING' if missing else 'HASH_VERIFIED')
        output(enabled='true', upload=str(bool(missing)).lower(), version=version, source=source)
        return record
    except Exception as error:
        record.update(status='FAILED', error=str(error))
        raise
    finally:
        write(path, record)


def verify_uploaded(path):
    record = json.loads(path.read_text())
    try:
        require(record['schema'] == SCHEMA and record['operation'] == 'release'
                and record['status'] == 'UPLOAD_PENDING', 'invalid upload receipt state')
        record['stage'] = 'pypi-hashes'
        missing = missing_files(record['assets'], pypi_files(record['python_version']))
        require(not missing, 'PyPI files still missing: ' + ', '.join(missing))
        record.update(pypi_status='HASH_VERIFIED', status='SMOKE_PENDING', missing=[])
    except Exception as error:
        record.update(status='FAILED', error=str(error))
        raise
    finally:
        write(path, record)
    return record


def smoke_conditions(root):
    return {**SMOKE_ENV, 'runtime_python': platform.python_version(),
            'runtime_os': platform.mac_ver()[0], 'runtime_machine': platform.machine(),
            'runner_image': os.environ.get('ImageVersion', 'local'),
            'smoke_sha256': digest(root / 'scripts/pypi_smoke.py'),
            'driver_sha256': digest(root / 'scripts/pypi_release.py')}


def reusable(previous, current, conditions):
    keys = ('schema', 'source_commit', 'git_tag', 'python_version', 'assets', 'repository',
            'tag_object_sha', 'checksums_sha256', 'provenance_sha256')
    return (all(previous.get(k) == current.get(k) for k in keys)
            and previous.get('status') == 'COMPLETE'
            and previous.get('smoke', {}).get('conditions') == conditions
            and previous.get('smoke', {}).get('result') == 'PASS')


def find_smoke(root, record, conditions):
    """Reuse only authenticated same-tooling CI receipts; expiry simply requires another short smoke."""
    if not os.environ.get('GITHUB_ACTIONS'):
        return None
    api = GitHub(record['repository'], os.environ.get('GH_TOKEN'))
    runs = api.json('/actions/workflows/release-candidate-ready.yml/runs?event=workflow_dispatch&per_page=30')['workflow_runs']
    for info in runs:
        if (info.get('head_sha') != record['tooling_commit'] or info.get('status') != 'completed'
                or str(info['id']) == os.environ.get('GITHUB_RUN_ID')
                or info.get('path', '').split('@')[0] != WORKFLOW):
            continue
        prefix = 'pypi-smoke-' + record['source_commit'] + '-'
        found = api.json(f"/actions/runs/{info['id']}/artifacts?per_page=100")['artifacts']
        matches = sorted((a for a in found if a['name'].startswith(prefix) and not a['expired']),
                         key=lambda a: a['id'], reverse=True)
        for item in matches:
            with tempfile.TemporaryDirectory(prefix='mariamem-pypi-reuse-') as tmp:
                archive = Path(tmp) / 'receipt.zip'
                reference = api.artifact(info['id'], item['name'], record['source_commit'], archive)
                with zipfile.ZipFile(archive) as zipped:
                    require(zipped.namelist() == ['ci-pypi-publication.json'], 'unexpected smoke receipt archive')
                    previous = json.loads(zipped.read('ci-pypi-publication.json'))
                if reusable(previous, record, conditions):
                    return {**previous['smoke'], 'reused_from': reference}
    return None


def smoke(root, path):
    record = json.loads(path.read_text())
    try:
        require(record['status'] == 'SMOKE_PENDING' and record['pypi_status'] == 'HASH_VERIFIED',
                'smoke requires verified PyPI publication')
        require(stable_version(record['git_tag']) == record['python_version'], 'smoke version differs')
        require(not missing_files(record['assets'], pypi_files(record['python_version'])),
                'PyPI files missing before smoke')
        record['stage'] = 'pypi-smoke'
        conditions = smoke_conditions(root)
        previous = find_smoke(root, record, conditions)
        if previous:
            record['smoke'] = previous
        else:
            with tempfile.TemporaryDirectory(prefix='mariamem-pypi-smoke-') as tmp:
                work = Path(tmp)
                venv.EnvBuilder(with_pip=True).create(work / 'venv')
                python = work / 'venv/bin/python'
                base = [python, '-I', '-m', 'pip', '--isolated', '--disable-pip-version-check']
                run([*base, 'install', '--index-url', 'https://pypi.org/simple', SMOKE_ENV['pip'], SMOKE_ENV['driver']], work)
                report = work / 'pip.json'
                run([*base, 'install', '--index-url', 'https://pypi.org/simple', '--no-cache-dir',
                     '--only-binary', ':all:', '--no-deps', '--report', report,
                     'mariamem==' + record['python_version']], work)
                installed = json.loads(report.read_text())['install']
                require(len(installed) == 1 and installed[0]['metadata']['name'] == 'mariamem',
                        'pip installed unexpected distribution')
                download = installed[0]['download_info']
                name = download['url'].rsplit('/', 1)[-1]
                require(download['url'].startswith('https://files.pythonhosted.org/')
                        and record['assets'].get(name) == download['archive_info']['hashes']['sha256'],
                        'pip selected wheel/hash differs')
                result = json.loads(run([python, '-I', root / 'scripts/pypi_smoke.py',
                                         record['python_version']], work))
                require(result.get('result') == 'PASS', 'installed smoke did not pass')
                record['smoke'] = {'result': 'PASS', 'conditions': conditions, 'wheel': name,
                                   'sha256': record['assets'][name], 'observed': result}
        record.update(status='COMPLETE', stage='complete')
    except Exception as error:
        record.update(status='FAILED', error=str(error))
        raise
    finally:
        write(path, record)
    return record


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['prepare', 'verify-upload', 'smoke'])
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--directory', type=Path, default=Path('build/pypi'))
    parser.add_argument('--source')
    parser.add_argument('--tag')
    parser.add_argument('--operation', choices=['verify', 'release'], default='verify')
    parser.add_argument('--repository', default='masahitojp/mariamem')
    parser.add_argument('--publication', type=Path)
    args = parser.parse_args()
    path = args.directory / 'ci-pypi-publication.json'
    try:
        if args.command == 'prepare':
            record = prepare(args.root, args.directory, args.source, args.tag, args.operation,
                             args.repository, args.publication)
        elif args.command == 'verify-upload':
            record = verify_uploaded(path)
        else:
            record = smoke(args.root, path)
        print(json.dumps(record, indent=2))
    except Exception as error:
        print('PyPI stage stopped: ' + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
