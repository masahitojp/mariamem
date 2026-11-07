#!/usr/bin/env python3
"""Fixed-guest G2: strict accepted baseline, then one observation-only source extension."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import subprocess
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
fix=load('g2_baseline_probe',HERE/'probe_baseline.py')
observer=load('g2_observer',HERE.parent/'issue65-g2/observations.py')
base=fix.base
G2_REFERENCE_SHA256='d307057e5d9f85945a79aaf6b06feae5826c8da39f5186d0de0e1a666a57d22f'
comparison=load('g2_repair_compare',HERE/'compare_results.py')
contract=load('g2_handshake_contract',HERE/'handshake_contract.py')

def compile_fixture(w):
    product=w/'temp/host/product'
    host=json.loads((w/'evidence/host-build.json').read_text())
    sys.path.insert(0,str(w/'worktree/scripts'))
    from dev_guest import inventory
    fixture=HERE.parent/'issue65-g2/g2_test.go.txt'
    baseline=host['source_inventory']
    if inventory(product)!=baseline:raise ValueError('full baseline inventory differs before G2 extension')
    if base.sha(w/'temp/host/wire.test')!=host['binary_sha256']:raise ValueError('baseline binary changed')
    prepared=contract.fixture(fixture.read_bytes())
    fixture_sha=hashlib.sha256(prepared).hexdigest()
    (product/'cmd/issue65-wire/g2_test.go').write_bytes(prepared)
    pins=inventory(product)
    expected=dict(baseline,**{'cmd/issue65-wire/g2_test.go':fixture_sha})
    if pins!=expected:raise ValueError('full source must be unchanged baseline plus G2 fixture')
    count=observer.require_extension(pins,baseline,fixture_sha)
    binary=w/'temp/host/g2.test'
    env=fix.go_env(w)
    subprocess.run(['go','test','-c','-p','1','-trimpath','-buildvcs=false','-o',str(binary),'./cmd/issue65-wire'],cwd=product,env=env,check=True)
    if inventory(product)!=pins:raise ValueError('source changed while compiling G2')
    base.save(w/'evidence/g2-build.json',{'guest_source_commit':fix.GUEST_SOURCE,'guest_sha256':fix.GUEST_SHA,
        'host_source_commit':fix.HOST_SOURCE,'baseline_binary_sha256':host['binary_sha256'],
        'binary_sha256':base.sha(binary),'fixture_sha256':fixture_sha,'original_fixture_sha256':base.sha(fixture),'contract':contract.CONTRACT,'source_inventory':pins,
        'staged_go_assembly_data_files':count,
        'tooling_source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        'go_buildinfo':subprocess.check_output(['go','version','-m',str(binary)],env=env,text=True)})

def observe(w):
    base.save(w/'evidence/g2-result.json',{'result':'INCOMPLETE: G2 pending','complete':False,'ready':False})
    base.command(w,'g2-compile',[sys.executable,Path(__file__),'compile','--workspace',w],300)
    code=0
    try:base.command(w,'g2-suite',[w/'temp/host/g2.test','-test.v','-test.run=^TestG2','-test.timeout=240s'],270)
    except subprocess.CalledProcessError as error:code=error.returncode
    result=observer.analyze((w/'evidence/g2-suite.txt').read_text(),code)
    build=json.loads((w/'evidence/g2-build.json').read_text())
    sys.path.insert(0,str(w/'worktree/scripts'))
    from dev_guest import inventory
    if (inventory(w/'temp/host/product')!=build['source_inventory']
        or base.sha(w/'temp/host/g2.test')!=build['binary_sha256']
        or base.sha(w/'temp/host/wire.test')!=build['baseline_binary_sha256']):
        raise ValueError('executed G2 source/binary changed')
    base.identity(w/'worktree',fix.HOST_SOURCE)
    result.update({k:build[k] for k in ('guest_source_commit','guest_sha256','host_source_commit','tooling_source_commit','fixture_sha256','binary_sha256','original_fixture_sha256','contract')})
    result['baseline_result']=json.loads((w/'evidence/result.json').read_text())['result']
    result['not_qualified']=['unobserved G2 combinations','public APIs','controller relocation','performance','adoption','release']
    base.save(w/'evidence/g2-result.json',result)
    if platform.system()=='Linux':
        reference=HERE/'evidence/macos-g2-result.json'
        if base.sha(reference)!=G2_REFERENCE_SHA256:raise ValueError('G2 Mac comparison reference changed')
        compared=comparison.compare(contract.reference_for_comparison(json.loads(reference.read_text())),result)
        base.save(w/'evidence/g2-source-platform-comparison.json',compared)
        if not compared['matched']:raise ValueError('G2 observations differ from Mac;original result retained')
    if not result['ready']:raise ValueError(result['result'])

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('stage',choices=('local','runtime','observe','compile'));p.add_argument('--workspace',type=Path,required=True)
    a=p.parse_args();w=a.workspace.resolve()
    if not (w/'experiment.json').is_file():p.error('owned workspace required')
    source=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip();base.identity(ROOT,source);base.identity(w/'worktree',fix.HOST_SOURCE)
    base.guest_record(w)
    base.save(w/'evidence'/('g2-platform-'+a.stage+'.json'),{'uname':list(platform.uname()),'tooling_source_commit':source,'probe_sha256':base.sha(Path(__file__))})
    if a.stage in ('local','runtime'):
        if a.stage=='local':
            if platform.system()!='Darwin' or platform.machine()!='arm64' or os.environ.get('GITHUB_ACTIONS')=='true':raise ValueError('local requires native macOS arm64 outside CI')
            stages=('translate','execute')
        else:
            if platform.system()!='Linux' or platform.machine()!='x86_64':raise ValueError('runtime requires native Linux x86_64')
            stages=('runtime',)
        for stage in stages:subprocess.run([sys.executable,fix.__file__,stage,'--workspace',str(w)],check=True)
        observe(w)
    elif a.stage=='compile':compile_fixture(w)
    else:
        if json.loads((w/'evidence/result.json').read_text()).get('ready') is not True:raise ValueError('accepted baseline required')
        observe(w)
if __name__=='__main__':main()
