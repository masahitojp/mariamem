from pathlib import Path
import hashlib,json,os,platform,subprocess,time,gzip,sys,datetime
W=Path(__file__).resolve().parents[1];E=W/'evidence';S=W/'worktree'
roots={'baseline':W.parent/'timer-measure-baseline','candidate':W}
records=[]
env={k:v for k,v in os.environ.items() if not k.startswith(('GO','MARIAMEM_','MYSQLMEM_','LC_STAGE_','LEXER_','CLOSE_DIAG_','ISSUE','MODELCASE_','SAMPLE_DIAG','FORK_STAGE','SHOP_','TIMER_','ANALYZE_'))}
env.update(GOMAXPROCS='8',GOGC='100',ISSUE88_POOL_MIB='16',FORK_STAGES='0')
source=subprocess.check_output(['git','rev-parse','HEAD'],cwd=S,text=True).strip()
assert not subprocess.check_output(['git','status','--porcelain'],cwd=S)
for arm,A in roots.items():
 identity=json.loads((E/(arm+'-runner.json')).read_text());assert identity['harness_source_commit']==source
 assert hashlib.sha256((A/'temp/shop.test').read_bytes()).hexdigest()==identity['binary_sha256']
 assert json.loads((E/(arm+'-oracle.json')).read_text())['result']=='PASS'
(E/'host.json').write_text(json.dumps({'platform':platform.platform(),'cpu':subprocess.check_output(['sysctl','-n','machdep.cpu.brand_string'],text=True).strip(),'memory_bytes':int(subprocess.check_output(['sysctl','-n','hw.memsize'],text=True)),'GOMAXPROCS':8,'GOGC':100,'go':'1.26.10','harness_source_commit':source},indent=2)+'\n')
def save():
 data=json.dumps(records,sort_keys=True,separators=(',',':')).encode()
 (E/'observations.json.gz').write_bytes(gzip.compress(data,mtime=0))
def execute(arm,kind,repeat,parallel):
 A=roots[arm];T=A/'temp';name=f'{kind}-p{parallel}-r{repeat}-{arm}';scratch=T/name;scratch.mkdir()
 out=T/(name+'.json');local=dict(env,TMPDIR=str(scratch),SHOP_PARALLEL=str(parallel),MODELCASE_TRACE=str(out))
 if kind=='lifecycle':local['TIMER_LIFECYCLE']='1'
 if kind=='analyze':local.update(TIMER_ANALYZE_PROBE='1',ANALYZE_PROBE_PATH=str(out))
 timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat()
 before=time.monotonic()
 with (T/(name+'.log')).open('w') as log:
  p=subprocess.run([str(T/'shop.test'),f'-test.parallel={parallel}','-test.timeout=140s','-test.count=1'],cwd=T/'runtime/product/tests/timer_calibration/runner',env=local,stdout=log,stderr=subprocess.STDOUT,timeout=150)
 data=json.loads(out.read_text()) if out.exists() else None
 record={'started_at_utc':timestamp,'arm':arm,'kind':kind,'repeat':repeat,'parallel':parallel,'process_wall_ms':(time.monotonic()-before)*1000,'exit_code':p.returncode,'scratch_empty':not list(scratch.iterdir()),'data':data}
 if kind=='analyze':
  (E/(arm+'-pipe-analyze.json')).write_text(json.dumps(record,indent=2)+'\n')
 else:records.append(record);save()
 assert p.returncode==0 and data and record['scratch_empty'], (name,(T/(name+'.log')).read_text()[-3000:])
 if kind=='analyze':
  assert data['subsequent_select']=='PASS' and data['active_mappings_after']==0
  assert len(data['rows'])==6
  for row in data['rows']:
   assert 'error' not in row
   q=json.loads(row['raw'])['query_block'];table=q['nested_loop'][0]['table']
   assert table['r_rows']==2 and table['r_loops']==1
   if row['delay']:assert 18<=q['r_total_time_ms']<=row['wall_ms']+5
 elif kind=='lifecycle':
  assert data['result']=='PASS' and data['active_mappings_after']==0
  assert [v['kind'] for v in data['observations']].count('fresh')==8
  assert [v['kind'] for v in data['observations']].count('fork')==16
 else:
  meta=data['meta'];spans=data['spans']
  for key,value in {'read_cases':'50','write_cases':'20','test_exit':'0','parallel':str(parallel),'fork_cap':str(parallel+1),'active_mappings_after':'0','innodb_buffer_pool_size':'16777216','innodb_read_io_threads':'1'}.items():assert meta[key]==value,(name,key,meta)
  for key,n in [('read',50),('write',20),('fork',21),('sample',21)]:assert sum(v['kind']==key for v in spans)==n
 record['accepted']=True
 if kind!='analyze':save()
 print(name,'PASS',round(data.get('elapsed_ms',record['process_wall_ms']),3),flush=True)
try:
 # Correctness on the exact Go Pipe benchmark route precedes all timed pairs.
 for arm in roots:execute(arm,'analyze',0,4)
 for repeat in range(-1,6):
  for arm in (['baseline','candidate'] if repeat%2==0 else ['candidate','baseline']):execute(arm,'lifecycle',repeat,4)
 for repeat in range(-1,5):
  for parallel in ([4,8] if repeat%2==0 else [8,4]):
   for arm in (['baseline','candidate'] if (repeat+parallel//4)%2==0 else ['candidate','baseline']):execute(arm,'shop',repeat,parallel)
finally:
 save()
 (E/'completion.json').write_text(json.dumps({'result':'COMPLETE' if len(records)==38 and all(r.get('accepted') for r in records) else 'INCOMPLETE','processes':len(records),'retries':0,'qualification':False},indent=2)+'\n')
