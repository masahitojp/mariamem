#!/usr/bin/env python3
"""Three scoped native compatibility fixes, with immutable guest/binding review."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
GUEST_SOURCE='8dc2b113394630c5be7127100903a359f994db45'
HOST_SOURCE=GUEST_SOURCE
GUEST_SHA='6956ea97ff4ad5fa7cc1b9617ec39ac0197c402c0bfa869469ec62a9ad6c3719'
spec=importlib.util.spec_from_file_location('linux_probe',HERE.parent/'issue65-native-linux/probe.py')
base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
base.GUEST_SOURCE=GUEST_SOURCE;base.HOST_SOURCE=HOST_SOURCE;base.GUEST_SHA=GUEST_SHA
sys.path.insert(0,str(HERE.parent/'issue65-native-compat'))
from observations import analyze


def go_env(w):
    sys.path.insert(0,str(w/'worktree/scripts'))
    from build_feedback import go_environment
    stripped={k:v for k,v in os.environ.items() if k not in ('GOCACHE','GOPATH','GOMODCACHE')}
    return go_environment(dict(stripped,MARIAMEM_DEV_WORKSPACE=str(w),CGO_ENABLED='0',
                              GOTOOLCHAIN='go1.26.10',GOWORK='off',GOENV='off',
                              GOFLAGS='',GOEXPERIMENT='',GOMAXPROCS='2',GOGC='50'))


def endpoint_tests(w):
    subprocess.run(['go','test','-v','./internal/live'],cwd=w/'temp/host/product',env=go_env(w),check=True)


def tools(w,with_binding=True):
    base.identity(w/'worktree',HOST_SOURCE);base.guest_record(w)
    dest=w/'temp/tools';dest.mkdir(exist_ok=True)
    original=HERE.parent/'issue65-native-capture'
    names=['wire_test.go.txt','capture_test.go.txt','runtime_wire.go.txt',
           'runtime_capture_test.go.txt','runtime_tests.py']
    reference=json.loads((original/'evidence/host-build-final-control.json').read_text())
    for name in names:
        source=original/name
        if name in reference['prototype_templates_sha256'] and base.sha(source)!=reference['prototype_templates_sha256'][name]:
            raise ValueError('historical regression template changed: '+name)
        shutil.copy2(source,dest/name)
    shutil.copy2(HERE.parent/'issue65-native-live/live_test.go.txt',dest/'live_test.go.txt')
    shutil.copy2(HERE.parent/'issue65-native-compat/compat_test.go.txt',dest/'compat_test.go.txt')
    for name in ('assemble.py','main.go.txt','live.go.txt','endpoint.go.txt','endpoint_test.go.txt','guard_controls.py','fix_controls_test.go.txt'):
        shutil.copy2(HERE/name,dest/name)
    if with_binding:
        binding=json.loads((HERE/'binding/identity.json').read_text())
        if binding['guest_sha256']!=GUEST_SHA:raise ValueError('binding/guest pin differs')
        shutil.copy2(HERE/'binding/identity.json',dest/'binding.json')
    sys.path.insert(0,str(w/'worktree/scripts'))
    from build_generated_guest import download
    pin=json.loads((w/'worktree/release/generated-go-toolchain.json').read_text())['archives']['converter']
    download(pin,w/'worktree/build/downloads')
    return dest


def translate(w):
    dest=tools(w,with_binding=False)
    base.command(w,'translation',[sys.executable,dest/'assemble.py','--workspace',w,'--translate-only'],1200)


def runtime(w):
    if platform.system()!='Linux' or platform.machine()!='x86_64' or (os.environ.get('GITHUB_ACTIONS')=='true' and os.environ.get('RUNNER_ARCH')!='X64'):
        raise ValueError('CI acceptance requires native Linux x86_64')
    translate(w)
    execute(w)


def execute(w):
    dest=tools(w)
    base.command(w,'host-build',[sys.executable,dest/'assemble.py','--workspace',w,'--resume'],1500)
    host=json.loads((w/'evidence/host-build.json').read_text());binary=w/'temp/host/wire.test'
    original=HERE.parent/'issue65-native-capture'
    lifecycle={x['name'] for x in json.loads((original/'evidence/results.json').read_text())['cases']}
    live_cases={'TestNativeLiveDrainAndReset','TestNativeLiveCapacityBeforeDrain',
                'TestNativeLiveReplacementFailureRecovery','TestNativeLiveCancellationBeforeCommit',
                'TestNativeLiveCleanupDebtRecovery','TestNativeLiveCaptureDebtIsPermanent',
                'TestNativeLiveParentAndEndpointClose','TestNativeLiveInvalidRestoreNeverAdmits'}
    if len(lifecycle)!=14:raise ValueError('historical lifecycle scope changed')
    base.command(w,'lifecycle-suite',[binary,'-test.v','-test.run=^(TestCapture|TestProtocolPrepared|TestQueryDeadlineAndIsolation|TestPartialInputDeadline|TestSlowOutputControl|TestNativeLive)','-test.timeout=120s'],150)
    cases=base.cases_from_log((w/'evidence/lifecycle-suite.txt').read_text(),lifecycle|live_cases)
    base.save(w/'evidence/lifecycle-result.json',{'cases':[{'name':n,'elapsed':t,'result':'PASS'} for n,t in cases]})
    base.save(w/'evidence/result.json',{'result':'INCOMPLETE: compatibility execution pending'})
    code=0
    try:base.command(w,'compat-suite',[binary,'-test.v','-test.run=^TestCompat','-test.timeout=120s'],150)
    except subprocess.CalledProcessError as error:code=error.returncode
    result=analyze((w/'evidence/compat-suite.txt').read_text(),code)
    result.update({'guest_source_commit':GUEST_SOURCE,'host_source_commit':HOST_SOURCE,
                   'guest_sha256':GUEST_SHA,'binary_sha256':host['binary_sha256'],
                   'tooling_source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
                   'lifecycle_cases':22,'not_qualified':['full compatibility/profile','public APIs',
                   'whole controller relocation','race freedom','performance','release']})
    base.save(w/'evidence/compat-result.json',result)
    base.save(w/'evidence/result.json',{'result':'INCOMPLETE: supporting checks pending','compatibility':result['result']})
    base.command(w,'fix-controls',[binary,'-test.v','-test.run=^TestFixFoundRowsNegotiatedPerConnection$','-test.timeout=30s'],45)
    if '--- PASS: TestFixFoundRowsNegotiatedPerConnection ' not in (w/'evidence/fix-controls.txt').read_text():raise ValueError('FOUND_ROWS opt-in isolation control missing')
    base.command(w,'live-endpoint-tests',[sys.executable,Path(__file__),'endpoint-tests','--workspace',w],120)
    base.command(w,'runtime-boundary',[sys.executable,dest/'runtime_tests.py'],300)
    base.command(w,'binding-controls',[sys.executable,dest/'guard_controls.py'],120)
    # Guard tests remain explicitly tied to the installer/canonical source fixture.
    base.command(w,'pytest-install',[sys.executable,'-m','pip','install','--disable-pip-version-check','--no-compile','--target',w/'temp/pytest','pytest==8.4.2'],180)
    code='import sys;sys.path.insert(0,sys.argv[1]);import pytest;raise SystemExit(pytest.main(["-q","-p","no:cacheprovider","--basetemp",sys.argv[2],sys.argv[3]]))'
    base.command(w,'binding-tests',[sys.executable,'-c',code,w/'temp/pytest',w/'temp/pytest-run',w/'worktree/tests/test_thread_lifetime_binding.py'],120)
    if '21 passed' not in (w/'evidence/binding-tests.txt').read_text():raise ValueError('binding scope incomplete')
    product=w/'temp/host/product'
    for name,pin in host['source_inventory'].items():
        if base.sha(product/name)!=pin:raise ValueError('staged source changed: '+name)
    if base.sha(binary)!=host['binary_sha256']:raise ValueError('binary changed')
    base.identity(w/'worktree',HOST_SOURCE)
    base.save(w/'evidence/tooling.json',{'probe_sha256':base.sha(Path(__file__)),
              'binding_sha256':base.sha(HERE/'binding/identity.json'),
              'main_source_commit':'0c4e75dc2c21421a59d04661efd72a1f58efecaa'})
    result['supporting_checks']='PASS'
    base.save(w/'evidence/result.json',result)
    if not result['ready']:raise ValueError(result['result'])
def build(w):
    if platform.system() != 'Linux' or platform.machine() != 'aarch64' or os.geteuid() != 0:
        raise ValueError('guest build requires the native Linux arm64 root builder')
    repo = w/'worktree';base.safe_git(repo,Path(json.loads((w/'experiment.json').read_text())['repo']));base.identity(repo, GUEST_SOURCE)
    mounts=[]
    for name, destination in [('root', '/root'), ('work', '/work')]:
        target = Path(destination)
        if target.is_mount() or (destination == '/work' and target.exists() and any(target.iterdir())):
            raise ValueError('refuse an existing mount/nonempty work directory')
        source=w/'temp'/('builder-'+name);source.mkdir();target.mkdir(exist_ok=True)
        subprocess.run(['mount', '--bind', str(source), destination], check=True)
        mounts.append(destination);base.save(w/'mounts.json', mounts)
    # Root owns only these two known source directories for Git inspection.
    base.safe_git(repo, Path(json.loads((w/'experiment.json').read_text())['repo']))
    base.identity(repo, GUEST_SOURCE)
    os.environ['MARIAMEM_PHASE_TRACE']=str(w/'evidence/phases.jsonl')
    base.command(w,'guest-download',[sys.executable,Path(__file__),'downloads','--workspace',w],900)
    base.command(w, 'guest-build', [sys.executable, repo/'scripts/build_generated_guest.py', '--development-output', w/'temp/artifact'], 2700)
    base.guest_record(w)
    base.save(w/'evidence/builder.json', {'machine':platform.machine(), 'system':platform.system(), 'source_commit':GUEST_SOURCE, 'guest_sha256':GUEST_SHA, 'probe_sha256':base.sha(Path(__file__))})


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('stage',choices=['build','downloads','runtime','translate','execute','endpoint-tests','cleanup'])
    p.add_argument('--workspace',type=Path,required=True);a=p.parse_args();w=a.workspace.resolve()
    if not (w/'experiment.json').is_file():p.error('owned workspace required')
    if not re.fullmatch('[0-9a-f]{64}',GUEST_SHA):p.error('guest pin not reviewed')
    tooling_sha=subprocess.check_output(['git','-c','safe.directory='+str(ROOT),'rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    base.identity(ROOT,tooling_sha)
    os.environ['MARIAMEM_TOOLING_SOURCE_COMMIT']=tooling_sha
    base.save(w/'evidence'/('platform-'+a.stage+'.json'),{'uname':list(platform.uname()),
              'runner_arch':os.environ.get('RUNNER_ARCH'),'run_id':os.environ.get('GITHUB_RUN_ID'),
              'probe_sha256':base.sha(Path(__file__)),
              'tooling_source_commit':subprocess.check_output(['git','-c','safe.directory='+str(ROOT),'rev-parse','HEAD'],cwd=ROOT,text=True).strip()})
    try:{'build':build,'downloads':base.downloads,'runtime':runtime,'translate':translate,
         'execute':execute,'endpoint-tests':endpoint_tests,'cleanup':base.cleanup}[a.stage](w)
    except Exception as error:
        base.save(w/'evidence'/(a.stage+'-failure.json'),{'error':str(error),'probe_sha256':base.sha(Path(__file__))});raise

if __name__=='__main__':main()
