#!/usr/bin/env python3
"""Bounded hosted Linux repeat of the immutable 3D.1 development endpoint."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import urllib.error

GUEST_SOURCE = '5d9915d9940ff691249361aafb6ea39551f29a87'
HOST_SOURCE = 'ecd5d2b7ceff2085cac59f629c36d688007fc6bc'
GUEST_SHA = 'c4c72644cd3fa4605a936a7eafe8d622ab4f670e5b7bdbfbdf30f0a351e8dfcf'
MAC_RECORD_SHA256 = '2db62c25d6a173885fe9cd3b6d9583861e924d294c360ef10b2fbfd0b2d5399f'
HERE = Path(__file__).resolve().parent
TOOLS = HERE.parent/'issue65-native-capture'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2)+'\n')


def identity(repo, expected):
    result = json.loads(subprocess.check_output([sys.executable, str(repo/'scripts/git_identity.py'), '--root', str(repo), 'inspect', 'HEAD'], text=True))
    if result['object_type'] != 'commit' or result['source_commit'] != expected:
        raise ValueError('source commit identity differs')
    if subprocess.check_output(['git', 'status', '--porcelain'], cwd=repo).strip():
        raise ValueError('source checkout is dirty')
    return result


def command(w, label, args, timeout):
    e = w/'evidence';e.mkdir(exist_ok=True)
    save(e/(label+'-command.json'), {'argv': [str(x) for x in args], 'timeout_seconds': timeout})
    guard = [sys.executable, str(w/'worktree/scripts/experiment_disk.py'), '--work-dir', str(w), '--min-free-gib', '12', '--budget-gib', '12', '--timeout', str(timeout), '--']
    with (e/(label+'.txt')).open('w') as log:
        subprocess.run(guard+[str(x) for x in args], cwd=w, stdout=log, stderr=subprocess.STDOUT, check=True)


def guest_record(w):
    record = json.loads((w/'temp/artifact/guest.json').read_text())
    shutil.copy2(w/'temp/artifact/guest.json', w/'evidence/guest.json')
    if record['result'] != 'UNQUALIFIED' or record['source_commit'] != GUEST_SOURCE or record['guest_sha256'] != GUEST_SHA or sha(w/'temp/artifact/mariamem.wasm') != GUEST_SHA:
        shutil.copy2(w/'temp/artifact/mariamem.wasm',w/'evidence/unexpected-guest.wasm')
        raise ValueError('guest must exactly reproduce the observed 3D.1 artifact; never refresh pins here')
    return record


def build(w):
    if platform.system() != 'Linux' or platform.machine() != 'aarch64' or os.geteuid() != 0:
        raise ValueError('guest build requires the native Linux arm64 root builder')
    repo = w/'worktree';safe_git(repo,Path(json.loads((w/'experiment.json').read_text())['repo']));identity(repo, GUEST_SOURCE)
    mounts=[]
    for name, destination in [('root', '/root'), ('work', '/work')]:
        target = Path(destination)
        if target.is_mount() or (destination == '/work' and target.exists() and any(target.iterdir())):
            raise ValueError('refuse an existing mount/nonempty work directory')
        source=w/'temp'/('builder-'+name);source.mkdir();target.mkdir(exist_ok=True)
        subprocess.run(['mount', '--bind', str(source), destination], check=True)
        mounts.append(destination);save(w/'mounts.json', mounts)
    # Root owns only these two known source directories for Git inspection.
    safe_git(repo, Path(json.loads((w/'experiment.json').read_text())['repo']))
    identity(repo, GUEST_SOURCE)
    os.environ['MARIAMEM_PHASE_TRACE']=str(w/'evidence/phases.jsonl')
    command(w,'guest-download',[sys.executable,Path(__file__),'downloads','--workspace',w],900)
    command(w, 'guest-build', [sys.executable, repo/'scripts/build_generated_guest.py', '--development-output', w/'temp/artifact'], 2700)
    guest_record(w)
    save(w/'evidence/builder.json', {'machine':platform.machine(), 'system':platform.system(), 'source_commit':GUEST_SOURCE, 'guest_sha256':GUEST_SHA, 'probe_sha256':sha(Path(__file__))})


def downloads(w):
    repo=w/'worktree';identity(repo,GUEST_SOURCE);sys.path.insert(0,str(repo/'scripts'))
    from build_generated_guest import download
    from common import ROOT,fetch,LOCK
    from guest_input import descriptor
    def retry(call):
        for attempt in range(3):
            try:return call()
            except (urllib.error.URLError,TimeoutError,ConnectionError):
                if attempt==2:raise
    for name,pin in json.loads((ROOT/'release/generated-go-toolchain.json').read_text())['archives'].items():
        retry(lambda:download(pin,ROOT/'build/downloads'));print(name,flush=True)
    for name in [descriptor(ROOT,LOCK)['source_input'],'lite4mariadb','libmariadb','wolfssl','pcre2','libfmt']:
        retry(lambda:fetch(name));print(name,flush=True)


def cases_from_log(log,expected):
    cases=re.findall(r'^--- PASS: (\w+) \(([^)]+)\)',log,re.M)
    if {n for n,_ in cases}!=set(expected) or len(cases)!=len(expected) or not log.endswith('PASS\n') or re.search(r'^--- FAIL:',log,re.M):
        raise ValueError('missing/failed scoped Linux cases')
    return cases


def source_difference(actual,reference):
    def selected(values):return {n:v for n,v in values.items() if n.endswith(('.go','.s')) or n.endswith('/data.bin')}
    a,b=selected(actual),selected(reference)
    return len(b),sorted(n for n in a.keys()|b.keys() if a.get(n)!=b.get(n))


def safe_git(*paths):
    os.environ['GIT_CONFIG_COUNT']=str(len(paths))
    for i, path in enumerate(paths):
        os.environ[f'GIT_CONFIG_KEY_{i}']='safe.directory'
        os.environ[f'GIT_CONFIG_VALUE_{i}']=str(path)


def runtime(w):
    if platform.system() != 'Linux' or platform.machine() != 'x86_64' or (os.environ.get('GITHUB_ACTIONS')=='true' and os.environ.get('RUNNER_ARCH')!='X64'):
        raise ValueError('runtime acceptance requires native Linux x86_64; no emulated result')
    repo=w/'worktree';identity(repo, HOST_SOURCE);guest_record(w)
    tools=w/'temp/tools';tools.mkdir()
    for name in ['assemble.py','runtime_tests.py','guard_controls.py','main.go.txt','wire_test.go.txt','capture_test.go.txt','runtime_wire.go.txt','runtime_capture_test.go.txt']:
        shutil.copy2(TOOLS/name, tools/name)
    reference=TOOLS/'evidence/host-build-final-control.json'
    if sha(reference)!=MAC_RECORD_SHA256:raise ValueError('immutable Mac evidence pin changed')
    mac=json.loads(reference.read_text())
    for name, expected in mac['prototype_templates_sha256'].items():
        if sha(tools/name)!=expected:raise ValueError('Mac template pin differs: '+name)
    # Only fetch the pinned converter; the exact WASM arrived from the build job.
    sys.path.insert(0,str(repo/'scripts'))
    from build_generated_guest import download
    pin=json.loads((repo/'release/generated-go-toolchain.json').read_text())['archives']['converter']
    download(pin,repo/'build/downloads')
    command(w,'translation',[sys.executable,tools/'assemble.py','--workspace',w,'--translate-only'],1200)
    command(w,'host-build',[sys.executable,tools/'assemble.py','--workspace',w,'--resume'],1500)
    host=json.loads((w/'evidence/host-build.json').read_text())
    compared,different=source_difference(host['source_inventory'],mac['source_inventory'])
    save(w/'evidence/source-comparison.json',{'mac_reference_binary_sha256':mac['binary_sha256'],'compared_go_assembly_data_files':compared,'different_files':different})
    if different:raise ValueError('runtime inputs differ from the Mac source bundle')
    command(w,'suite',[w/'temp/host/wire.test','-test.v','-test.timeout=90s'],120)
    log=(w/'evidence/suite.txt').read_text()
    expected={x['name'] for x in json.loads((TOOLS/'evidence/results.json').read_text())['cases']}
    if len(expected)!=14:raise ValueError('Mac scope must remain14 cases')
    cases=cases_from_log(log,expected)
    command(w,'runtime-boundary',[sys.executable,tools/'runtime_tests.py'],300)
    if '--- PASS: TestWireCaptureWaitsForFailedWorkerPeer' not in (w/'evidence/runtime-boundary.txt').read_text():
        raise ValueError('controlled worker/peer test missing')
    command(w,'binding-controls',[sys.executable,tools/'guard_controls.py'],120)
    command(w,'pytest-install',[sys.executable,'-m','pip','install','--disable-pip-version-check','--no-compile','--target',w/'temp/pytest','pytest==8.4.2'],180)
    test_code='import sys;sys.path.insert(0,sys.argv[1]);import pytest;raise SystemExit(pytest.main(["-q","-p","no:cacheprovider","--basetemp",sys.argv[2],sys.argv[3]]))'
    command(w,'binding-tests',[sys.executable,'-c',test_code,w/'temp/pytest',w/'temp/pytest-run',repo/'tests/test_thread_lifetime_binding.py'],120)
    if not re.search(r'\b21 passed\b',(w/'evidence/binding-tests.txt').read_text()):raise ValueError('binding test scope did not complete21 cases')
    shutil.copy2(w/'temp/host/installation-inputs.json',w/'evidence/installation-inputs.json')
    shutil.copy2(w/'temp/host/translation/input-manifest.json',w/'evidence/translation-inputs.json')
    # Binary is disposable, so check all source and output hashes before cleanup.
    if sha(w/'temp/host/wire.test')!=host['binary_sha256']:raise ValueError('test binary changed')
    for n,v in host['source_inventory'].items():
        if sha(w/'temp/host/product'/n)!=v:raise ValueError('staged source changed: '+n)
    identity(repo,HOST_SOURCE)
    save(w/'evidence/result.json',{'result':'PASS for scoped native Linux experiment','system':platform.system(),'machine':platform.machine(),'uname':list(platform.uname()),'go_buildinfo':host['go_buildinfo'],'guest_source_commit':GUEST_SOURCE,'host_source_commit':HOST_SOURCE,'guest_sha256':GUEST_SHA,'binary_sha256':host['binary_sha256'],'cases':[{'name':n,'elapsed':t,'result':'PASS'} for n,t in cases],'worker_peer_boundary':'PASS','probe_sha256':sha(Path(__file__)),'not_qualified':['Live','public API integration','full protocol compatibility','performance','release']})


def converter_review(w):
    converters=list((w/'temp').glob('host/translation/converter/*'))
    if not converters:return
    repo=w/'worktree';sys.path.insert(0,str(repo/'scripts'))
    spec=importlib.util.spec_from_file_location('checked_converter',repo/'benchmarks/spikes/generated-go-integration/translate_guest.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    archive=repo/'build/downloads/wasm2go-upstream.tar.gz'
    if sha(archive)!=module.CONVERTER_SHA:raise ValueError('converter archive differs')
    check=w/'temp/converter-cleanup-reproduction';check.mkdir()
    with tarfile.open(archive) as tar:tar.extractall(check,filter='data')
    source=next(check.iterdir());subprocess.run(['git','init','-q'],cwd=source,check=True)
    for name in module.PATCHES:subprocess.run(['git','apply','--unidiff-zero',str(repo/'benchmarks/spikes/wasm2go'/name)],cwd=source,check=True)
    def inventory(root):return {str(p.relative_to(root)):sha(p) for p in root.rglob('*') if p.is_file() and '.git' not in p.relative_to(root).parts}
    expected=inventory(source);rows=[]
    for converter in converters:
        if inventory(converter)!=expected:raise ValueError('unexpected converter source; preserve before removing')
        if subprocess.run(['git','rev-parse','--verify','HEAD'],cwd=converter,capture_output=True).returncode==0 or subprocess.check_output(['git','for-each-ref'],cwd=converter).strip() or any(p.is_file() for p in (converter/'.git/objects').rglob('*')):
            raise ValueError('unexpected converter Git history')
        shutil.rmtree(converter/'.git');rows.append(str(converter.relative_to(w)))
    shutil.rmtree(source/'.git');save(w/'evidence/converter-cleanup.json',{'archive_sha256':module.CONVERTER_SHA,'exact_reproduced_files':len(expected),'empty_unborn_copies':rows})


def cleanup(w):
    if not (w/'experiment.json').exists():return
    record=json.loads((w/'experiment.json').read_text());repo=Path(record['repo'])
    mounts=json.loads((w/'mounts.json').read_text()) if (w/'mounts.json').exists() else []
    for target in reversed(mounts):
        if target not in ('/root','/work'):raise ValueError('unexpected owned mount')
        subprocess.run(['umount',target],check=True)
    safe_git(repo,w/'worktree')
    for source,name in [('temp/artifact/guest.json','guest.json'),('temp/host/translation/input-manifest.json','translation-inputs.json'),('temp/host/installation-inputs.json','installation-inputs.json')]:
        if (w/source).is_file():shutil.copy2(w/source,w/'evidence'/name)
    converter_review(w)
    save(w/'cleanup-policy.json',{'reproducible':{'temp':{'reason':'Generated guest/Go/SDK/cache; pinned source and unique observations exported to evidence','command':'Replay native Linux probe workflow','inputs':GUEST_SOURCE+' / '+HOST_SOURCE},'worktree/build':{'reason':'Locked archives and source preparation scratch','command':'Replay fixed guest development build','inputs':GUEST_SOURCE}},'keep':{'evidence':{'kind':'durable-evidence','reason':'Actual Linux/native builder observations, source/binary hashes, original errors and bounded test results'}}})
    helper=[sys.executable,str(repo/'scripts/experiment_workspace.py'),'--root',str(w.parent),'--repo',str(repo)]
    subprocess.run(helper+['finalize',w.name],check=True)
    dry=json.loads(subprocess.check_output(helper+['cleanup','--name',w.name,'--json'],text=True));save(w/'evidence/cleanup-dryrun.json',dry)
    if any(x['classification']!='DELETE' or not x['automatic'] for x in dry['decisions']):raise ValueError('cleanup needs source/result review')
    applied=json.loads(subprocess.check_output(helper+['cleanup','--name',w.name,'--apply','--json'],text=True));save(w/'evidence/cleanup.json',applied)
    if applied['cleanup_debt'] or (w/'temp').exists() or (w/'worktree').exists():raise ValueError('owned cleanup incomplete')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('stage',choices=['build','runtime','cleanup','downloads']);p.add_argument('--workspace',type=Path,required=True);a=p.parse_args();w=a.workspace.resolve()
    if w.is_symlink() or not (w/'experiment.json').is_file():p.error('owned workspace required')
    save(w/'evidence'/('platform-'+a.stage+'.json'),{'uname':list(platform.uname()),'python':platform.python_version(),'runner_arch':os.environ.get('RUNNER_ARCH'),'run_id':os.environ.get('GITHUB_RUN_ID'),'tooling_source_commit':subprocess.check_output(['git','-c','safe.directory='+str(HERE.parents[2]),'rev-parse','HEAD'],cwd=HERE.parents[2],text=True).strip(),'probe_sha256':sha(Path(__file__))})
    try:{'build':build,'runtime':runtime,'cleanup':cleanup,'downloads':downloads}[a.stage](w)
    except Exception as error:
        save(w/'evidence'/(a.stage+'-failure.json'),{'stage':a.stage,'error':str(error),'probe_sha256':sha(Path(__file__))});raise

if __name__=='__main__':main()
