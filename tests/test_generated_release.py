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


@pytest.mark.parametrize('mode', ['acceptance-only', 'guard-only'])
def test_generated_reuse_with_symlinked_system_temp(tmp_path, monkeypatch, mode):
    # Reproduce macOS /var -> /private/var on every CI platform, regardless
    # of TMPDIR overrides or pytest's own canonical temporary directory.
    physical = tmp_path.resolve() / 'physical-temp'
    physical.mkdir()
    alias = tmp_path.resolve() / 'system-temp'
    alias.symlink_to(physical, target_is_directory=True)
    monkeypatch.setattr(ci.tempfile, 'tempdir', str(alias))
    root = tmp_path.resolve() / 'checkout'
    root.mkdir()
    payload = b'guest fixture'
    handoff = io.BytesIO()
    with tarfile.open(fileobj=handoff, mode='w') as tar:
        member = tarfile.TarInfo('build/generated-release/guest.json')
        member.size = len(payload)
        tar.addfile(member, io.BytesIO(payload))
    import hashlib
    requests = []

    class FixtureGitHub:
        def __init__(self, *args): pass
        def artifact(self, run, name, commit, destination):
            requests.append((run, name))
            with zipfile.ZipFile(destination, 'w') as archive:
                if name.startswith('release-candidate-'):
                    archive.writestr('candidate-handoff.tar', handoff.getvalue())
                    archive.writestr('candidate-handoff.sha256',
                                     hashlib.sha256(handoff.getvalue()).hexdigest())
                else:
                    archive.writestr('build/release/generated-acceptance.json', '{}')
                    archive.writestr('tests/evidence/alpha.json', '{}')

    monkeypatch.setattr(ci, 'GitHub', FixtureGitHub)
    # Path restoration uses real ZIP/TAR validation; unrelated expensive
    # artifact/source/consumer verification is covered by the other tests.
    for name in ('verify_build', 'verify_source', 'verify_wheel'):
        monkeypatch.setattr(ci, name, lambda *args: None)
    guards = []
    monkeypatch.setattr(ci, 'guard', lambda *args: guards.append(args))
    ci.restore_platform(root, 'a'*40, release.DARWIN, mode,
                        candidate_run=123, evidence_run=456)
    assert (root/'build/generated-release/guest.json').read_bytes() == payload
    assert len(requests) == (2 if mode == 'guard-only' else 1)
    if mode == 'guard-only':
        assert (root/'build/release/generated-acceptance.json').read_text() == '{}'
        assert (root/'tests/evidence/alpha.json').read_text() == '{}'
        assert guards == [(root, 'a'*40, release.DARWIN)]
    assert not list(physical.iterdir())  # Owned scratch is removed on success.


def test_reuse_evidence_still_rejects_destination_symlink(tmp_path):
    root = tmp_path.resolve() / 'checkout'
    root.mkdir()
    outside = tmp_path.resolve() / 'outside'
    outside.mkdir()
    (root/'build').symlink_to(outside, target_is_directory=True)
    archive = tmp_path/'evidence.zip'
    with zipfile.ZipFile(archive, 'w') as z:
        z.writestr('build/release/generated-acceptance.json', '{}')
    with pytest.raises(ValueError, match='symlink'):
        ci.unzip(archive, root)
    assert not list(outside.iterdir())


def test_toolchain_recipe_exact_pins():
    pins=json.loads((ROOT/'release/generated-go-toolchain.json').read_text())
    assert pins['llvm']=='23.1.0' and pins['sysroot_variant']=='sysroot-eh'
    assert pins['sysroot_variants']==['sysroot-eh','sysroot-ehpic']
    assert pins['archives']['sysroot_pic']['sha256']=='54e00486bd0ab658009120c3980b967f96c95ec2ec10d23ba49261b9931927d0'
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
    monkeypatch.setattr(publisher,'check_aggregate',lambda *a:ready)
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
    release.write(root/'python/deployment_target.json', {'minimum_macos':15})
    for name in ('LICENSE','NOTICE','THIRD_PARTY_LICENSES'):(root/name).write_text(name)
    import shutil
    shutil.copytree(ROOT/'licenses',root/'licenses')
    for name in ('distribution-licenses.json','generated-license-evidence.json'):
        shutil.copyfile(ROOT/'release'/name,root/'release'/name)
    manifest={'version':1,'runtime_kind':'generated-go','platform':'darwin-arm64','package_version':'0.4.0',
              'minimum_macos':15,'guest_sha256':'c'*64,'public_release_ready':False,'sha256':{'mariamem-host':hashlib.sha256(b'host').hexdigest()}}
    wheel=root/'build/dist'/release.wheel_name('0.4.0','darwin-arm64');wheel.parent.mkdir(parents=True)
    def make(extra=None):
        with zipfile.ZipFile(wheel,'w') as z:
            z.writestr('mariamem/mariamem/_native/manifest.json',json.dumps(manifest))
            z.writestr('mariamem/mariamem/_native/mariamem-host',b'host')
            z.writestr('mariamem-0.4.0.dist-info/WHEEL','Tag: py3-none-macosx_15_0_arm64')
            z.writestr('mariamem-0.4.0.dist-info/METADATA','Version: 0.4.0\n')
            for name in release.notices(root):z.writestr('mariamem-0.4.0.dist-info/licenses/'+Path(name).name,(root/name).read_bytes())
            if extra:z.writestr(extra,b'old-runtime')
        release.write(root/'tests/evidence/alpha-wheel.json',{'wheel':wheel.relative_to(root).as_posix(),'sha256':digest(wheel),'manifest':manifest,
            'source_commit':'a'*40,'source_files_sha256':release.source_inventory(root),
            'host_buildinfo':'vcs.revision='+('a'*40)+'\nvcs.modified=false'})
    make();return root,wheel,manifest,make


def test_host_only_wheel_and_notice_bytes(host_wheel):
    root,wheel,manifest,make=host_wheel
    assert release.verify_wheel(root,'darwin-arm64')[0]==wheel
    make('mariamem/mariamem/_native/wasmer-headless')
    with pytest.raises(ValueError,match='assets'):release.verify_wheel(root,'darwin-arm64')
    make();(root/'NOTICE').write_text('changed')
    record=release.read(root/'tests/evidence/alpha-wheel.json')
    record['source_files_sha256']=release.source_inventory(root)
    release.write(root/'tests/evidence/alpha-wheel.json',record)
    with pytest.raises(ValueError,match='notice'):release.verify_wheel(root,'darwin-arm64')


def test_host_only_wheel_rejects_legacy_notices(host_wheel):
    root,wheel,manifest,make=host_wheel
    make('mariamem-0.4.0.dist-info/licenses/Wasmer-Singlepass-BUSL-1.1.txt')
    with pytest.raises(ValueError,match='legacy-only'):release.verify_wheel(root,'darwin-arm64')


@pytest.mark.parametrize('field,value,match',[('runtime_kind','wasmer','generated-Go'),('minimum_macos',14,'platform metadata'),
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
    runtime={'runtime_basis_commit':'b'*40,'release_source_commit':'a'*40,'run_id':7,'platforms':{}}
    records[release.DARWIN]['runtime_validation']=runtime
    with pytest.raises(ValueError,match='runtime evidence differs'):
        release.check_aggregate(tmp_path,'a'*40)
    records[release.UBUNTU]['runtime_validation']=runtime
    ready=release.check_aggregate(tmp_path,'a'*40)
    assert ready['platforms'][release.DARWIN]['runtime_validation']==runtime
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


def test_wheel_build_receipt_rejects_other_candidate(host_wheel):
    root,wheel,manifest,make=host_wheel
    with pytest.raises(ValueError,match='another source commit'):
        release.verify_wheel(root,'darwin-arm64','b'*40)
    record=release.read(root/'tests/evidence/alpha-wheel.json')
    record['host_buildinfo']='vcs.modified=true'
    release.write(root/'tests/evidence/alpha-wheel.json',record)
    with pytest.raises(ValueError,match='build identity'):
        release.verify_wheel(root,'darwin-arm64','a'*40)


def test_newer_local_macos_is_not_minimum_platform_release_evidence(tmp_path,monkeypatch):
    import generated_release_acceptance as acceptance
    version_file=tmp_path/'python/mariamem/_version.py';version_file.parent.mkdir(parents=True)
    version_file.write_text('PYTHON_VERSION="0.4.0"\nGIT_TAG="v0.4.0"\n')
    monkeypatch.setattr(release,'source_inventory',lambda *a:{})
    monkeypatch.setattr(acceptance,'harness_inventory',lambda *a:{})
    report={'contract':release.CONTRACT,'result':'PASS','source_commit':'a'*40,
            'platform':'darwin-arm64','python_version':'0.4.0','wheel_sha256':'b'*64,
            'go_source_sha256':{},'harness_sha256':{},'steps':{k:'PASS' for k in release.STEPS},
            'sqlalchemy_cases':44,'gorm_cases':32,'outside_checkout':True,'runtime_overrides':False,
            'module_version':'v0.4.0','go_version':'go version go1.26.8 darwin/arm64',
            'environment':{'system':'Darwin','architecture':'arm64','product_version':'27.0.1'}}
    release.write(tmp_path/'build/release/generated-acceptance.json',report)
    with pytest.raises(ValueError,match='macOS acceptance environment'):
        release.verify_acceptance(tmp_path,'a'*40,'darwin-arm64','b'*64)


@pytest.mark.parametrize('mode', ['candidate','published'])
def test_artifact_consumers_stay_full_but_public_smoke_is_identity_bound(tmp_path,monkeypatch,mode):
    import generated_release_acceptance as acceptance
    from consumer_acceptance import MODULE
    from types import SimpleNamespace
    root=tmp_path/'source'; root.mkdir()
    for name in ('tests/godefault/default_test.go','tests/consumer/gorm/go.mod',
                 'tests/consumer/test_generated_platform.py','tests/consumer/test_sqlalchemy_dogfood.py',
                 'scripts/guest_smoke/main.go'):
        file=root/name; file.parent.mkdir(parents=True,exist_ok=True); file.write_text('fixture')
    wheel=root/'accepted.whl'; wheel.write_bytes(b'accepted')
    record={'sha256':digest(wheel),'manifest':{'package_version':'0.4.5'}}
    metadata={'GIT_TAG':'v0.4.5','PYTHON_VERSION':'0.4.5'}
    proof={'status':'PUBLISHED','source_commit':'a'*40,'git_tag':'v0.4.5',
           'platforms':{'darwin-arm64':{'result':'READY','wheel_record':record}}}
    for name,value in [('checkout',lambda *a:None),('verify_wheel',lambda *a:(wheel,record)),
                       ('version',lambda *a:metadata),('source_inventory',lambda *a:{}),
                       ('harness_inventory',lambda *a:{}),('environment',lambda *a:{}),
                       ('prepare_proxy',lambda *a:root)]:
        monkeypatch.setattr(acceptance,name,value)
    resolved={'Path':MODULE,'Version':'v0.4.5','Sum':'h1:fixture','Origin':{'Hash':'a'*40},'Dir':str(root)}
    monkeypatch.setattr(acceptance.subprocess,'check_output',lambda argv,**kw:
                        'go version go1.26.8 darwin/arm64' if argv[:2]==['go','version'] else json.dumps(resolved))
    identity=[]
    monkeypatch.setattr(acceptance,'verify_module_files',lambda *a:identity.append(a) or {'library':'hash'})
    commands=[]
    def execute(argv,**kwargs):
        commands.append(argv)
        env=kwargs['env']
        if 'DOGFOOD_EVIDENCE' in env and argv[0]=='go':
            Path(env['DOGFOOD_EVIDENCE']).write_text(json.dumps({'passed':True,'cases':list(range(8))}))
        if '--junitxml' in argv:
            Path(argv[argv.index('--junitxml')+1]).write_text('<testsuites><testsuite tests="11" failures="0" errors="0" skipped="0"/></testsuites>')
        if '--public-smoke' in argv:
            release.write(root/'tests/evidence/public-wheel-smoke.json',{'passed':True,'installed_files_match_wheel':True,
                          'wheel_sha256':record['sha256'],'version':'0.4.5'})
        return SimpleNamespace(returncode=0)
    monkeypatch.setattr(acceptance.subprocess,'run',execute)
    output=tmp_path/'result.json'
    if mode=='published':
        with pytest.raises(ValueError,match='accepted artifact proof'):
            acceptance.accept(root,'a'*40,'darwin-arm64',output,mode=mode)
        assert not commands and not output.exists()
    report=acceptance.accept(root,'a'*40,'darwin-arm64',output,mode=mode,publication=proof)
    assert report['result']=='PASS'
    if mode=='candidate':
        assert report['gorm_cases']==32 and report['sqlalchemy_cases']==44
        assert set(report['steps'])==release.STEPS
        assert sum('DOGFOOD' not in str(c) and '--junitxml' in c for c in commands)==4
        assert not identity and not any('--public-smoke' in c for c in commands)
    else:
        assert len(identity)==1
        assert set(report['steps'])=={'public_go_smoke','public_wheel_smoke'}
        assert not any('pytest' in c or '--junitxml' in c for c in commands)
        assert ['go','run','.'] in commands
        assert any('--public-smoke' in c for c in commands)
