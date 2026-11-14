import hashlib
import json
from pathlib import Path
import sys
import zipfile

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'scripts'))
from additional_v062 import collect, verify_existing_assets, TARGETS, wheel_name

SOURCE = 'a'*40


def write(path, value):
    path.write_text(json.dumps(value))


@pytest.fixture
def candidate(tmp_path):
    root = tmp_path/'inputs'
    root.mkdir()
    for target in TARGETS:
        folder = root/target
        folder.mkdir()
        binary = 'mariamem-host.exe' if target.startswith('windows-') else 'mariamem-host'
        body = target.encode()
        host_sha = hashlib.sha256(body).hexdigest()
        manifest = dict(platform=target,package_version='0.6.2',runtime_kind='generated-go',sha256={binary:host_sha})
        wheel = folder/wheel_name(target)
        with zipfile.ZipFile(wheel,'w') as archive:
            archive.writestr('mariamem/_native/manifest.json',json.dumps(manifest))
            archive.writestr('mariamem/_native/'+binary,body)
        sha = hashlib.sha256(wheel.read_bytes()).hexdigest()
        write(folder/'build.json',dict(source_commit=SOURCE,sha256=sha,manifest=manifest,archive_checks_passed=True))
        families = ['windows'] if target.startswith('windows-') else ['manylinux_2_28','musllinux_1_2']
        for family in families:
            count = dict(tests=18 if family=='windows' else 2,failures=0,errors=0,skipped=0)
            receipt = dict(source_commit=SOURCE,target=target,host_sha256=host_sha)
            if family=='windows':
                receipt.update(status='PASS',wheel_sha256=sha,cases=count)
            else:
                receipt.update(result='PASS',sha256=sha,family=family,environment=dict(cases=count))
            write(folder/(family+'.json'),receipt)
    return root


def test_all_native_cells_required(candidate,tmp_path):
    records = collect(candidate,tmp_path/'accepted',SOURCE)
    assert set(records)==set(TARGETS)
    assert sum(len(r['acceptance']) for r in records.values())==6


@pytest.mark.parametrize('change',['missing','skip','source','wheel','host','build','duplicate'])
def test_invalid_or_missing_cell_rejected(candidate,tmp_path,change):
    folder = candidate/'linux-aarch64'
    path = folder/'musllinux_1_2.json'
    receipt = json.loads(path.read_text())
    if change=='missing':
        path.unlink()
    elif change=='duplicate':
        write(folder/'duplicate.json',receipt)
    elif change=='build':
        (folder/'build.json').unlink()
    else:
        if change=='skip':receipt['environment']['cases']['skipped']=1
        if change=='source':receipt['source_commit']='b'*40
        if change=='wheel':receipt['sha256']='b'*64
        if change=='host':receipt['host_sha256']='b'*64
        write(path,receipt)
    with pytest.raises(ValueError):
        collect(candidate,tmp_path/'accepted',SOURCE)


def test_partial_upload_keeps_successful_bytes():
    expected={'one.whl':'a'*64,'two.whl':'b'*64}
    assert verify_existing_assets(expected,{'one.whl':'a'*64})==['two.whl']
    with pytest.raises(ValueError,match='conflict'):
        verify_existing_assets(expected,{'one.whl':'c'*64})


def test_verify_is_read_only_and_release_reuses_existing_files(candidate,tmp_path,monkeypatch):
    import additional_v062 as module
    directory=tmp_path/'bundle'
    targets=collect(candidate,directory,SOURCE)
    assets={r['wheel']:r['wheel_sha256'] for r in targets.values()}
    record=dict(schema=module.SCHEMA,status='QUALIFIED',source_commit=SOURCE,version='0.6.2',
                repository=module.REPOSITORY,targets=targets,assets=assets,
                original_assets={'old.whl':'a'*64},original_pypi={'old.whl':'a'*64})
    write(directory/'candidate.json',record)
    actual={'old.whl':'a'*64}
    one=next(iter(assets));actual[one]=assets[one]
    monkeypatch.setattr(module,'release_info',lambda:{})
    monkeypatch.setattr(module,'github_hashes',lambda _:dict(actual))
    monkeypatch.setattr(module,'pypi_files',lambda _: {'old.whl':dict(sha256='a'*64,yanked=False),one:dict(sha256=assets[one],yanked=False)})
    calls=[]
    def run(args,**kwargs):
        calls.append(args)
        path=Path(args[-1]);actual[path.name]=module.digest(path)
        return ''
    monkeypatch.setattr(module,'run',run)
    module.prepare_upload(directory,SOURCE,'verify')
    assert not calls and not list((directory/'upload').iterdir())
    (directory/'upload').rmdir()
    module.prepare_upload(directory,SOURCE,'release')
    assert len(calls)==3
    assert one not in {p.name for p in (directory/'upload').iterdir()}
    assert json.loads((directory/'transaction.json').read_text())['status']=='UPLOAD_PENDING'


def test_upload_verification_rejects_hash_conflict_without_retry(tmp_path,monkeypatch):
    import additional_v062 as module
    write(tmp_path/'transaction.json',dict(operation='release',status='UPLOAD_PENDING',
        original_pypi={},assets={'one.whl':'a'*64}))
    monkeypatch.setattr(module,'pypi_files',lambda _: {'one.whl':dict(sha256='b'*64,yanked=False)})
    monkeypatch.setattr(module.time,'sleep',lambda _: pytest.fail('hash conflict must not retry'))
    with pytest.raises(ValueError,match='conflict'):
        module.verify_uploaded(tmp_path)


def test_workflow_qualifies_all_targets_and_separates_read_only_verify():
    from workflow_model import parse
    root=Path(__file__).resolve().parents[1]
    workflow=parse((root/'.github/workflows/release-candidate-ready.yml').read_text())
    jobs=workflow['jobs']
    assert 'environment' not in jobs['additional_verify']
    assert jobs['additional_publication']['environment']=='pypi'
    assert jobs['additional_publication']['permissions']=={'contents':'write','actions':'read','id-token':'write'}
    assert "inputs.operation == 'release'" in jobs['additional_publication']['if']
    assert 'always()' not in jobs['additional_public_smoke']['if']
    for name in ('resolve','public_smoke_recovery','pypi_verify','pypi_publication'):
        assert '!inputs.additional_v062' in jobs[name]['if']
    build=parse((root/'.github/workflows/additional-v062-build.yml').read_text())['jobs']['native']
    assert {row['target'] for row in build['strategy']['matrix']['include']}==set(TARGETS)
    smoke=jobs['additional_public_smoke']
    assert {row['target'] for row in smoke['strategy']['matrix']['include']}==set(TARGETS)|{'darwin-arm64'}
    commands='\n'.join(step.get('run','') for step in smoke['steps'])
    assert 'for LIBC in manylinux_2_28 musllinux_1_2' in commands
