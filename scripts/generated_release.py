"""Fail-closed v0.4 generated-Go artifact/source contract (no publication)."""
import gzip
import io
import json
from pathlib import Path
import re
import runpy
import shutil
import subprocess
import sys
import tarfile
import tempfile
import zipfile
from common import ROOT, digest, extract, fetch
from check_public import check, public_files
from runtime_sources import verify_runtime_sources
from native_target import DARWIN, UBUNTU, target_metadata, platform_fields
from distribution_licenses import inventory as license_inventory, paths as license_paths, source_inputs, verify_upstream_notices

CONTRACT = 'generated-go-v1'
PLATFORMS = (DARWIN, UBUNTU)
STEPS = {'go_default', 'go_snapshot_failure_lifecycle', 'gorm', 'installed_wheel', 'sqlalchemy'}


def require(condition, message):
    if not condition: raise ValueError(message)


def read(path): return json.loads(Path(path).read_text())


def write(path, value):
    path=Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,indent=2,sort_keys=True)+'\n')


def version(root): return runpy.run_path(str(root/'python/mariamem/_version.py'))


def source_name(value): return f'mariamem-{value}-corresponding-source.tar.gz'


def wheel_name(value, platform):
    return f"mariamem-{value}-py3-none-{target_metadata(platform)['wheel_platform']}.whl"


def expected_names(value):
    return {source_name(value),f'mariamem-{value}-provenance.json',*(wheel_name(value,p) for p in PLATFORMS)}


def source_inventory(root): return check(root)['files']


def notices(root, *, legacy=False):
    return {p.relative_to(root).as_posix():digest(p) for p in license_paths(root, legacy=legacy)}


def checkout(root, commit):
    require(re.fullmatch('[0-9a-f]{40}',commit) is not None,'full candidate SHA required')
    if (root/'.git').exists():
        actual=subprocess.check_output(['git','-c','safe.directory='+str(root),'rev-parse','HEAD'],cwd=root,text=True).strip()
        require(actual==commit,'checkout is not exact candidate')
        require(not subprocess.check_output(['git','-c','safe.directory='+str(root),'diff','--name-only','HEAD'],cwd=root,text=True).strip(),'candidate has tracked changes')


def verify_build(root, commit, directory=None):
    directory=directory or root/'build/generated-release'
    guest=read(directory/'guest.json'); regen=read(directory/'regeneration.json')
    pins=read(root/'release/generated-go-inputs.json')
    tools=read(root/'release/generated-go-toolchain.json')
    canonical=read(root/'release/generated-go-build.json')
    require(guest['contract']==regen['contract']==CONTRACT,'wrong build contract')
    require(guest['source_commit']==regen['source_commit']==commit,'build source differs')
    require(guest['guest_sha256']==regen['guest_sha256']==pins['guest_sha256']==canonical['guest_sha256'],'guest identity differs')
    require(digest(directory/'mariamem.wasm')==pins['guest_sha256'],'guest bytes differ')
    require((directory/'mariamem.wasm').stat().st_size==guest['guest_bytes']==canonical['guest_size'],'guest size differs')
    require(len(guest['repetitions'])>=2 and all(r==guest['repetitions'][0] for r in guest['repetitions']),'independent rebuild evidence missing/different')
    require(guest['repetitions'][0]=={'guest_sha256':pins['guest_sha256'],'linked_sha256':canonical['linked_guest_sha256']},'linked guest differs')
    prepared=guest['prepared_source']
    require(not prepared.get('experimental_patch') and 'experimental.patch' not in prepared['overlays'],'experimental guest patch')
    require(prepared['modified_files']==canonical['prepared_source']['modified_files'],'modified guest source differs')
    require(prepared['overlays']=={p.name:digest(p) for p in (root/'guest').iterdir() if p.is_file()},'source overlays differ')
    require(prepared['inputs_lock_sha256']==digest(root/'release/inputs.lock.json'),'guest input lock differs')
    tool=guest['toolchain']
    require(tool['pins_sha256']==digest(root/'release/generated-go-toolchain.json'),'toolchain pin identity differs')
    require(tool['archives_sha256']=={k:v['sha256'] for k,v in tools['archives'].items()},'toolchain archives differ')
    require(tool['host']=='linux-arm64' and tool['sysroot']['entries']>0,'wrong canonical build host/sysroot')
    require(regen['result']=='PASS' and regen['input_manifest_sha256']==digest(root/'release/generated-go-inputs.json'),'generation inputs differ')
    generated=root/'internal/generatedgo'
    require(regen['generated_inventory']=={p.relative_to(generated).as_posix():digest(p) for p in generated.rglob('*') if p.is_file()},'generated source inventory differs')
    require(regen['provenance_sha256']==digest(generated/'provenance.json'),'generated provenance differs')
    raw=regen['raw_translation']; expected=read(root/'release/generated-go-translation.json')
    # A generator executable is platform dependent. Its source/patch/output
    # hashes, not its native executable hash, are the portable comparison.
    for key in ('guest_sha256','converter_commit','converter_archive_sha256','patches_sha256','files_sha256'):
        require(raw[key]==expected[key],'converter identity/output differs: '+key)
    return {'guest':guest,'regeneration':regen}


def package_source(root, commit):
    checkout(root,commit); build=verify_build(root,commit)
    lock=read(root/'release/inputs.lock.json')
    inputs=source_inputs(root,lock)
    # Preserve repository/fallback attribution; the external Wasmer engine
    # source is not corresponding source for the generated-Go artifacts.
    for entry in inputs: fetch(entry['name'])
    verify_upstream_notices(root,lock)
    converter=read(root/'release/generated-go-toolchain.json')['archives']['converter']
    from build_generated_guest import download
    download(converter,root/'build/downloads')
    runtime_sources=verify_runtime_sources(root,lock)
    require({'licenses/wasm2go-MIT.txt','licenses/Go-BSD-3-Clause.txt','licenses/GPL-2.0-only.txt'}<=set(notices(root)),'required notices missing')
    with tarfile.open(root/'build/downloads'/converter['file']) as tar:
        licenses=[m for m in tar if m.name.count('/')==1 and m.name.endswith('/LICENSE')]
        require(len(licenses)==1 and tar.extractfile(licenses[0]).read()==(root/'licenses/wasm2go-MIT.txt').read_bytes(),'converter MIT notice differs')
    manifest={'contract':CONTRACT,'source_commit':commit,'python_version':version(root)['PYTHON_VERSION'],
              'files':source_inventory(root),'notices':notices(root),'source_inputs':inputs,
              'repository_notices':notices(root,legacy=True),'license_inventory':license_inventory(root),
              'converter_source':converter,'runtime_sources':runtime_sources,'build':build,
              'sysroot_rebuild_verified':False}
    value=manifest['python_version']; out=root/'build/release'; out.mkdir(parents=True,exist_ok=True)
    archive=out/source_name(value); prefix='mariamem-'+value
    with archive.open('wb') as raw, gzip.GzipFile(filename='',fileobj=raw,mode='wb',mtime=0) as gz:
        with tarfile.open(fileobj=gz,mode='w') as tar:
            def add(path,name):
                info=tar.gettarinfo(str(path),prefix+'/'+name)
                info.uid=info.gid=info.mtime=0; info.uname=info.gname=''
                with path.open('rb') as stream: tar.addfile(info,stream)
            for path in public_files(root): add(path,path.relative_to(root).as_posix())
            for entry in [*inputs,converter]: add(root/'build/downloads'/entry['file'],'build/downloads/'+entry['file'])
            content=(json.dumps(manifest,indent=2,sort_keys=True)+'\n').encode()
            info=tarfile.TarInfo(prefix+'/build/generated-source-manifest.json'); info.size=len(content)
            tar.addfile(info,io.BytesIO(content))
    write(out/'generated-source.json',{'file':archive.name,'sha256':digest(archive),'manifest':manifest})
    verify_source(root,commit)


def verify_source(root,commit):
    record=read(root/'build/release/generated-source.json'); archive=root/'build/release'/record['file']
    v=version(root)['PYTHON_VERSION']
    require(archive.name==source_name(v) and digest(archive)==record['sha256'],'corresponding source identity differs')
    manifest=record['manifest']
    require(manifest['contract']==CONTRACT and manifest['source_commit']==commit and manifest['python_version']==v,'source/version differs')
    require(manifest['files']==source_inventory(root) and manifest['notices']==notices(root),'source/notices differ')
    require(manifest['repository_notices']==notices(root,legacy=True) and
            manifest['license_inventory']==license_inventory(root),'repository/license inventory differs')
    require(manifest['build']==verify_build(root,commit),'source build evidence differs')
    lock=read(root/'release/inputs.lock.json')
    require(manifest['source_inputs']==source_inputs(root,lock),'source input set differs')
    require(manifest['converter_source']==read(root/'release/generated-go-toolchain.json')['archives']['converter'],'converter source pin differs')
    with tempfile.TemporaryDirectory(prefix='mariamem-generated-source-') as temporary:
        unpack=Path(temporary)/'unpack'; extract(archive,unpack)
        project=unpack/('mariamem-'+v)
        expected=set(manifest['files']) | {'build/generated-source-manifest.json'} | {
            'build/downloads/'+e['file'] for e in [*manifest['source_inputs'],manifest['converter_source']]}
        actual={p.relative_to(project).as_posix() for p in project.rglob('*') if p.is_file()}
        require(actual==expected,'unexpected/missing corresponding-source members')
        require({p.name for p in unpack.iterdir()}=={'mariamem-'+v},'unexpected source archive roots')
        require(source_inventory(project)==manifest['files'],'bundled public source differs')
        require(read(project/'build/generated-source-manifest.json')==manifest,'bundled source manifest differs')
        require(version(project)['PYTHON_VERSION']==v,'bundled version differs')
        for entry in [*manifest['source_inputs'],manifest['converter_source']]:
            require(digest(project/'build/downloads'/entry['file'])==entry['sha256'],'bundled upstream source differs: '+entry['file'])
        require(verify_runtime_sources(project,lock)==manifest['runtime_sources'],'runtime source/license coverage differs')
        verify_upstream_notices(project,lock)
        program="import runpy,urllib.request,sys\nsys.path.insert(0,'scripts')\ndef offline(*a,**k): raise RuntimeError('unexpected network')\nurllib.request.urlopen=offline\nrunpy.run_path('scripts/prepare_guest.py',run_name='__main__')"
        subprocess.run([sys.executable,'-c',program],cwd=project,check=True)
        prepared=read(project/'build/prepared-source.json')
        require(prepared==manifest['build']['guest']['prepared_source'],'offline preparation differs from actual build')
    return record


def verify_wheel(root, platform, commit=None):
    value=version(root)['PYTHON_VERSION']; record=read(root/'tests/evidence/alpha-wheel.json')
    require(re.fullmatch('[0-9a-f]{40}',record.get('source_commit','')) is not None,
            'wheel build source receipt missing')
    if commit is not None:
        require(record['source_commit']==commit,'wheel built from another source commit')
    require(record.get('source_files_sha256')==source_inventory(root),'wheel build source inventory differs')
    require('vcs.revision='+record['source_commit'] in record.get('host_buildinfo','') and
            'vcs.modified=false' in record.get('host_buildinfo',''),'wheel host build identity differs')
    path=root/record['wheel']
    require(path.name==wheel_name(value,platform) and digest(path)==record['sha256'],'wheel hash/version/target differs')
    manifest=record['manifest']
    require(manifest['runtime_kind']=='generated-go' and manifest['platform']==platform,'wheel is not generated-Go platform artifact')
    require(all(manifest.get(k)==v for k,v in platform_fields(target_metadata(platform,root)).items()),
            'wheel platform metadata differs')
    require(manifest['package_version']==value and manifest['guest_sha256']==read(root/'release/generated-go-inputs.json')['guest_sha256'],'wheel guest/version differs')
    require(manifest['public_release_ready'] is False and set(manifest['sha256'])=={'mariamem-host'},'wheel must be host-only, without embedded approval')
    with zipfile.ZipFile(path) as archive:
        names=archive.namelist(); require(len(names)==len(set(names)),'duplicate wheel entries')
        native={n.rsplit('/',1)[-1] for n in names if '/mariamem/_native/' in n and not n.endswith('/')}
        require(native=={'manifest.json','mariamem-host'},'unexpected wheel runtime assets')
        prefix='mariamem-'+value+'.dist-info/'
        require('Tag: py3-none-'+target_metadata(platform)['wheel_platform'] in archive.read(prefix+'WHEEL').decode(),'wheel tag differs')
        require('\nVersion: '+value+'\n' in '\n'+archive.read(prefix+'METADATA').decode(),'wheel metadata differs')
        packaged=next(n for n in names if n.endswith('/mariamem/_native/manifest.json'))
        require(json.loads(archive.read(packaged))==manifest,'wheel manifest differs')
        host=next(n for n in names if n.endswith('/mariamem/_native/mariamem-host'))
        import hashlib
        require(hashlib.sha256(archive.read(host)).hexdigest()==manifest['sha256']['mariamem-host'],'wheel host checksum differs')
        for name in notices(root):
            found=[n for n in names if '.dist-info/' in n and n.rsplit('/',1)[-1]==Path(name).name]
            require(found and all(archive.read(n)==(root/name).read_bytes() for n in found),'wheel notice missing/different: '+name)
        legacy_names=set(license_inventory(root)['legacy_notices'])
        require(not any(n.rsplit('/',1)[-1] in legacy_names for n in names),'legacy-only wheel notices')
    return path,record


def verify_acceptance(root, commit, platform, wheel_hash):
    report=read(root/'build/release/generated-acceptance.json')
    require(report['contract']==CONTRACT and report['result']=='PASS','external acceptance failed/missing')
    require((report['source_commit'],report['platform'],report['python_version'],report['wheel_sha256'])==
            (commit,platform,version(root)['PYTHON_VERSION'],wheel_hash),'acceptance identity differs')
    require(report['go_source_sha256']==source_inventory(root),'consumer source inventory differs')
    from generated_release_acceptance import harness_inventory
    require(report['harness_sha256']==harness_inventory(root),'acceptance harness differs')
    require(set(report['steps'])==STEPS and all(v=='PASS' for v in report['steps'].values()),'acceptance steps missing/failed')
    require(report['sqlalchemy_cases']==44 and report['gorm_cases']==32,'ORM acceptance counts differ')
    require(report['outside_checkout'] and not report['runtime_overrides'] and report['module_version']==version(root)['GIT_TAG'],'consumer boundary differs')
    require(report['go_version'].startswith('go version go1.26.8 '),'consumer Go toolchain differs')
    env=report['environment']
    if platform==DARWIN:
        require(env['system']=='Darwin' and env['architecture']=='arm64' and env['product_version'].startswith('15.'),'wrong macOS acceptance environment')
    else:
        require(env['system']=='Linux' and env['architecture']=='x86_64' and env['distribution']=='ubuntu' and env['version_id']=='24.04','wrong Ubuntu acceptance environment')
    installed=read(root/'tests/evidence/alpha.json')
    require(installed['passed'] and installed['wheel_sha256']==wheel_hash and installed['installed_files_match_wheel'] and installed['consumer_outside_repository'] and installed['native_overrides'] is False,'installed wheel evidence differs')
    require({r['name'] for r in installed['runs']}=={'serial','parallel','migration','failure-cleanup'},'installed-wheel suite incomplete')
    return digest(root/'build/release/generated-acceptance.json')


def guard(root, commit, platform):
    from check_version import check_release_docs
    check_release_docs(root)
    checkout(root,commit); build=verify_build(root,commit); source=verify_source(root,commit)
    wheel,record=verify_wheel(root,platform,commit)
    acceptance=verify_acceptance(root,commit,platform,record['sha256'])
    return {'version':3,'contract':CONTRACT,'result':'READY','source_commit':commit,'platform':platform,
            'git_tag':version(root)['GIT_TAG'],'python_version':version(root)['PYTHON_VERSION'],
            'assets':{source['file']:source['sha256'],wheel.name:record['sha256']},
            'guest_sha256':build['guest']['guest_sha256'],'build_evidence_sha256':digest(root/'build/generated-release/guest.json'),
            'regeneration_sha256':digest(root/'build/generated-release/regeneration.json'),
            'notices':notices(root),'acceptance_sha256':acceptance,'wheel_record':record}


def check_aggregate(root,commit):
    checkout(root,commit); records={}
    for platform in PLATFORMS:
        project=root/'build/platforms'/platform
        require(source_inventory(project)==source_inventory(root),'platform candidate source differs')
        records[platform]=guard(project,commit,platform)
    first=records[DARWIN]; assets={}
    for record in records.values():
        for key in ('source_commit','git_tag','python_version','guest_sha256','build_evidence_sha256','regeneration_sha256','notices'):
            require(record[key]==first[key],'common source/provenance differs: '+key)
        for name,value in record['assets'].items():
            require(name not in assets or assets[name]==value,'common source archive differs')
            assets[name]=value
    provenance={'contract':CONTRACT,'source_commit':commit,'guest_sha256':first['guest_sha256'],
                'generated_provenance_sha256':digest(root/'internal/generatedgo/provenance.json'),
                'inputs_sha256':digest(root/'release/generated-go-inputs.json'),
                'toolchain_sha256':digest(root/'release/generated-go-toolchain.json'),
                'notices':notices(root),'platforms':records,'assets':assets}
    import hashlib
    encoded=(json.dumps(provenance,indent=2,sort_keys=True)+'\n').encode()
    assets={**assets,f"mariamem-{first['python_version']}-provenance.json":hashlib.sha256(encoded).hexdigest()}
    require(set(assets)==expected_names(first['python_version']),'aggregate asset set differs')
    return {'version':3,'contract':CONTRACT,'result':'READY','source_commit':commit,
            'git_tag':first['git_tag'],'python_version':first['python_version'],'platforms':records,'assets':assets}


def stage(root,ready):
    staging=root/'build/release/publish'; staging.mkdir(parents=True,exist_ok=True)
    require(not set(p.name for p in staging.iterdir())-(set(ready['assets'])|{'SHA256SUMS'}),'unexpected staged assets')
    first=ready['platforms'][DARWIN]
    provenance={'contract':CONTRACT,'source_commit':ready['source_commit'],'guest_sha256':first['guest_sha256'],
                'generated_provenance_sha256':digest(root/'internal/generatedgo/provenance.json'),
                'inputs_sha256':digest(root/'release/generated-go-inputs.json'),
                'toolchain_sha256':digest(root/'release/generated-go-toolchain.json'),
                'notices':notices(root),'platforms':ready['platforms'],
                'assets':{k:v for k,v in ready['assets'].items() if not k.endswith('-provenance.json')}}
    write(staging/f"mariamem-{ready['python_version']}-provenance.json",provenance)
    for platform in PLATFORMS:
        project=root/'build/platforms'/platform
        wheel,_=verify_wheel(project,platform,ready['source_commit'])
        shutil.copyfile(wheel,staging/wheel.name)
    source=source_name(ready['python_version'])
    shutil.copyfile(root/'build/platforms'/DARWIN/'build/release'/source,staging/source)
    require({p.name:digest(p) for p in staging.iterdir() if p.name!='SHA256SUMS'}==ready['assets'],'staged artifact bytes differ')
    sums=''.join(f'{value}  {name}\n' for name,value in sorted(ready['assets'].items()))
    (staging/'SHA256SUMS').write_text(sums); (root/'build/release/SHA256SUMS').write_text(sums)
    write(root/'build/release/ci-ready.json',ready)
