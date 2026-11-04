"""Fixed build/pilot/measure runner. Run under experiment_workspace.py run."""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

W = Path(os.environ['MARIAMEM_EXPERIMENT_TEMP']).parent
T, E = W/'temp', W/'evidence'
S = T/'source'
ENV = dict(os.environ, GOTOOLCHAIN='go1.26.10', CGO_ENABLED='0', GOMAXPROCS='8', GOCACHE=str(T/'go-cache'))
GO='/opt/homebrew/bin/go'

def git(*args):
    return subprocess.check_output(['git',*args],cwd=S,text=True).strip()
def write(name, data):
    (E/name).write_text(json.dumps(data,indent=2)+'\n')
def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def identity():
    spec=importlib.util.spec_from_file_location('git_identity', S/'scripts/git_identity.py')
    mod=importlib.util.module_from_spec(spec);sys.modules[spec.name]=mod;spec.loader.exec_module(mod)
    return mod

def build():
    assert not git('status','--porcelain')
    plan=json.loads((S/'benchmarks/forkstages/plan.json').read_text())
    product=plan['source_commit']; mod=identity();mod.require_commit(S,product)
    head=git('rev-parse','HEAD');mod.require_commit(S,head)
    changed=git('diff','--name-only',product,head).splitlines()
    assert changed and all(x.startswith('benchmarks/forkstages/') for x in changed),changed
    subprocess.run([sys.executable,'benchmarks/forkstages/overlay.py',str(S),str(T/'overlay')],cwd=S,check=True,env=ENV)
    command=[GO,'build','-trimpath','-buildvcs=true','-overlay',str(T/'overlay/overlay.json'),'-o',str(T/'probe'),'./benchmarks/forkstages']
    with (E/'build.txt').open('w') as log: subprocess.run(command,cwd=S,env=ENV,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=900)
    old=os.environ.get('GOTOOLCHAIN');os.environ['GOTOOLCHAIN']='go1.26.10'
    try: stamp=mod.verify_go_binary(S,T/'probe',head,go=GO,toolchain='go1.26.10')
    finally:
        if old is None:os.environ.pop('GOTOOLCHAIN',None)
        else:os.environ['GOTOOLCHAIN']=old
    write('inputs.json',{'source_commit':product,'harness_source_commit':head,'source_identity':'commit object, clean checkout, benchmark-only diff',
          'guest_sha256':__import__('re').search(r'GuestSHA256\s*=\s*"([a-f0-9]{64})"',(S/'internal/generatedgo/main.go').read_text()).group(1),
          'native_version_source_sha256':digest(S/'native_version.go'),
          'binary_sha256':digest(T/'probe'),'binary_build_info':stamp,
          'overlay':json.loads((T/'overlay/hashes.json').read_text()),'platform':platform.platform(),
          'machine':subprocess.check_output(['sysctl','-n','machdep.cpu.brand_string'],text=True).strip(),
          'memory_bytes':int(subprocess.check_output(['sysctl','-n','hw.memsize'],text=True)),
          'plan':plan,'build_command':['go','build','-trimpath','-buildvcs=true','-overlay','<TEMP>/overlay/overlay.json','-o','<TEMP>/probe','./benchmarks/forkstages']})

def run(name,traced,negative=False):
    d=T/name;d.mkdir();scratch=d/'scratch';scratch.mkdir();traces=d/'traces';traces.mkdir()
    env=dict(ENV,TMPDIR=str(scratch))
    cmd=[str(T/'probe'),'--trace-dir',str(traces)]
    if traced:cmd+=['--trace']
    if negative:cmd+=['--negative']
    start=time.time();p=subprocess.run(cmd,cwd=S,env=env,capture_output=True,text=True,timeout=45)
    (E/(name+'.stderr.txt')).write_text(p.stderr)
    data=json.loads(p.stdout)
    data.update({'exit_code':p.returncode,'process_seconds':time.time()-start,'scratch_remaining':sorted(x.name for x in scratch.iterdir())})
    write(name+'.json',data)
    if negative:
        assert p.returncode==1 and 'seed oracle' in data['error'] and data['result']=='FAIL'
    else:
        assert p.returncode==0 and data['result']=='PASS' and len(data['children'])==4
        assert all(c['oracle'] for c in data['children'])
        if traced:
            for c in data['children']:
                names={x['name'] for x in c['events']}
                assert {'runtime/prepared_handles_begin','runtime/prepared_handles_ready','runtime/reserve_begin','runtime/reserve_end','runtime/construct_begin','runtime/construct_end','startup/ready_response_observed','startup/wire_listener_ready','fork/end'}<=names,names
                assert len(c['guest']['events'])>=8,c['guest']
    assert not data['scratch_remaining']
    assert all(data['cleanup'][n]==0 for n in ('active_mappings','active_rw_bytes','active_reserved_bytes','release_failures'))
    print(name, data['result'],flush=True)

p=argparse.ArgumentParser();p.add_argument('--phase',choices=['build','pilot','measure','all'],required=True);args=p.parse_args()
if args.phase in ('build','all'):build()
if args.phase in ('pilot','all'):
    run('pilot',True);run('negative',True,True)
    write('pilot-assessment.json',{'positive':'PASS','wrong_seed_detected':'PASS','cleanup':'PASS'})
if args.phase in ('measure','all'):
    assert json.loads((E/'pilot-assessment.json').read_text())['positive']=='PASS'
    run('warmup-plain',False);run('warmup-traced',True)
    for i in range(5):
        for traced in ([False,True] if i%2==0 else [True,False]):run(f'round{i}-'+('traced' if traced else 'plain'),traced)
