#!/usr/bin/env python3
"""Stage and verify additive 0.6.2 distribution; existing release bytes are immutable."""
import argparse
import hashlib
import json
import os
import platform
import time
import sys
import venv
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
import tempfile
import zipfile

from common import digest, extract
from ci_release_reuse import GitHub, WORKFLOW
from git_identity import inspect_ref, require_commit, read_release_pin, verify_release_pin
from pypi_release import checksums, missing_files, pypi_files, verify_origin
from published_assets import require

REPOSITORY = 'masahitojp/mariamem'
VERSION = '0.6.2'
PRODUCT_BASE = 'c053baeeeabdb30d07aff24932e55acae4306dce'
SCHEMA = 'additional-v062-v1'
TARGETS = {
    'linux-x86_64': 'manylinux_2_28_x86_64.musllinux_1_2_x86_64',
    'linux-aarch64': 'manylinux_2_28_aarch64.musllinux_1_2_aarch64',
    'windows-x86_64': 'win_amd64', 'windows-arm64': 'win_arm64',
}


def run(args, cwd=None):
    return subprocess.check_output([str(a) for a in args], cwd=cwd, text=True).strip()


def write(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + '\n')


def wheel_name(target):
    return f'mariamem-{VERSION}-py3-none-{TARGETS[target]}.whl'


def product_identity(tooling, source):
    require_commit(tooling, source)
    run(['git', 'merge-base', '--is-ancestor', PRODUCT_BASE, source], tooling)
    # This publication path cannot silently ship a later engine as 0.6.2.
    run(['git', 'diff', '--exit-code', PRODUCT_BASE, source, '--', 'internal', 'guest',
         'cmd', 'go.mod', 'go.sum', 'release/generated-go-inputs.json', 'python/mariamem'], tooling)
    pin = read_release_pin(tooling / 'release/baselines/v0.6.2.json')
    verify_release_pin(tooling, pin)
    return {'source_commit': source, 'original_source_commit': pin.source_commit,
            'tag_object_sha': pin.tag_object_sha, 'tooling_commit': inspect_ref(tooling, 'HEAD').source_commit}


def native_member(archive, name):
    relative = 'mariamem/_native/' + name
    allowed = {prefix + relative for prefix in ('', f'mariamem-{VERSION}.data/purelib/',
                                                f'mariamem-{VERSION}.data/platlib/')}
    found = [item for item in archive.namelist() if item in allowed]
    require(len(found) == 1, 'missing or ambiguous native member: ' + name)
    return archive.read(found[0])


def verify_cell(record, target, source, wheel_sha):
    require(record.get('source_commit') == source, 'acceptance source differs')
    require(record.get('target') == target, 'acceptance CPU differs')
    if target.startswith('windows-'):
        require(record.get('status') == 'PASS' and record.get('wheel_sha256') == wheel_sha,
                'Windows wheel acceptance differs')
        counts = record.get('cases')
        expected = 18
    else:
        require(record.get('result') == 'PASS' and record.get('sha256') == wheel_sha,
                'Linux wheel acceptance differs')
        counts = record.get('environment', {}).get('cases')
        expected = 2
    require(counts == dict(tests=expected, failures=0, errors=0, skipped=0),
            'acceptance cases failed, missing or skipped')


def collect(directory, output, source):
    """Require all four wheels, source-bound build receipts and six native cells."""
    directory, output = Path(directory), Path(output)
    output.mkdir(parents=True, exist_ok=True)
    records = {}
    for target in TARGETS:
        candidates = list(directory.rglob(wheel_name(target)))
        require(len(candidates) == 1, 'wheel missing or ambiguous: ' + target)
        wheel = candidates[0]
        wheel_sha = digest(wheel)
        with zipfile.ZipFile(wheel) as archive:
            manifest = json.loads(native_member(archive, 'manifest.json'))
            binary = 'mariamem-host.exe' if target.startswith('windows-') else 'mariamem-host'
            host_sha = hashlib.sha256(native_member(archive, binary)).hexdigest()
            require(manifest.get('platform') == target and manifest.get('package_version') == VERSION,
                    'wheel target/version differs')
            require(manifest.get('runtime_kind') == 'generated-go' and
                    manifest.get('sha256') == {binary: host_sha}, 'wheel host inventory differs')
        builds = []
        for receipt in directory.rglob('*.json'):
            value = json.loads(receipt.read_text())
            if (value.get('source_commit') == source and value.get('sha256') == wheel_sha
                    and value.get('manifest') == manifest and value.get('archive_checks_passed') is True):
                builds.append(value)
        require(len(builds) == 1, 'source-bound build receipt missing or ambiguous: ' + target)
        cells = {}
        for receipt in directory.rglob('*.json'):
            value = json.loads(receipt.read_text())
            if value.get('target') != target:
                continue
            verify_cell(value, target, source, wheel_sha)
            require(value.get('host_sha256') == host_sha, 'accepted host differs')
            cell = value.get('family', 'windows')
            require(cell not in cells, 'duplicate acceptance cell')
            cells[cell] = value
        expected = {'windows'} if target.startswith('windows-') else {'manylinux_2_28', 'musllinux_1_2'}
        require(set(cells) == expected, 'libc acceptance cell missing')
        shutil.copyfile(wheel, output / wheel.name)
        records[target] = {'wheel': wheel.name, 'wheel_sha256': wheel_sha,
                           'host_sha256': host_sha, 'manifest': manifest, 'acceptance': cells}
    return records


def verify_existing_assets(expected, actual):
    """Absent additions are resumable; every existing filename is immutable."""
    missing = []
    for name, sha in expected.items():
        require(Path(name).name == name and re.fullmatch('[0-9a-f]{64}', sha), 'invalid asset identity')
        if name not in actual:
            missing.append(name)
        else:
            require(actual[name] == sha, 'existing GitHub asset hash conflict: ' + name)
    return sorted(missing)


def release_info():
    value = json.loads(run(['gh', 'api', f'repos/{REPOSITORY}/releases/tags/v{VERSION}']))
    require(value.get('draft') is False and value.get('prerelease') is False,
            'original stable release unavailable')
    return value


def download(name, destination):
    run(['gh', 'release', 'download', 'v'+VERSION, '--repo', REPOSITORY,
         '--dir', destination, '--pattern', name])


def github_hashes(release):
    hashes = {}
    for asset in release['assets']:
        name = asset['name']
        require(name not in hashes and Path(name).name == name, 'ambiguous release asset')
        checksum = asset.get('digest', '')
        if re.fullmatch('sha256:[0-9a-f]{64}', checksum or ''):
            hashes[name] = checksum[7:]
        else:
            with tempfile.TemporaryDirectory() as temp:
                download(name, Path(temp))
                hashes[name] = digest(Path(temp)/name)
    return hashes


def assemble(tooling, product, inputs, output, source):
    identity = product_identity(tooling, source)
    require(inspect_ref(product, 'HEAD').source_commit == source, 'product checkout differs')
    require(not run(['git', 'status', '--porcelain', '--untracked-files=no'], product), 'dirty product checkout')
    targets = collect(inputs, output, source)
    release = release_info()
    with tempfile.TemporaryDirectory() as temp:
        temp = Path(temp)
        prov = f'mariamem-{VERSION}-provenance.json'
        download('SHA256SUMS', temp)
        download(prov, temp)
        sums = checksums((temp/'SHA256SUMS').read_text())
        require(sums[prov] == digest(temp/prov), 'original provenance hash differs')
        mac = verify_origin(None, json.loads((temp/prov).read_text()), sums, release,
                            identity['original_source_commit'], 'v'+VERSION, REPOSITORY)
        original_assets = {**sums, 'SHA256SUMS': digest(temp/'SHA256SUMS')}
        actual = github_hashes(release)
        require(not verify_existing_assets(original_assets, actual), 'original release assets missing')
        require(not missing_files(mac, pypi_files(VERSION)), 'original macOS PyPI wheel changed/missing')
        original_source = f'mariamem-{VERSION}-corresponding-source.tar.gz'
        download(original_source, temp)
        require(digest(temp/original_source) == sums[original_source], 'original corresponding source differs')
        overlay = temp/'product-source.tar.gz'
        with overlay.open('wb') as stream:
            subprocess.run(['git', 'archive', '--format=tar.gz', source], cwd=product, stdout=stream, check=True)
        # Keep the complete already-published dependency sources and the complete
        # current tracked tree. No local build folder is a source prerequisite.
        instructions = temp/'BUILD-SOURCE.txt'
        instructions.write_text('Extract product-source.tar.gz into an empty directory.\n'
            'Extract build/downloads dependency archives from the enclosed original corresponding-source archive\n'
            'into that directory. Use its scripts/generate_runtime.py and scripts/build_alpha.py;\n'
            'the tracked generated engine and OS adapters are the exact product source.\n'
            'Do not overlay old product files on the new tracked tree.\n')
        source_name = f'mariamem-{VERSION}-additional-{source}-source.tar.gz'
        with tarfile.open(output/source_name, 'w:gz') as archive:
            for name in (original_source, overlay.name, instructions.name):
                archive.add(temp/name, arcname=name)
        source_sha = digest(output/source_name)
    assets = {r['wheel']: r['wheel_sha256'] for r in targets.values()}
    assets[source_name] = source_sha
    record = dict(schema=SCHEMA, version=VERSION, **identity, targets=targets,
                  original_assets=original_assets, original_pypi=mac, assets=assets,
                  status='QUALIFIED', repository=REPOSITORY)
    name = f'mariamem-{VERSION}-additional-{source}-provenance.json'
    write(output/name, record)
    write(output/'candidate.json', {**record, 'provenance': name,
                                   'assets': {**assets, name: digest(output/name)}})
    return record


def prepare_upload(directory, source, operation):
    require(operation in ('verify', 'release'), 'invalid publication operation')
    record = json.loads((directory/'candidate.json').read_text())
    require(record.get('schema') == SCHEMA and record.get('status') == 'QUALIFIED'
            and record.get('source_commit') == source and record.get('version') == VERSION
            and record.get('repository') == REPOSITORY, 'invalid qualified candidate')
    require(set(record['targets']) == set(TARGETS), 'target missing')
    for target, target_record in record['targets'].items():
        require(target_record['wheel'] == wheel_name(target) and
                record['assets'].get(target_record['wheel']) == target_record['wheel_sha256'],
                'qualified target asset differs')
        expected_cells = {'windows'} if target.startswith('windows-') else {'manylinux_2_28','musllinux_1_2'}
        require(set(target_record['acceptance']) == expected_cells, 'qualified cell missing')
        for cell in target_record['acceptance'].values():
            verify_cell(cell,target,source,target_record['wheel_sha256'])
    for name, checksum in record['assets'].items():
        require(Path(name).name == name and digest(directory/name) == checksum, 'staged asset differs: '+name)
    require(set(record['original_assets']).isdisjoint(record['assets']), 'attempt to replace original asset')
    actual = github_hashes(release_info())
    require(not verify_existing_assets(record['original_assets'], actual), 'original release assets missing')
    missing = verify_existing_assets(record['assets'], actual)
    all_wheels = {r['wheel']:r['wheel_sha256'] for r in record['targets'].values()}
    require(not missing_files(record['original_pypi'], pypi_files(VERSION)), 'original PyPI asset differs')
    absent = missing_files(all_wheels, pypi_files(VERSION))
    if operation == 'release':
        for name in missing:
            # No --clobber: a race or conflicting existing asset must stop.
            run(['gh', 'release', 'upload', 'v'+VERSION, '--repo', REPOSITORY, directory/name])
        actual = github_hashes(release_info())
        require(not verify_existing_assets(record['assets'], actual), 'GitHub additions incomplete')
    upload = directory/'upload'
    require(not upload.exists(), 'stale PyPI upload directory')
    upload.mkdir()
    if operation == 'release':
        for name in absent:
            shutil.copyfile(directory/name, upload/name)
    write(directory/'transaction.json', dict(schema=SCHEMA, source_commit=source,
          operation=operation, assets=all_wheels, original_pypi=record['original_pypi'],
          missing=absent, status='VERIFIED' if operation=='verify' else 'UPLOAD_PENDING'))
    if os.environ.get('GITHUB_OUTPUT'):
        with open(os.environ['GITHUB_OUTPUT'], 'a') as stream:
            stream.write('upload='+str(bool(absent) and operation=='release').lower()+'\n')


def verify_uploaded(directory):
    record = json.loads((directory/'transaction.json').read_text())
    require(record.get('operation')=='release' and record.get('status')=='UPLOAD_PENDING', 'not a release transaction')
    missing = []
    for delay in (0,2,4,8,16,30):
        if delay:
            time.sleep(delay)
        missing = missing_files({**record['original_pypi'], **record['assets']}, pypi_files(VERSION))
        if not missing:
            break
    require(not missing, 'PyPI additions incomplete')
    record['status']='PUBLISHED'
    write(directory/'transaction.json',record)


def smoke(directory, target, family=None, previous_run=None):
    record = json.loads((directory/'candidate.json').read_text())
    expected = dict(record['original_pypi']) if target=='darwin-arm64' else {
        record['targets'][target]['wheel']:record['targets'][target]['wheel_sha256']}
    require(not missing_files(expected, pypi_files(VERSION)), 'public wheel hash differs')
    cell = target + ('-'+family if family else '')
    conditions = dict(script_sha256=digest(Path(__file__).with_name('pypi_smoke.py')),
                      driver='PyMySQL==1.2.3', python=sys.version,
                      os=platform.platform(), libc=platform.libc_ver(), cell=cell)
    # Use JSON-normalized values so tuple/list representation cannot alter reuse.
    conditions=json.loads(json.dumps(conditions))
    if previous_run:
        api=GitHub(REPOSITORY,os.environ.get('GH_TOKEN',''))
        name=f'additional-smoke-{target}-{previous_run}'
        entries=api.json(f'/actions/runs/{previous_run}/artifacts?per_page=100')['artifacts']
        available=[a for a in entries if a['name']==name and not a.get('expired')]
        if available:
            with tempfile.TemporaryDirectory() as previous:
                previous=Path(previous)
                api.artifact(previous_run,name,record['source_commit'],previous/'smoke.zip')
                extract(previous/'smoke.zip',previous/'unpacked')
                path=previous/'unpacked'/('smoke-'+cell+'.json')
                if path.exists():
                    old=json.loads(path.read_text())
                    if (old.get('source_commit')==record['source_commit'] and old.get('assets')==expected
                            and old.get('conditions')==conditions and old.get('result',{}).get('result')=='PASS'):
                        write(directory/('smoke-'+cell+'.json'),old)
                        return
    with tempfile.TemporaryDirectory() as temp:
        temp=Path(temp)
        venv.EnvBuilder(with_pip=True).create(temp/'venv')
        python=temp/'venv'/('Scripts/python.exe' if os.name=='nt' else 'bin/python')
        base=[python,'-I','-m','pip','--isolated','--disable-pip-version-check']
        run([*base,'download','--index-url','https://pypi.org/simple','--no-deps',
             '--only-binary=:all:','--dest',temp,'mariamem=='+VERSION])
        wheels=list(temp.glob('*.whl'))
        require(len(wheels)==1 and expected.get(wheels[0].name)==digest(wheels[0]), 'pip selected unexpected public wheel')
        run([*base,'install','--only-binary=:all:',wheels[0],'PyMySQL==1.2.3'])
        result=run([python,'-I',Path(__file__).with_name('pypi_smoke.py'),VERSION,target],temp)
        write(directory/('smoke-'+cell+'.json'),dict(source_commit=record['source_commit'],
              assets=expected,conditions=conditions,result=json.loads(result)))


def restore(tooling, source, run_id, directory):
    require(str(run_id).isdigit(), 'invalid qualification run')
    api=GitHub(REPOSITORY,os.environ.get('GH_TOKEN') or os.environ.get('GITHUB_TOKEN',''))
    info=api.json(f'/actions/runs/{run_id}')
    require(info.get('head_sha')==inspect_ref(tooling,'HEAD').source_commit,
            'reuse tooling/qualification conditions changed')
    archive=directory/'qualification.zip'
    api.artifact(run_id,'additional-v062-'+source,source,archive)
    extract(archive,directory)
    archive.unlink()
    record=json.loads((directory/'candidate.json').read_text())
    require(record.get('source_commit')==source and record.get('status')=='QUALIFIED', 'reuse source differs')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('command',choices=('identity','assemble','prepare','verify-upload','smoke','restore'))
    parser.add_argument('--source',required=True)
    parser.add_argument('--run')
    parser.add_argument('--tooling',type=Path,default=Path(__file__).resolve().parents[1])
    parser.add_argument('--product',type=Path)
    parser.add_argument('--inputs',type=Path)
    parser.add_argument('--directory',type=Path,required=True)
    parser.add_argument('--operation',choices=('verify','release'),default='verify')
    parser.add_argument('--target',choices=(*TARGETS,'darwin-arm64'))
    parser.add_argument('--family',choices=('manylinux_2_28','musllinux_1_2'))
    args=parser.parse_args()
    args.directory.mkdir(parents=True,exist_ok=True)
    if args.command=='identity':
        write(args.directory/'identity.json',product_identity(args.tooling,args.source))
    elif args.command=='assemble':
        assemble(args.tooling,args.product,args.inputs,args.directory,args.source)
    elif args.command=='prepare':
        product_identity(args.tooling,args.source)
        prepare_upload(args.directory,args.source,args.operation)
    elif args.command=='restore':
        restore(args.tooling,args.source,args.run,args.directory)
    elif args.command=='verify-upload':
        verify_uploaded(args.directory)
    else:
        require(args.target is not None,'smoke target required')
        smoke(args.directory,args.target,args.family,args.run)


if __name__=='__main__':
    main()
