#!/usr/bin/env python3
"""Native G2 prepared repair, with new guest/binding and unchanged observation oracles."""
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
OLD_FIX=HERE.parent/'issue65-compat-fixes'
LIMITS_FIXTURE_SHA256='808fe47bd4ee69f8e80b9702170429b1cfe56d2cbd83d3721c184bdb3cc16549'
GUEST_SOURCE='b2d9a2a6e37ed7dd3149b6c85f8908d8d11df17a'
HOST_SOURCE=GUEST_SOURCE
GUEST_SHA='a75416e3b677b83fb9fca4d213dd67ec32c1e1732939d275866183828aa868ee'
SOURCE_REFERENCE_SHA256='260d3983e797791bb84e61380bde57a07d6f3a65c3607d4790bc794cf9ef5562'
spec=importlib.util.spec_from_file_location('linux_probe',HERE.parent/'issue65-native-linux/probe.py')
base=importlib.util.module_from_spec(spec);spec.loader.exec_module(base)
base.GUEST_SOURCE=GUEST_SOURCE;base.HOST_SOURCE=HOST_SOURCE;base.GUEST_SHA=GUEST_SHA
sys.path.insert(0,str(HERE.parent/'issue65-native-compat'))
from observations import analyze
limit_spec=importlib.util.spec_from_file_location('policy_limit_observations',HERE.parent/'issue65-native-limits/observations.py')
limit_observations=importlib.util.module_from_spec(limit_spec);limit_spec.loader.exec_module(limit_observations)
g1_spec=importlib.util.spec_from_file_location('repair_g1_observations',HERE.parent/'issue65-prepared-input/observations.py')
g1=importlib.util.module_from_spec(g1_spec);g1_spec.loader.exec_module(g1)



CAPTURE_FIXTURE_BEFORE='e35a01dad1e18ceddfd7569dbba22f6a554a23057751f7ce2f2387bc93192bbd'
CAPTURE_FIXTURE_AFTER='655525c2bbae543f5e466c1880f4d4a0e5406e5c0b921feec646dc5fddbfd5bc'
CAPTURE_FIXTURE_NAME='cmd/issue65-wire/capture_test.go'

def prepared_capture_fixture(raw):
    import hashlib
    if hashlib.sha256(raw).hexdigest()!=CAPTURE_FIXTURE_BEFORE:raise ValueError('capture fixture preimage changed')
    anchor=b'\trd := dbFor(t, r, nil)\n\tdefer rd.Close()\n\tr.failAcquisition = true\n'
    if raw.count(anchor)!=1:raise ValueError('capture fixture anchor changed')
    corrected=raw.replace(anchor,anchor.replace(b'\tr.failAcquisition',b'\tidle(t, r)\n\tr.failAcquisition'))
    if hashlib.sha256(corrected).hexdigest()!=CAPTURE_FIXTURE_AFTER:raise ValueError('capture fixture correction changed')
    return corrected

def adjusted_capture_reference(inventory):
    if inventory.get(CAPTURE_FIXTURE_NAME)!=CAPTURE_FIXTURE_BEFORE:raise ValueError('capture reference preimage changed')
    expected=dict(inventory);expected[CAPTURE_FIXTURE_NAME]=CAPTURE_FIXTURE_AFTER
    return expected


def go_env(w):
    sys.path.insert(0,str(w/'worktree/scripts'))
    from build_feedback import go_environment
    stripped={k:v for k,v in os.environ.items() if k not in ('GOCACHE','GOPATH','GOMODCACHE')}
    task_tmp=w/'temp/go-tmp';task_tmp.mkdir(exist_ok=True)
    return go_environment(dict(stripped,MARIAMEM_DEV_WORKSPACE=str(w),CGO_ENABLED='0',
                              GOTOOLCHAIN='go1.26.10',GOWORK='off',GOENV='off',GOTMPDIR=str(task_tmp),TMPDIR=str(task_tmp),
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
    (dest/'capture_test.go.txt').write_bytes(prepared_capture_fixture((original/'capture_test.go.txt').read_bytes()))
    shutil.copy2(HERE.parent/'issue65-native-live/live_test.go.txt',dest/'live_test.go.txt')
    shutil.copy2(HERE.parent/'issue65-native-compat/compat_test.go.txt',dest/'compat_test.go.txt')
    known=json.loads((OLD_FIX/'evidence/macos-reference.json').read_text())['template_sha256']
    for name in ('assemble.py','main.go.txt','live.go.txt','endpoint.go.txt','endpoint_test.go.txt','guard_controls.py','runtime_tests.py','fix_controls_test.go.txt'):
        source=(HERE if name=='assemble.py' else OLD_FIX)/name
        if name.endswith('.txt') and base.sha(source)!=known[name]:raise ValueError('accepted host template changed: '+name)
        shutil.copy2(source,dest/name)
    fixture=HERE.parent/'issue65-native-limits/limits_test.go.txt'
    if base.sha(fixture)!=LIMITS_FIXTURE_SHA256:raise ValueError('original38-observation fixture changed')
    shutil.copy2(fixture,dest/'limits_test.go.txt')
    shutil.copy2(HERE.parent/'issue65-policy-fix/policy_controls_test.go.txt',dest/'policy_controls_test.go.txt')
    fixture=HERE.parent/'issue65-prepared-input/g1_test.go.txt'
    if base.sha(fixture)!='804f48fa64a4467a879c3fcd65eb14b6a2b8dda53cf4bade570e163eabc0fd77':raise ValueError('original234-observation fixture changed')
    shutil.copy2(fixture,dest/'g1_test.go.txt')
    shutil.copy2(HERE/'repair_controls_test.go.txt',dest/'repair_controls_test.go.txt')
    if with_binding:
        binding=json.loads((HERE/'binding/identity.json').read_text())
        if binding['guest_sha256']!=GUEST_SHA:raise ValueError('binding/guest pin differs')
        shutil.copy2(HERE/'binding/identity.json',dest/'binding.json')
    sys.path.insert(0,str(w/'worktree/scripts'))
    from build_generated_guest import download
    pin=json.loads((w/'worktree/release/generated-go-toolchain.json').read_text())['archives']['converter']
    download(pin,w/'worktree/build/downloads')
    for name in ('main.go.txt','runtime_wire.go.txt','completion_probe.go.txt','owner_native_test.go.txt','lifetime_overlay.py'):
        shutil.copy2(HERE/name,dest/name)
    for name in ('owner.go','owner_test.go'):
        shutil.copy2(ROOT/'internal/nativewire'/name,dest/(name+'.txt'))
    return dest


def translate(w):
    dest=tools(w,with_binding=False)
    base.command(w,'translation',[sys.executable,dest/'assemble.py','--workspace',w,'--translate-only'],1200)


def runtime(w):
    if platform.system()!='Linux' or platform.machine()!='x86_64' or (os.environ.get('GITHUB_ACTIONS')=='true' and os.environ.get('RUNNER_ARCH')!='X64'):
        raise ValueError('CI acceptance requires native Linux x86_64')
    translate(w)
    execute(w)


def execute(w,compare_reference=True):
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
    base.command(w,'fix-controls',[binary,'-test.v','-test.run=^TestFix','-test.timeout=60s'],75)
    base.cases_from_log((w/'evidence/fix-controls.txt').read_text(),{'TestFixFoundRowsNegotiatedPerConnection','TestFixPreparedUCAThroughNativeFork'})
    limits_exit=0
    try:base.command(w,'limits-suite',[binary,'-test.v','-test.run=^TestLimits','-test.timeout=240s'],270)
    except subprocess.CalledProcessError as error:limits_exit=error.returncode
    limits_result=limit_observations.analyze((w/'evidence/limits-suite.txt').read_text(),limits_exit)
    base.save(w/'evidence/limits-result.json',limits_result)
    base.command(w,'policy-controls',[binary,'-test.v','-test.run=^TestPolicy','-test.timeout=60s'],75)
    controls=base.cases_from_log((w/'evidence/policy-controls.txt').read_text(),{
        'TestPolicyRejectedResetPreservesPreparedSession','TestPolicyLoginErrorDeliveredBeforeRetire','TestPolicyOutputErrorPreservesStream'})
    base.save(w/'evidence/policy-controls.json',{'cases':[{'name':n,'elapsed':t,'result':'PASS'} for n,t in controls]})
    g1_exit=0
    try:base.command(w,'g1-suite',[binary,'-test.v','-test.run=^TestG1','-test.timeout=240s'],270)
    except subprocess.CalledProcessError as error:g1_exit=error.returncode
    g1_result=g1.analyze((w/'evidence/g1-suite.txt').read_text(),g1_exit)
    base.save(w/'evidence/g1-result.json',g1_result)
    base.command(w,'repair-controls',[binary,'-test.v','-test.run=^TestRepair','-test.timeout=60s'],75)
    repair=base.cases_from_log((w/'evidence/repair-controls.txt').read_text(),{
        'TestRepairMultiParameterDescriptorRollback','TestRepairRetainsBoundCharset',
        'TestRepairFirstRejectedBind','TestRepairEmptyPrepareInvalidatesAlias'})
    base.save(w/'evidence/repair-controls.json',{'cases':[{'name':n,'elapsed':t,'result':'PASS'} for n,t in repair]})
    base.command(w,'live-endpoint-tests',[sys.executable,Path(__file__),'endpoint-tests','--workspace',w],120)
    base.command(w,'runtime-boundary',[sys.executable,dest/'runtime_tests.py'],300)
    base.command(w,'owner-native',[binary,'-test.v','-test.run=^TestOwner','-test.timeout=180s'],210)
    names={'TestOwnerHostIdentity','TestOwnerNativeRetirementFence','TestOwnerHostRelayFence',
           'TestOwnerCapturePendingOpen','TestOwnerLostOpen','TestOwnerStaleFrames',
           'TestOwnerWrongProfile','TestOwnerWrongOpened','TestOwnerRequestExhaustion'}
    rows=base.cases_from_log((w/'evidence/owner-native.txt').read_text(),names)
    base.save(w/'evidence/owner-native.json',{'cases':[{'name':n,'elapsed':t,'result':'PASS'} for n,t in rows]})
    base.command(w,'lifetime-leaf',[sys.executable,HERE/'lifetime_tests.py','--workspace',w],240)
    base.cases_from_log((w/'evidence/lifetime-leaf.txt').read_text(),{
      'TestWorkerReclaimWaitsForLastAccess','TestDetachedSelfReclaimEndsBeforePoolCompletion',
      'TestCompletedJoinAddressReuseAndIndependentDB','TestConcurrentWorkerReclaims',
      'TestFailedSpawnDoesNotRegisterAllocation','TestCallerOwnedStackHasNoTrackedFree',
      'TestReclaimerAddressReuseDoesNotEraseNewGeneration','TestWorkerAllocationBindingRejectsInvalidInputs',
      'TestDeferredAllocatorFailureIsRetained','TestLateReclaimerYieldCannotWriteDeadTLS'})

    base.command(w,'native-controls',[sys.executable,HERE/'native_controls.py','--workspace',w],700)
    base.command(w,'binding-controls',[sys.executable,dest/'guard_controls.py'],120)
    # Guard tests remain explicitly tied to the installer/canonical source fixture.
    base.command(w,'pytest-install',[sys.executable,'-m','pip','install','--no-cache-dir','--disable-pip-version-check','--no-compile','--target',w/'temp/pytest','pytest==8.4.2'],180)
    code='import sys;sys.path.insert(0,sys.argv[1]);import pytest;raise SystemExit(pytest.main(["-q","-p","no:cacheprovider","--basetemp",sys.argv[2],sys.argv[3]]))'
    base.command(w,'binding-tests',[sys.executable,'-c',code,w/'temp/pytest',w/'temp/pytest-run',w/'worktree/tests/test_thread_lifetime_binding.py'],120)
    if '22 passed' not in (w/'evidence/binding-tests.txt').read_text():raise ValueError('binding scope incomplete')
    product=w/'temp/host/product'
    sys.path.insert(0,str(w/'worktree/scripts'))
    from dev_guest import inventory
    if inventory(product)!=host['source_inventory']:raise ValueError('full executed source inventory changed')
    for name,pin in host['source_inventory'].items():
        if base.sha(product/name)!=pin:raise ValueError('staged source changed: '+name)
    if base.sha(binary)!=host['binary_sha256']:raise ValueError('binary changed')
    base.identity(w/'worktree',HOST_SOURCE)
    if compare_reference:
        reference=HERE/'evidence/macos-reference.json'
        if base.sha(reference)!=SOURCE_REFERENCE_SHA256:raise ValueError('reviewed source reference changed')
        recorded=json.loads(reference.read_text())
        if recorded['guest_sha256']!=GUEST_SHA:raise ValueError('source reference guest differs')
        compared,different=base.source_difference(host['source_inventory'],recorded['source_inventory'])
        base.save(w/'evidence/source-comparison.json',{'mac_reference_binary_sha256':recorded['binary_sha256'],
                   'compared_go_assembly_data_files':compared,'different_files':different,
                   'reference_adjustments':[]})
        if different:raise ValueError('compiled code differs from reviewed macOS source bundle')
        result['source_reference_status']='MATCHED_P1_OWNER_REFERENCE'
    else:
        result['source_reference_status']='LOCAL_REFERENCE_CANDIDATE'
    base.save(w/'evidence/tooling.json' ,{'probe_sha256':base.sha(Path(__file__)),
              'binding_sha256':base.sha(HERE/'binding/identity.json'),
              'historical_main_baseline_commit':'61973daa19b6f665d7342338c3252dd7af61fc90'})
    result['supporting_checks']='PASS'
    result['limits_result']=limits_result
    result['policy_controls']=3
    result['g1_result']=g1_result
    result['repair_controls']=4
    result['owner_cases']=9
    result['lifetime_cases']=10
    result['native_fault_controls']=3
    result['ready']=result['ready'] and limits_result['ready'] and g1_result['ready']
    result['result']='PASS scoped native P1-a baseline' if result['ready'] else 'NOT_READY: native P1-a baseline'
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
    base.command(w, 'guest-build', [sys.executable, HERE/'build_checked_guest.py', '--workspace', w], 2700)
    base.guest_record(w)
    base.save(w/'evidence/builder.json', {'machine':platform.machine(), 'system':platform.system(), 'source_commit':GUEST_SOURCE, 'guest_sha256':GUEST_SHA, 'probe_sha256':base.sha(Path(__file__))})


def record_local(w):
    if os.environ.get('GITHUB_ACTIONS')=='true' or platform.system()!='Darwin' or platform.machine()!='arm64':
        raise ValueError('reference recording is explicit local macOS arm64 only; CI cannot bypass comparison')
    execute(w,compare_reference=False)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('stage',choices=['build','downloads','runtime','translate','execute','record-local','endpoint-tests','preflight','cleanup'])
    p.add_argument('--workspace',type=Path,required=True);a=p.parse_args();w=a.workspace.resolve()
    if not (w/'experiment.json').is_file():p.error('owned workspace required')
    if not re.fullmatch('[0-9a-f]{64}',GUEST_SHA):p.error('guest pin not reviewed')
    tooling_sha=subprocess.check_output(['git','-c','safe.directory='+str(ROOT),'rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    receipt=json.loads((w/'experiment.json').read_text())
    base.safe_git(ROOT,w/'worktree',Path(receipt['repo']))
    base.identity(ROOT,tooling_sha)
    os.environ['MARIAMEM_TOOLING_SOURCE_COMMIT']=tooling_sha
    base.save(w/'evidence'/('platform-'+a.stage+'.json'),{'uname':list(platform.uname()),
              'runner_arch':os.environ.get('RUNNER_ARCH'),'run_id':os.environ.get('GITHUB_RUN_ID'),
              'probe_sha256':base.sha(Path(__file__)),
              'tooling_source_commit':subprocess.check_output(['git','-c','safe.directory='+str(ROOT),'rev-parse','HEAD'],cwd=ROOT,text=True).strip()})
    try:{'build':build,'downloads':base.downloads,'runtime':runtime,'translate':translate,
         'execute':execute,'record-local':record_local,'endpoint-tests':endpoint_tests,'preflight':lambda work:base.identity(work/'worktree',HOST_SOURCE),'cleanup':base.cleanup}[a.stage](w)
    except Exception as error:
        base.save(w/'evidence'/(a.stage+'-failure.json'),{'error':str(error),'probe_sha256':base.sha(Path(__file__))});raise

if __name__=='__main__':main()
