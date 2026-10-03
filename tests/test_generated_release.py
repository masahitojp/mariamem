"""Current release contract: fail closed on wrong bytes, sources and boundaries."""
import io
import json
from pathlib import Path
import sys
import tarfile
import zipfile
import pytest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
import generated_release as release
import release_generated_ci as ci
from common import digest


def test_minimum_artifact_set():
    names=release.expected_names('0.4.0')
    assert names=={'mariamem-0.4.0-py3-none-macosx_15_0_arm64.whl',
                   'mariamem-0.4.0-py3-none-linux_x86_64.whl',
                   'mariamem-0.4.0-corresponding-source.tar.gz','mariamem-0.4.0-provenance.json'}
    assert not any('native' in n or 'wasmu' in n for n in names)


@pytest.mark.parametrize('name',['../outside','/outside','build/guest-aot/mariamem.wasmu',
                                'build/dist/../../source.go','build/dist/other.whl','build/generated-release/guest.exe'])
def test_frozen_path_rejection(name):
    with pytest.raises(ValueError): ci.allowed(name)


def test_handoff_hash_special_duplicate_and_overwrite(tmp_path):
    archive=tmp_path/'candidate.tar'; root=tmp_path/'checkout';root.mkdir()
    def make(names):
        with tarfile.open(archive,'w') as tar:
            for name,kind in names:
                m=tarfile.TarInfo(name);m.type=kind
                if kind==tarfile.REGTYPE: m.size=1;tar.addfile(m,io.BytesIO(b'x'))
                else: m.linkname='outside';tar.addfile(m)
    make([('build/generated-release/guest.json',tarfile.REGTYPE)])
    with pytest.raises(ValueError,match='SHA256'): ci.restore_handoff(archive,'0'*64,root)
    make([('build/generated-release/guest.json',tarfile.SYMTYPE)])
    with pytest.raises(ValueError,match='special'): ci.restore_handoff(archive,digest(archive),root)
    make([('build/generated-release/guest.json',tarfile.REGTYPE)]*2)
    with pytest.raises(ValueError,match='duplicate'): ci.restore_handoff(archive,digest(archive),root)
    make([('build/generated-release/guest.json',tarfile.REGTYPE)])
    ci.restore_handoff(archive,digest(archive),root)
    with pytest.raises(ValueError,match='overwriting'): ci.restore_handoff(archive,digest(archive),root)


def test_evidence_zip_rejects_unknown_and_duplicates(tmp_path):
    archive=tmp_path/'evidence.zip'
    with zipfile.ZipFile(archive,'w') as z:z.writestr('untrusted.json','{}')
    with pytest.raises(ValueError,match='unexpected'):ci.unzip(archive,tmp_path/'dest')
    with zipfile.ZipFile(archive,'w') as z:
        z.writestr('build/release/generated-acceptance.json','{}')
        with pytest.warns(UserWarning): z.writestr('build/release/generated-acceptance.json','{}')
    with pytest.raises(ValueError,match='duplicate'):ci.unzip(archive,tmp_path/'dest')


def test_toolchain_recipe_exact_pins():
    pins=json.loads((ROOT/'release/generated-go-toolchain.json').read_text())
    assert pins['llvm']=='23.1.0' and pins['sysroot_variant']=='sysroot-eh'
    assert pins['archives']['sysroot']['sha256']=='8c54240afabda1106c19f284bdfff77f29932caa55f82756f87d01f69ffd50f4'
    assert all(len(v['sha256'])==64 and v['url'].startswith('https://') for v in pins['archives'].values())


def test_missing_platform_never_ready(tmp_path):
    with pytest.raises((ValueError,FileNotFoundError)):release.check_aggregate(tmp_path,'a'*40)


def test_new_publisher_contract_dry_run(tmp_path,monkeypatch):
    import ci_release_publish as publisher
    version='0.4.0';tag='v0.4.0';sha='a'*40
    root=tmp_path; staging=root/'build/release/publish';staging.mkdir(parents=True)
    version_path=root/'python/mariamem/_version.py';version_path.parent.mkdir(parents=True)
    version_path.write_text(f'PYTHON_VERSION="{version}"\nGIT_TAG="{tag}"\nSTAGE=""\nSERIAL=0\n')
    notes=root/'release/NOTES-v0.4.0.md';notes.parent.mkdir();notes.write_text('# '+tag)
    assets={}
    for name in release.expected_names(version):
        (staging/name).write_text(name);assets[name]=digest(staging/name)
    ready={'version':3,'contract':release.CONTRACT,'result':'READY','source_commit':sha,
           'git_tag':tag,'python_version':version,'platforms':{p:{} for p in release.PLATFORMS},'assets':assets}
    release.write(root/'build/release/ci-ready.json',ready)
    (root/'build/release/SHA256SUMS').write_text(''.join(f'{v}  {k}\n' for k,v in assets.items()))
    monkeypatch.setattr(release,'check_aggregate',lambda *a:ready)
    calls=[]
    def command(args,cwd):
        calls.append(args)
        if args[:3]==['git','rev-parse','HEAD']:return sha
        if args[:2]==['git','ls-files']:return str(notes.relative_to(root))
        if args[:3]==['gh','api','repos/masahitojp/mariamem/commits/'+sha]:return json.dumps({'sha':sha})
        return ''
    monkeypatch.setattr(publisher,'command',command)
    monkeypatch.setattr(publisher,'release_exists',lambda *a:False)
    result=publisher.publish(root,sha,'masahitojp/mariamem',dry_run=True)
    assert result['status']=='DRY_RUN' and result['contract']==release.CONTRACT
    assert not any(a[:2]==['git','push'] or a[:3]==['git','tag','-a'] or
                   a[:2]==['gh','release'] for a in calls)
    (staging/next(iter(assets))).write_text('corrupt')
    with pytest.raises(ValueError,match='hash'): publisher.publish(root,sha,'masahitojp/mariamem',dry_run=True)


@pytest.fixture
def host_wheel(tmp_path):
    import hashlib
    root=tmp_path; release.write(root/'release/generated-go-inputs.json',{'guest_sha256':'c'*64})
    path=root/'python/mariamem/_version.py';path.parent.mkdir(parents=True)
    path.write_text('PYTHON_VERSION="0.4.0"\nGIT_TAG="v0.4.0"\n')
    for name in ('LICENSE','NOTICE','THIRD_PARTY_LICENSES'):(root/name).write_text(name)
    (root/'licenses').mkdir();(root/'licenses/wasm2go-MIT.txt').write_text('MIT')
    manifest={'version':1,'runtime_kind':'generated-go','platform':'darwin-arm64','package_version':'0.4.0',
              'guest_sha256':'c'*64,'public_release_ready':False,'sha256':{'mariamem-host':hashlib.sha256(b'host').hexdigest()}}
    wheel=root/'build/dist'/release.wheel_name('0.4.0','darwin-arm64');wheel.parent.mkdir(parents=True)
    def make(extra=None):
        with zipfile.ZipFile(wheel,'w') as z:
            z.writestr('mariamem/mariamem/_native/manifest.json',json.dumps(manifest))
            z.writestr('mariamem/mariamem/_native/mariamem-host',b'host')
            z.writestr('mariamem-0.4.0.dist-info/WHEEL','Tag: py3-none-macosx_15_0_arm64')
            z.writestr('mariamem-0.4.0.dist-info/METADATA','Version: 0.4.0\n')
            for name in release.notices(root):z.writestr('mariamem-0.4.0.dist-info/licenses/'+Path(name).name,(root/name).read_bytes())
            if extra:z.writestr(extra,b'old-runtime')
        release.write(root/'tests/evidence/alpha-wheel.json',{'wheel':wheel.relative_to(root).as_posix(),'sha256':digest(wheel),'manifest':manifest})
    make();return root,wheel,manifest,make


def test_host_only_wheel_and_notice_bytes(host_wheel):
    root,wheel,manifest,make=host_wheel
    assert release.verify_wheel(root,'darwin-arm64')[0]==wheel
    make('mariamem/mariamem/_native/wasmer-headless')
    with pytest.raises(ValueError,match='assets'):release.verify_wheel(root,'darwin-arm64')
    make();(root/'NOTICE').write_text('changed')
    with pytest.raises(ValueError,match='notice'):release.verify_wheel(root,'darwin-arm64')


@pytest.mark.parametrize('field,value,match',[('runtime_kind','wasmer','generated-Go'),
 ('guest_sha256','d'*64,'guest'),('package_version','0.3.0','guest'),('public_release_ready',True,'approval')])
def test_wheel_identity_rejection(host_wheel,field,value,match):
    root,wheel,manifest,make=host_wheel;manifest[field]=value;make()
    with pytest.raises(ValueError,match=match):release.verify_wheel(root,'darwin-arm64')


def test_aggregate_common_source_and_provenance_must_match(tmp_path,monkeypatch):
    records={p:{'version':3,'contract':release.CONTRACT,'result':'READY','source_commit':'a'*40,
             'platform':p,'git_tag':'v0.4.0','python_version':'0.4.0','guest_sha256':'b'*64,
             'build_evidence_sha256':'c'*64,'regeneration_sha256':'d'*64,'notices':{},
             'assets':{release.source_name('0.4.0'):'e'*64,release.wheel_name('0.4.0',p):'f'*64}}
             for p in release.PLATFORMS}
    monkeypatch.setattr(release,'checkout',lambda *a:None)
    monkeypatch.setattr(release,'source_inventory',lambda *a:{'same':'source'})
    monkeypatch.setattr(release,'guard',lambda root,commit,platform:records[platform])
    (tmp_path/'internal/generatedgo').mkdir(parents=True)
    (tmp_path/'internal/generatedgo/provenance.json').write_text('{}')
    (tmp_path/'release').mkdir()
    for name in ('generated-go-inputs.json','generated-go-toolchain.json'):(tmp_path/'release'/name).write_text('{}')
    monkeypatch.setattr(release,'notices',lambda *a:{})
    ready=release.check_aggregate(tmp_path,'a'*40)
    assert ready['contract']==release.CONTRACT and set(ready['assets'])==release.expected_names('0.4.0')
    records[release.UBUNTU]['assets'][release.source_name('0.4.0')]='0'*64
    with pytest.raises(ValueError,match='archive differs'):release.check_aggregate(tmp_path,'a'*40)
    records[release.UBUNTU]['assets'][release.source_name('0.4.0')]='e'*64
    records[release.UBUNTU]['guest_sha256']='0'*64
    with pytest.raises(ValueError,match='provenance differs'):release.check_aggregate(tmp_path,'a'*40)


def test_normal_release_check_routes_generated_guard(monkeypatch):
    import verify
    commands=[]
    monkeypatch.setattr(verify, 'run', lambda command, **kwargs: commands.append(command))
    monkeypatch.setattr(sys, 'argv', ['verify.py','release-check','--ci-candidate-sha','a'*40,
                                    '--platform','darwin-arm64'])
    verify.main()
    assert commands[0][1:]==['scripts/release_generated_ci.py','guard','--candidate-sha','a'*40,
                            '--platform','darwin-arm64']


def test_guard_failure_replaces_old_ready(tmp_path,monkeypatch):
    release.write(tmp_path/'build/release/ci-ready.json',{'result':'READY'})
    monkeypatch.setattr(ci,'check_aggregate',lambda *a: (_ for _ in ()).throw(ValueError('missing platform')))
    monkeypatch.setattr(sys,'argv',['release_generated_ci.py','guard','--root',str(tmp_path),
                                    '--candidate-sha','a'*40])
    assert ci.main()==1
    record=release.read(tmp_path/'build/release/ci-ready.json')
    assert record['result']=='NOT READY' and record['error']=='missing platform'
