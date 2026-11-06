#!/usr/bin/env python3
"""Observe the fixed native guest against the approved contract; no policy patch."""
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
from observations import analyze
spec=importlib.util.spec_from_file_location('live_probe',HERE.parent/'issue65-native-live/probe.py')
live=importlib.util.module_from_spec(spec)
spec.loader.exec_module(live)
base=live.base


def compile_compat(w):
    base.identity(w/'worktree',base.HOST_SOURCE)
    subprocess.run(['go','test','-c','-p','1','-trimpath','-buildvcs=false',
                    '-o',str(w/'temp/host/compat.test'),'./cmd/issue65-wire'],
                   cwd=w/'temp/host/product',env=live.go_env(w),check=True)


def runtime(w):
    # Preserve the original source-comparison/binding controls and all22 cases.
    live.runtime(w)
    shutil.copy2(w/'evidence/result.json',w/'evidence/live-repeat-result.json')
    base.save(w/'evidence/result.json',{'result':'INCOMPLETE: compatibility not yet executed'})
    product=w/'temp/host/product'
    from dev_guest import inventory
    original=inventory(product)
    target=product/'cmd/issue65-wire/compat_test.go'
    if target.exists():raise ValueError('unexpected existing compatibility file')
    source=HERE/'compat_test.go.txt';template_sha=base.sha(source)
    shutil.copy2(source,target)
    env=live.go_env(w)
    go_root=Path(subprocess.check_output(['go','env','GOROOT'],env=env,text=True).strip())
    subprocess.run([str(go_root/'bin/gofmt'),'-w',str(target)],env=env,check=True)
    pins=inventory(product)
    if set(pins)-set(original)!={'cmd/issue65-wire/compat_test.go'} or any(pins.get(n)!=v for n,v in original.items()):
        raise ValueError('compatibility assembly changed the qualified source bundle')
    base.command(w,'compat-build',[sys.executable,Path(__file__),'compile','--workspace',w],1200)
    binary=w/'temp/host/compat.test'
    if inventory(product)!=pins:raise ValueError('compile changed source')
    build={'result':'UNQUALIFIED','source_inventory':pins,'binary_sha256':base.sha(binary),
           'template_sha256':template_sha,'probe_sha256':base.sha(Path(__file__)),
           'observations_sha256':base.sha(HERE/'observations.py'),
           'tooling_source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=HERE.parents[2],text=True).strip(),
           'guest_source_commit':base.GUEST_SOURCE,'guest_sha256':base.GUEST_SHA,
           'host_source_commit':base.HOST_SOURCE,
           'go_buildinfo':subprocess.check_output(['go','version','-m',str(binary)],env=env,text=True)}
    base.save(w/'evidence/compat-build.json',build)
    exit_code=0
    try:
        base.command(w,'compat-suite',[binary,'-test.v','-test.run=^TestCompat','-test.timeout=120s'],150)
    except subprocess.CalledProcessError as error:
        exit_code=error.returncode
    # Preserve mismatches even when go test exits1. No acceptance target refresh.
    result=analyze((w/'evidence/compat-suite.txt').read_text(),exit_code)
    result.update({'guest_sha256':base.GUEST_SHA,'guest_source_commit':base.GUEST_SOURCE,
                   'host_source_commit':base.HOST_SOURCE,'binary_sha256':build['binary_sha256'],
                   'tooling_source_commit':build['tooling_source_commit'],
                   'not_qualified':['full command/capability profile','large aggregate output and output caps',
                                    'all prepared edge vectors','public APIs','controller relocation',
                                    'race freedom','performance','release']})
    base.save(w/'evidence/result.json',result)
    if inventory(product)!=pins or base.sha(binary)!=build['binary_sha256'] or base.sha(source)!=template_sha:
        raise ValueError('executed source/binary changed')
    base.identity(w/'worktree',base.HOST_SOURCE)
    if not result['ready']:
        raise ValueError(result['result']+'; original observations retained; do not weaken the contract')


if __name__=='__main__':
    if len(sys.argv)==4 and sys.argv[1:3]==['compile','--workspace']:
        compile_compat(Path(sys.argv[3]).resolve())
    else:
        base.runtime=runtime
        base.main()
