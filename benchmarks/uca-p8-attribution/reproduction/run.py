from pathlib import Path
import json,os,sys,subprocess,hashlib,time,re,platform
W=Path(__file__).resolve().parents[1];S=W/'worktree';E=W/'evidence';T=W/'temp'
sys.path.insert(0,str(S/'scripts'));from experiment_disk import DiskGuard
guard=DiskGuard(W,6,8)
plan=json.loads((S/'benchmarks/uca-p8-attribution/plan.json').read_text())
source=subprocess.check_output(['git','rev-parse','HEAD'],cwd=S,text=True).strip()
assert not subprocess.check_output(['git','status','--porcelain'],cwd=S)
env={k:v for k,v in os.environ.items() if not k.startswith(('GO','MARIAMEM_','MYSQLMEM_','LC_STAGE_','LEXER_','CLOSE_DIAG_','ISSUE','MODELCASE_','SAMPLE_','FORK_STAGE','SHOP_','TIMER_','ANALYZE_'))}
env.update(GOMAXPROCS='8',GOGC='100',ISSUE88_POOL_MIB='16',FORK_STAGES='0',SHOP_PARALLEL='8')
records=[]
def dump(p,x):p.write_text(json.dumps(x,separators=(',',':'))+'\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def blocks(text,db):
 result=[]
 for block in text.split('\n\n'):
  labels=next((json.loads(l[len('# labels: '):]) for l in block.splitlines() if l.startswith('# labels: ')),{})
  if labels.get('db_id')==db:result.append(block)
 return result

def usable(c,text):
 return (c['call_enter_us']<=c['snapshot_begin_us']<=c['snapshot_end_us']<=c['call_return_us'] and not c['truncated'] and not c.get('error') and any('/internal/generatedgo/code/p' in b for b in blocks(text,c['db_id'])))

def execute(arm,mode,repeat):
 name=f'{mode}-{repeat}-{arm}';d=T/name;d.mkdir();scratch=d/'scratch';scratch.mkdir();diag=mode!='off'
 binary=T/(arm+('.diag.test' if diag else '.test'))
 identity=json.loads((E/(arm+('-diagnostic.json' if diag else '-runner.json'))).read_text());assert sha(binary)==identity['binary_sha256']
 local=dict(env,TMPDIR=str(scratch),MODELCASE_TRACE=str(d/'trace.json'))
 if diag:local.update(ISSUE88_SAMPLE_PHASES='1',ISSUE68_CAPTURE='1',ISSUE68_CONTROL='1' if mode=='control' else '0',ISSUE68_CAPTURE_DIR=str(d/'captures'),SAMPLE_PHASES_OUT=str(d/'sql.json'))
 guard.check();start=time.monotonic()
 with (d/'console.txt').open('w') as f:
  p=subprocess.run(['/usr/bin/time','-l',binary,'-test.parallel=8','-test.timeout=140s','-test.count=1'],cwd=T/arm/'tests/timer_calibration/runner',env=local,stdout=f,stderr=subprocess.STDOUT,timeout=150)
 elapsed=(time.monotonic()-start)*1000;guard.check()
 assert p.returncode==0,(name,(d/'console.txt').read_text()[-3000:])
 trace=json.loads((d/'trace.json').read_text());m=trace['meta'];spans=trace['spans']
 for k,v in {'read_cases':'50','write_cases':'20','test_exit':'0','parallel':'8','fork_cap':'9','active_mappings_after':'0','innodb_buffer_pool_size':'16777216','innodb_read_io_threads':'1'}.items():assert m[k]==v,(name,k,m)
 for k,n in [('fork',21),('sample',21),('read',50),('write',20)]:assert sum(s['kind']==k for s in spans)==n
 assert not list(scratch.iterdir()),name
 r={'name':name,'arm':arm,'mode':mode,'repeat':repeat,'process_wall_ms':elapsed,'rss_bytes':int(re.search(r'(?m)^\s*(\d+)\s+maximum resident set size$',(d/'console.txt').read_text()).group(1)),'trace':trace,'exit_code':p.returncode,'scratch_empty':True,'captures':[]}
 if diag:
  r['loaders']=json.loads((d/'sql.json').read_text());assert len(r['loaders'])==21
  for rec in r['loaders']:
   dd=rec['durations_us'];assert len(dd['prepare'])==3 and len(dd['order_insert'])==40 and len(dd['item_insert'])==len(dd['stock_update'])==100 and len(dd['commit'])==1
  for cp in sorted((d/'captures').glob('capture-*.json')):
   c=json.loads(cp.read_text());pp=d/'captures'/c['profile_file'];text=pp.read_text();assert len(text.encode())==c['bytes'];c['usable']=usable(c,text);c['profile_sha256']=sha(pp);c['matching_db_blocks']=len(blocks(text,c['db_id']));r['captures'].append(c)
   if c['usable']:
    out=E/(name+'-profile.txt');out.write_text(text);c['retained_profile']=out.name
  assert len(r['captures'])<=1
  if mode=='control':
   assert len(r['captures'])==1 and r['captures'][0]['usable'] and r['captures'][0]['phase']=='positive_control'
   c=r['captures'][0];text=(E/c['retained_profile']).read_text()
   for changed in [{'db_id':'nonexistent-db'},{'snapshot_begin_us':c['call_return_us']+1},{'truncated':True}]:assert not usable(dict(c,**changed),text)
   assert not usable(c,'no guest stacks')
 r['accepted']=True;records.append(r);dump(E/'observations.json',records)
 print(name,'PASS',round(trace['elapsed_ms'],3),'long sample',sum(s['kind']=='sample' and s['end_ms']-s['start_ms']>100 for s in spans),'captures',[(c['phase'],c['operation_ordinal'],c['usable']) for c in r['captures']],flush=True)

host={'platform':platform.platform(),'cpu':subprocess.check_output(['sysctl','-n','machdep.cpu.brand_string'],text=True).strip(),'memory_bytes':int(subprocess.check_output(['sysctl','-n','hw.memsize'],text=True)),'source_commit':source,'plan':plan}
dump(E/'host.json',host)
try:
 # Validate attribution before natural sampling; controls are separate from metrics.
 for arm in ['baseline','candidate']:execute(arm,'control',0)
 for repeat in range(-1,10):
  for arm in (['baseline','candidate'] if repeat%2==0 else ['candidate','baseline']):execute(arm,'off',repeat)
 for repeat in range(4):
  for arm in (['candidate','baseline'] if repeat%2==0 else ['baseline','candidate']):execute(arm,'diagnostic',repeat)
finally:
 dump(E/'observations.json',records)
 dump(E/'completion.json',{'result':'COMPLETE' if len(records)==32 and all(r['accepted'] for r in records) else 'INCOMPLETE','processes':len(records),'measurement_retries':0,'adoption':False})
