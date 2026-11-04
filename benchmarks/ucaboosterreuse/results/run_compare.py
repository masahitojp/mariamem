import argparse,hashlib,json,os,subprocess,sys,time
from pathlib import Path
W=Path(__file__).resolve().parents[1];T=W/'temp';E=W/'evidence';S=T/'source';PY=T/'venv/bin/python'
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(n,j):(E/n).write_text(json.dumps(j,indent=2,ensure_ascii=False)+'\n')
def binary(label):return T/'baseline-host' if label=='baseline' else T/'dev-native/mariamem-dev-host'
def validate(j,negative=False):
 assert j['result']==('FAIL' if negative else 'PASS') and not j['cleanup_errors']
 assert j['cleanup']=={'refs':0,'process_exit':0,'reaped':True,'root_exists':False}
 if negative:assert 'seed oracle' in j['error']
 else:
  assert len(j['children'])==4 and all(c['oracle'] for c in j['children'])
  assert [h['children'] for h in j['held']]==[0,1,2,4]
  reference=json.loads((E/'native-reference.json').read_text())
  for c in j['children']:
   assert c['fork_wall_ns']>0 and c['fork_cpu_ns']>0
   for k in ['ascii','mixed']:assert c['sql'][k]['result']==reference['perf_expected'][k]
def preflight():
 sys.path.insert(0,str(S/'scripts'));import git_identity,dev_guest
 source='f24c308bb6758e97722f4cb26bcb1de7c2df16b9';git_identity.require_commit(S,source)
 assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=S,text=True).strip()=='d6c7e8b677ce3e5c390a2717d1dde076b3c3a2c5'
 assert not subprocess.check_output(['git','status','--porcelain'],cwd=S,text=True)
 guest=dev_guest.verify_guest(S,T/'dev-guest');development=json.loads((T/'dev-native/development.json').read_text());assert development['smoke']=='PASS' and development['result']=='UNQUALIFIED' and development['host_source_identity']['commit']=='d6c7e8b677ce3e5c390a2717d1dde076b3c3a2c5'
 baseline=json.loads((E/'baseline-binary.json').read_text());assert digest(binary('baseline'))==baseline['binary_sha256']
 assert digest(binary('candidate'))==development['binary_sha256'] and guest['guest_sha256']==development['guest_sha256']
 base_info=json.loads(subprocess.check_output([str(binary('baseline')),'--snapshot-info'],text=True));assert base_info['wasm_sha256']!=guest['guest_sha256']
 frozen=json.loads((E/'frozen-measurement-tools.json').read_text())['files']
 for name,sha in frozen.items():assert digest(E/name)==sha,name
 save('measurement-inputs.json',{'source_commit':source,'host_stage_source_commit':'d6c7e8b677ce3e5c390a2717d1dde076b3c3a2c5','product_behavior_base':'bc00b8e66e5fd57bc9b2127001faf8e05952b417','measurement_tools':frozen,'binaries':{'baseline':{'sha256':baseline['binary_sha256'],'guest_sha256':base_info['wasm_sha256']},'candidate':{'sha256':development['binary_sha256'],'guest_sha256':guest['guest_sha256']}},'candidate_identity':'UNQUALIFIED dev pipeline; source/patch/tool identities plus staged generated/host inventories and binary hash, buildvcs=false as the documented route','observer':json.loads((E/'resource-observer-check.json').read_text())})
def run(name,label,mode='measure',negative=False):
 frozen=json.loads((E/'frozen-measurement-tools.json').read_text())['files']
 assert digest(E/'probe.py')==frozen['probe.py'] and digest(Path(__file__))==frozen['run_compare.py']
 d=T/'runs'/name;d.mkdir(parents=True);scratch=d/'scratch';scratch.mkdir();env={k:v for k,v in os.environ.items() if not k.startswith(('MARIAMEM_','MYSQLMEM_'))};env.update(PYTHONPATH=str(S/'python'),TMPDIR=str(scratch),GOMAXPROCS='8')
 cmd=[str(PY),str(E/'probe.py'),'--mode',mode,'--host',str(binary(label))]
 if negative:cmd+=['--negative']
 a=time.perf_counter_ns();p=subprocess.run(cmd,cwd=S,env=env,text=True,capture_output=True,timeout=180);elapsed=time.perf_counter_ns()-a
 (E/(name+'.stderr.txt')).write_text(p.stderr);j=json.loads(p.stdout);j.update(probe_sha256=digest(E/'probe.py'),runner_sha256=digest(Path(__file__)),label=label,exit_code=p.returncode,controller_process_wall_ns=elapsed,binary_sha256=digest(binary(label)),scratch_remaining=sorted(str(x.relative_to(scratch)) for x in scratch.rglob('*')));save(name+'.json',j)
 assert not j['scratch_remaining'] and p.returncode==(1 if negative else 0)
 if mode=='semantic':
  assert j['result']=='PASS' and j['semantic']==json.loads((E/'native-reference.json').read_text())['semantic'];assert all(c['oracle'] for c in j['children'])
  assert j['cleanup']=={'refs':0,'process_exit':0,'reaped':True,'root_exists':False} and not j['cleanup_errors']
 else:validate(j,negative)
 print(name,'expected negative detected' if negative else 'PASS',flush=True)
p=argparse.ArgumentParser();p.add_argument('--phase',choices=['baseline-pilot','pilot','measure'],required=True);a=p.parse_args()
if a.phase!='baseline-pilot':
 assert json.loads((E/'guest-table-verification.json').read_text())['result']=='PASS'
 preflight()
if a.phase=='baseline-pilot':
 run('baseline-early-pilot','baseline');run('baseline-early-negative','baseline',negative=True)
elif a.phase=='pilot':
 assert json.loads((T/'dev-native/development.json').read_text())['smoke']=='PASS'
 run('candidate-semantic','candidate','semantic')
 for label in ['baseline','candidate']:run(label+'-negative',label,negative=True)
 save('pilot-check.json',{'semantic_native_baseline_candidate':'PASS','wrong_seed_controls':'PASS','cleanup':'PASS'})
else:
 assert json.loads((E/'pilot-check.json').read_text())['semantic_native_baseline_candidate']=='PASS'
 for label in ['baseline','candidate']:run('warmup-'+label,label)
 for i in range(5):
  for label in (['baseline','candidate'] if i%2==0 else ['candidate','baseline']):run(f'round{i}-'+label,label)
