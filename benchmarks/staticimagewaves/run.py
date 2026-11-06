from pathlib import Path
import os,sys,json,subprocess,hashlib,time,resource,platform,tarfile
s=Path(__file__).resolve().parents[2];w=s.parent;t=w/'temp';e=w/'evidence';b=Path(__file__).resolve().parent
sys.path.insert(0,str(s/'scripts'))
from experiment_disk import DiskGuard,run_guarded
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
inputs=json.loads((e/'inputs.json').read_text());plan=json.loads((b/'plan.json').read_text())
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=s,text=True).strip()==inputs['source_commit']
assert not subprocess.check_output(['git','status','--porcelain'],cwd=s)
assert sha(b/'plan.json')==inputs['plan_sha256']
for name,meta in inputs['binaries'].items():assert sha(t/name)==meta['sha256']
env={k:v for k,v in os.environ.items() if not k.startswith(('GO','MARIAMEM_','MYSQLMEM_','UPDATE_','ISSUE','FORKSTAGES_'))};env.update(GOMAXPROCS='8',GOGC='100')
(e/'host.json').write_text(json.dumps({'platform':platform.platform(),'cpu':subprocess.check_output(['sysctl','-n','machdep.cpu.brand_string'],text=True).strip(),'memory_bytes':int(subprocess.check_output(['sysctl','-n','hw.memsize'],text=True))},indent=2)+'\n')
guard=DiskGuard(w,12,8);records=[];deadline=time.monotonic()+600
def run(arm,p,rep,kind,count=48):
 name=f'{arm}-p{p}-r{rep}-{kind}';out=e/(name+'.json');assert not out.exists(),name
 scratch=t/'scratch'/name;scratch.mkdir();v=dict(env,TMPDIR=str(scratch),MARIAMEM_STATIC_IMAGE_EXPERIMENT='1' if arm=='pages' else '0',MARIAMEM_STATIC_IMAGE_PAGES='1' if arm=='pages' else '0')
 variant='diagnostic' if kind=='diagnostic' else 'ordinary'
 if kind=='diagnostic':
  trace=t/'trace'/name;trace.mkdir();v['UPDATE_NOTIFY_DIR']=str(trace)
  timing=t/'trace'/(name+'-timing');timing.mkdir();v['MARIAMEM_TIMING_DIR']=str(timing)
 command=[str(t/variant),'-fixed-waves','-mode','fork','-parallel',str(p),'-count',str(count),'-out',str(out)]
 if kind=='negative':command+=['-corrupt-seed']
 if kind=='pilot':command+=['-semantic']
 if kind=='memory':command+=['-held']
 assert time.monotonic()<deadline,'campaign deadline';guard.check();before=resource.getrusage(resource.RUSAGE_CHILDREN);at=time.monotonic()
 with (e/(name+'.log')).open('w') as log:code=run_guarded(command,guard,cwd=b,env=v,output=log,timeout=min(190,max(1,deadline-time.monotonic())))
 after=resource.getrusage(resource.RUSAGE_CHILDREN)
 rec={'name':name,'arm':arm,'parallel':p,'rep':rep,'kind':kind,'count':count,'report':out.name,'exit_code':code,'external_guarded_ms':(time.monotonic()-at)*1000,'process_cpu_ms':((after.ru_utime+after.ru_stime)-(before.ru_utime+before.ru_stime))*1000}
 records.append(rec);(e/'records.json').write_text(json.dumps(records,indent=2)+'\n')
 assert out.exists(),(name,code)
 r=json.loads(out.read_text());assert r['cleanup'] and not list(scratch.iterdir()),(name,'cleanup')
 assert all(r['cleanup_stats'][k]==0 for k in ['active_mappings','active_rw_bytes','active_reserved_bytes','release_failures'])
 assert r['image_after_close']['owned_fds']==0 and r['image_after_close']['closed']
 assert r['image_before_close']['page_only']==(arm=='pages')
 assert r['image_before_close']['enabled']==(arm=='pages')
 assert r['image_before_close']['builds']==(1 if arm=='pages' else 0)
 assert r['image_before_close']['acquires']==((1+(p if kind=='memory' else len(r['samples']))) if arm=='pages' else 0)
 assert r['resolved_max_forks']==p and r['gomaxprocs']==8
 assert r['fixed_waves'] and len(r['waves'])==((len(r['samples'])+p-1)//p)
 last_end=0
 for wave in r['waves']:
  samples=[s for s in r['samples'] if s['index']//p==wave['index']];assert len(samples)==p
  assert last_end<=wave['begin_ms']<=wave['forks_begin_ms']<=wave['all_ready_ms']<=wave['end_ms']
  for sample in samples:
   spans={x['name']:x for x in sample['spans']}
   assert wave['forks_begin_ms']<=spans['start_or_fork']['begin_ms']<=spans['start_or_fork']['end_ms']<=wave['all_ready_ms']
   assert spans['connect']['begin_ms']>=wave['all_ready_ms'] and sample['end_ms']<=wave['end_ms']
  last_end=wave['end_ms']
 if kind=='negative':assert code==1 and not r['success'] and 'pristine oracle' in r['error'],(name,code,r)
 else:
  assert code==0 and r['success'],(name,code,r)
  if kind=='memory':assert [x['stage'] for x in r['memory']]==['before_root','baseline','held_ready','held_after_sql','after_children_close']
  else:
   assert len(r['samples'])==count and 0<r['max_active']<=p
   assert {x['index'] for x in r['samples']}==set(range(count))
   assert all(x['oracle'] and x['cleanup'] and not x.get('error') for x in r['samples'])
   assert '12.3.3' in r['samples'][0]['version']
 if kind=='diagnostic':
  for sample in r['samples']:
   assert set(sample['traces'])=={'fork','api_startup','startup'} and sample['traces']['startup'].get('guest')
  timing_reports={p.name:json.loads(p.read_text()) for p in timing.glob('*.json')}
  (e/(name+'-timing.json')).write_text(json.dumps(timing_reports,separators=(',',':'))+'\n')
  paths=sorted(trace.glob('*.json'));assert len(paths)==count,(name,len(paths))
  meta=[]
  for path in paths:
   j=json.loads(path.read_text());assert not j['truncated'];meta.append({'file':path.name,'sha256':sha(path),'bytes':path.stat().st_size})
  archive=e/(name+'-owner-traces.tar.gz')
  with tarfile.open(archive,'w:gz') as z:
   for path in paths:z.add(path,arcname=path.name)
  rec['owner_archive']={'file':archive.name,'sha256':sha(archive),'members':meta}
  (e/'records.json').write_text(json.dumps(records,indent=2)+'\n')
 print(name,'expected FAIL' if kind=='negative' else 'PASS',round(r['suite_ms'],2),flush=True)
for arm in ['anonymous','pages']:
 run(arm,4,-2,'pilot',4);run(arm,4,-2,'negative',4)
for arm in ['anonymous','pages']:run(arm,4,-1,'warmup')
for rep in range(5):
 for arm in (['anonymous','pages'] if rep%2==0 else ['pages','anonymous']):run(arm,4,rep,'primary')
for arm in ['pages','anonymous']:run(arm,4,0,'diagnostic')
assert len(records)==18
(e/'collected.json').write_text(json.dumps({'result':'COLLECTED','processes':18,'primary_processes':10,'diagnostic_processes':2,'extra_repetitions':0,'source_commit':inputs['source_commit'],'peak_owned_bytes':guard.peak,'minimum_free_bytes':guard.minimum_free},indent=2)+'\n')
