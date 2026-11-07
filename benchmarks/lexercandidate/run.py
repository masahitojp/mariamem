from pathlib import Path
import subprocess,sys,os,json,hashlib,platform
s=Path(__file__).resolve().parents[2];w=s.parent;t=w/'temp';e=w/'evidence';b=Path(__file__).resolve().parent
sys.path.insert(0,str(s/'scripts'))
from experiment_disk import DiskGuard,run_guarded
from git_identity import require_commit
inp=json.loads((e/'inputs.json').read_text());require_commit(s,inp['source_commit'])
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=s,text=True).strip()==inp['source_commit']
assert not subprocess.check_output(['git','status','--porcelain'],cwd=s)
assert hashlib.sha256((t/'diagnostic').read_bytes()).hexdigest()==inp['binaries']['diagnostic']['sha256']
env={k:v for k,v in os.environ.items() if not k.startswith(('GO','MARIAMEM_','MYSQLMEM_','UPDATE_','LP_','LC_'))};env.update(GOMAXPROCS='8',GOGC='100')
(e/'host.json').write_text(json.dumps({'platform':platform.platform(),'cpu':subprocess.check_output(['sysctl','-n','machdep.cpu.brand_string'],text=True).strip(),'memory':int(subprocess.check_output(['sysctl','-n','hw.memsize'],text=True))},indent=2)+'\n')
guard=DiskGuard(w,12,10);records=[]
def run(arm,p,obs,rep,kind='primary',count=48,negative=False):
 name=f'{arm}-p{p}-{obs}-r{rep}-{kind}';out=e/(name+'.json');assert not out.exists()
 scratch=t/'scratch'/name;scratch.mkdir();v=dict(env,LP_MODE=arm,TMPDIR=str(scratch));traces={};undo=[]
 if kind=='control':v['LP_SQL']='1'
 if kind=='inventory':v['LC_INPUT_PATH']=str(e/'producer-inputs.json')
 if obs=='on':
  stage=t/'stages'/name;stage.mkdir(parents=True);generic=stage/'generic';generic.mkdir();v.update(LC_STAGE_DIR=str(stage),MARIAMEM_TIMING_DIR=str(generic))
  trace=t/'traces'/name;trace.mkdir(parents=True);v['UPDATE_NOTIFY_DIR']=str(trace)
 command=[str(t/'diagnostic'),'-mode','fork','-parallel',str(p),'-count',str(count),'-out',str(out)]+(['-corrupt-seed'] if negative else [])
 with (e/(name+'.txt')).open('w') as log:code=run_guarded(command,guard,cwd=b,env=v,output=log,timeout=190)
 r=json.loads(out.read_text())
 if negative:assert code==1 and not r['success'] and 'pristine oracle' in r['error']
 else:assert code==0 and r['success'] and len(r['samples'])==count,(name,code,r.get('error'))
 assert r['cleanup'] and not list(scratch.iterdir())
 c=r['cleanup_stats'];assert all(c[k]==0 for k in ['active_mappings','active_rw_bytes','active_reserved_bytes','release_failures'])
 n=count+1;assert c['lp_copies']==(0 if arm=='original' else n)
 assert c['lp_original']==(638*n if arm=='original' else 0)
 assert c['lp_hits']==(0 if arm=='original' else 638*n)
 assert c['lp_verified']==(638*n if arm=='verify' else 0)
 assert r['resolved_max_forks']==p
 if kind=='control':assert r['lexer_sql_checks']>=count
 if not negative:assert all(x['oracle'] and x['cleanup'] and not x.get('error') for x in r['samples'])
 if obs=='on':
  for i in range(count):
   traces[str(i)]={op:json.loads((stage/f'child-{i:03d}-{op}.json').read_text()) for op in ['fork','api_startup','startup']}
   assert 'guest' in traces[str(i)]['startup']
  for path in sorted(trace.glob('*.json')):
   tr=json.loads(path.read_text());assert not tr['truncated'];dest=name+'-undo-'+path.name;(e/dest).write_bytes(path.read_bytes());undo.append(dest)
  assert len(undo)==count
 rec={'arm':arm,'parallel':p,'observer':obs,'rep':rep,'kind':kind,'count':count,'negative':negative,'exit_code':code,'report':r,'traces':traces,'undo_files':undo}
 records.append(rec);(e/'observations.json').write_text(json.dumps(records,indent=2)+'\n')
 print(name,'expected FAIL' if negative else 'PASS',round(r['suite_ms'],2),flush=True)
run('original',1,'off',0,'inventory',1)
assert len(json.loads((e/'producer-inputs.json').read_text()))==638
for arm in ['original','verify']:run(arm,1,'off',0,'control',2)
for arm in ['original','prepared']:run(arm,1,'off',0,'negative',1,True)
cells=[(1,'off'),(1,'on'),(4,'off'),(4,'on')]
for p,obs in cells:
 for arm in ['original','prepared']:run(arm,p,obs,-1,'warmup')
for rep in range(3):
 for p,obs in cells[rep:]+cells[:rep]:
  arms=['original','prepared'] if (rep+cells.index((p,obs)))%2==0 else ['prepared','original']
  for arm in arms:run(arm,p,obs,rep)
assert len(records)==37
(e/'completion.json').write_text(json.dumps({'result':'COLLECTED','processes':37,'primary_processes':24,'primary_children':1152,'extra_trials':0,'source_commit':inp['source_commit'],'budget':{'peak_bytes':guard.peak,'min_free_bytes':guard.minimum_free}},indent=2)+'\n')
