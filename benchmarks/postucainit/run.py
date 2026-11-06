from pathlib import Path
import subprocess,sys,json,hashlib,os,time,platform,resource,tarfile
s=Path(__file__).resolve().parents[2];w=s.parent;t=w/'temp';e=w/'evidence';b=Path(__file__).resolve().parent
sys.path.insert(0,str(s/'scripts'))
from experiment_disk import DiskGuard
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
inputs=json.loads((e/'inputs.json').read_text());plan=json.loads((b/'plan.json').read_text())
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=s,text=True).strip()==inputs['harness_source_commit']
assert not subprocess.check_output(['git','status','--porcelain'],cwd=s)
assert sha(b/'plan.json')==inputs['plan_sha256'];assert sha(t/'probe')==inputs['binary_sha256']
env={k:v for k,v in os.environ.items() if not k.startswith(('GO','MARIAMEM_','MYSQLMEM_','UPDATE_','ISSUE','FORKSTAGES_','PYTEST'))}
env.update(GOMAXPROCS='8',GOGC='100')
(e/'host.json').write_text(json.dumps({'platform':platform.platform(),'cpu':subprocess.check_output(['sysctl','-n','machdep.cpu.brand_string'],text=True).strip(),'memory_bytes':int(subprocess.check_output(['sysctl','-n','hw.memsize'],text=True))},indent=2)+'\n')
guard=DiskGuard(w,12,8);records=[]
def run(mode,p,rep,kind='primary',count=48,negative=False):
 name=f'{mode}-p{p}-r{rep}-{kind}';out=e/(name+'.json');assert not out.exists(),name
 scratch=t/'scratch'/name;scratch.mkdir();v=dict(env,TMPDIR=str(scratch));trace=t/'trace'/name
 if mode=='on':
  trace.mkdir(parents=True);v['MARIAMEM_TIMING_DIR']=str(trace);v['UPDATE_NOTIFY_DIR']=str(trace/'undo');(trace/'undo').mkdir()
 command=[str(t/'probe'),'-mode','fork','-parallel',str(p),'-count',str(count),'-out',str(out)]+(['-corrupt-seed'] if negative else [])
 guard.check();before=resource.getrusage(resource.RUSAGE_CHILDREN);at=time.monotonic()
 with (e/(name+'.txt')).open('w') as log:code=subprocess.run(command,cwd=b,env=v,stdout=log,stderr=subprocess.STDOUT,timeout=190).returncode
 after=resource.getrusage(resource.RUSAGE_CHILDREN)
 rec={'name':name,'mode':mode,'parallel':p,'rep':rep,'kind':kind,'negative':negative,'count':count,'exit_code':code,'process_wall_ms':(time.monotonic()-at)*1000,'process_cpu_ms':((after.ru_utime+after.ru_stime)-(before.ru_utime+before.ru_stime))*1000}
 r=json.loads(out.read_text());rec['report']=r
 assert r['cleanup'] and not list(scratch.iterdir()),(name,'cleanup')
 assert r['mode']=='fork' and r['parallel']==p and r['count']==count and r['gomaxprocs']==8
 assert 0<r['max_active']<=p and r['resolved_max_forks']==p
 assert all(r['cleanup_stats'][k]==0 for k in ['active_mappings','active_rw_bytes','active_reserved_bytes','release_failures','grow_failures'])
 if negative:assert code==1 and not r['success'] and 'pristine oracle' in r['error'],(name,code,r)
 else:
  assert code==0 and r['success'] and len(r['samples'])==count,(name,code,r)
  assert {x['index'] for x in r['samples']}==set(range(count))
  assert all(x['oracle'] and x['cleanup'] and not x.get('error') for x in r['samples'])
  assert '12.3.3' in r['samples'][0]['version']
 if mode=='on':
  traces={}
  for child in range(count):
   traces[str(child)]={}
   for op in ['fork','api_startup','startup']:
    path=trace/f'child-{child:03d}-{op}.json';j=json.loads(path.read_text());traces[str(child)][op]=j
   g=traces[str(child)]['startup']['guest'];init=g['initialization'];assert init['dropped_records']==0
   names=[a['name'] for a in init['events']];assert 'embedded_begin' in names and 'embedded_complete' in names and 'innodb_plugin_begin' in names and 'innodb_background_complete' in names,names
   assert all(not a['name'].endswith('.failed') for a in init['events'])
  rec['traces']=traces
  uf=list((trace/'undo').glob('*.json'));assert len(uf)==count
  for f in uf:assert not json.loads(f.read_text())['truncated']
  with tarfile.open(e/(name+'-undo.tar.gz'),'w:gz') as z:
   for f in sorted(uf):z.add(f,arcname=f.name)
 records.append(rec);(e/'observations.json').write_text(json.dumps(records,indent=2)+'\n')
 guard.check();print(name,'expected FAIL' if negative else 'PASS','suite',round(r['suite_ms'],2),flush=True)
run('on',4,-2,'pilot',4)
run('on',1,-2,'negative',1,True)
for p in [1,4]:
 for mode in ['off','on']:run(mode,p,-1,'warmup')
for rep in range(3):
 for p in ([1,4] if rep%2==0 else [4,1]):
  modes=['off','on'] if (rep+([1,4].index(p)))%2==0 else ['on','off']
  for mode in modes:run(mode,p,rep)
assert len(records)==18
(e/'completion.json').write_text(json.dumps({'result':'COLLECTED','total_processes':18,'primary_processes':12,'extra_repetitions':0,'harness_source_commit':inputs['harness_source_commit'],'peak_workspace_bytes':guard.peak,'minimum_free_bytes':guard.minimum_free},indent=2)+'\n')
