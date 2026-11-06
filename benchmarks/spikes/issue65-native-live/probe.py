#!/usr/bin/env python3
"""3D.2 native Live experiment, layered on the immutable Linux repeat."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('linux_probe', HERE.parent/'issue65-native-linux/probe.py')
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
linux_runtime = base.runtime
EXPECTED = {
    'TestNativeLiveDrainAndReset',
    'TestNativeLiveCapacityBeforeDrain',
    'TestNativeLiveReplacementFailureRecovery',
    'TestNativeLiveCancellationBeforeCommit',
    'TestNativeLiveCleanupDebtRecovery',
    'TestNativeLiveCaptureDebtIsPermanent',
    'TestNativeLiveParentAndEndpointClose',
    'TestNativeLiveInvalidRestoreNeverAdmits',
}


def go_env(w):
    sys.path.insert(0, str(w/'worktree/scripts'))
    from build_feedback import go_environment
    isolated = {k:v for k,v in os.environ.items() if k not in ('GOCACHE','GOPATH','GOMODCACHE')}
    return go_environment(dict(isolated, MARIAMEM_DEV_WORKSPACE=str(w),
                              CGO_ENABLED='0', GOTOOLCHAIN='go1.26.10',
                              GOWORK='off', GOENV='off', GOFLAGS='', GOEXPERIMENT='',
                              GOMAXPROCS='2', GOGC='50'))


def compile_live(w):
    base.identity(w/'worktree',base.HOST_SOURCE)
    subprocess.run(['go','test','-c','-p','1','-trimpath','-buildvcs=false',
                    '-o',str(w/'temp/host/live.test'),'./cmd/issue65-wire'],
                   cwd=w/'temp/host/product',env=go_env(w),check=True)


def runtime(w):
    # Keep the original 14 cases, source equality and failure controls intact.
    linux_runtime(w)
    shutil.copy2(w/'evidence/result.json', w/'evidence/linux-repeat-result.json')
    base.save(w/'evidence/result.json', {'result':'INCOMPLETE: Live proof has not passed'})
    product = w/'temp/host/product'
    cmd = product/'cmd/issue65-wire'
    original = json.loads((w/'evidence/host-build.json').read_text())
    templates = {}
    for name in ('live.go', 'live_test.go'):
        source = HERE/(name+'.txt')
        target = cmd/name
        if target.exists():
            raise ValueError('unexpected existing Live file')
        shutil.copy2(source, target)
        templates[source.name] = base.sha(source)
    sys.path.insert(0, str(w/'worktree/scripts'))
    from dev_guest import inventory
    env = go_env(w)
    go_root = Path(subprocess.check_output(['go','env','GOROOT'],env=env,text=True).strip())
    subprocess.run([str(go_root/'bin/gofmt'),'-w',str(cmd/'live.go'),str(cmd/'live_test.go')],env=env,check=True)
    sources = inventory(product)
    added = {n for n in sources if n not in original['source_inventory']}
    if added != {'cmd/issue65-wire/live.go','cmd/issue65-wire/live_test.go'}:
        raise ValueError('Live must add exactly the two inventoried templates')
    if any(sources.get(n) != v for n,v in original['source_inventory'].items()):
        raise ValueError('Live assembly changed the Linux-qualified baseline sources')
    binary = w/'temp/host/live.test'
    base.command(w,'live-build',[sys.executable,Path(__file__),'compile',
                                 '--workspace',w],1200)
    pins = inventory(product)
    if pins != sources:
        raise ValueError('compile changed staged source')
    base.save(w/'evidence/live-build.json', {
        'result':'UNQUALIFIED', 'host_source_commit':base.HOST_SOURCE,
        'guest_source_commit':base.GUEST_SOURCE, 'guest_sha256':base.GUEST_SHA,
        'tooling_source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=HERE.parents[2],text=True).strip(),
        'probe_sha256':base.sha(Path(__file__)), 'templates_sha256':templates,
        'source_inventory':pins, 'binary_sha256':base.sha(binary),
        'go_buildinfo':subprocess.check_output(['go','version','-m',str(binary)],env=env,text=True),
        'unchanged_baseline_files':len(original['source_inventory']),
    })
    # Entire combined binary reruns all original cases as well as Live cases.
    base.command(w,'live-suite',[binary,'-test.v','-test.timeout=120s'],150)
    prior = {c['name'] for c in json.loads((w/'evidence/linux-repeat-result.json').read_text())['cases']}
    cases = base.cases_from_log((w/'evidence/live-suite.txt').read_text(), prior|EXPECTED)
    if len(prior)!=14 or len(cases)!=22:
        raise ValueError('Live scope changed')
    if base.sha(binary) != json.loads((w/'evidence/live-build.json').read_text())['binary_sha256'] or inventory(product)!=pins:
        raise ValueError('executed source/binary changed')
    base.identity(w/'worktree',base.HOST_SOURCE)
    base.save(w/'evidence/result.json', {
        'result':'PASS for bounded native Live experiment',
        'system':base.platform.system(),'machine':base.platform.machine(),
        'guest_sha256':base.GUEST_SHA,'guest_source_commit':base.GUEST_SOURCE,
        'host_source_commit':base.HOST_SOURCE,
        'cases':[{'name':n,'elapsed':t,'result':'PASS'} for n,t in cases],
        'modeled_failures':['replacement rejection','ordinary disposal debt','root acquisition cleanup debt'],
        'not_qualified':['public Live API integration','full protocol compatibility','race freedom','performance','release'],
    })


if __name__ == '__main__':
    if len(sys.argv)==4 and sys.argv[1:3]==['compile','--workspace']:
        compile_live(Path(sys.argv[3]).resolve())
    else:
        base.runtime = runtime
        base.main()
