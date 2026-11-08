"""Fixed finite paired campaign; all observations retained, no adaptive reruns."""
from pathlib import Path
import hashlib,json,os,platform,subprocess,sys
S=Path(__file__).resolve().parents[2];W=S.parent;T=W/'temp';E=W/'evidence';B=Path(__file__).resolve().parent
sys.path.insert(0,str(S/'scripts'))
from experiment_disk import DiskGuard,run_guarded
from git_identity import require_commit
P=json.loads((B/'plan.json').read_text());I=json.loads((E/'inputs.json').read_text());require_commit(S,I['source_commit'])
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=S,text=True).strip()==I['source_commit']
assert not subprocess.check_output(['git','status','--porcelain'],cwd=S)
assert all(hashlib.sha256((T/k).read_bytes()).hexdigest()==v['sha256'] for k,v in I['binaries'].items())
env={k:v for k,v in os.environ.items() if not k.startswith(('GO','MARIAMEM_','MYSQLMEM_','UPDATE_','LP_','LC_'))};env.update(GOMAXPROCS='8',GOGC='100')
(E/'host.json').write_text(json.dumps({'platform':platform.platform(),'cpu':subprocess.check_output(['sysctl','-n','machdep.cpu.brand_string'],text=True).strip(),'memory':int(subprocess.check_output(['sysctl','-n','hw.memsize'],text=True))},indent=2)+'\n')
guard=DiskGuard(W,P['min_free_gib'],P['budget_gib']);records=[]
def run(arm,mode,p,obs,rep,kind='primary',count=48,negative=False):
 name=f'{arm}-{mode}-p{p}-{obs}-r{rep}-{kind}';out=E/(name+'.json');assert not out.exists()
 scratch=T/'scratch'/name;scratch.mkdir();v=dict(env,TMPDIR=str(scratch));traces={}
 if kind=='control':v['LP_SQL']='1'
 if obs=='on':
  stage=T/'stages'/name;stage.mkdir(parents=True);generic=stage/'generic';generic.mkdir();v.update(LC_STAGE_DIR=str(stage),MARIAMEM_TIMING_DIR=str(generic))
 command=[str(T/(arm+'-'+obs)),'-mode',mode,'-parallel',str(p),'-count',str(count),'-out',str(out)]+(['-corrupt-seed'] if negative else [])
 with (E/(name+'.txt')).open('w') as log:code=run_guarded(command,guard,cwd=B,env=v,output=log,timeout=P['process_timeout_seconds'])
 r=json.loads(out.read_text())
 if negative:assert code==1 and not r['success'] and 'pristine oracle' in r['error']
 else:assert code==0 and r['success'] and len(r['samples'])==count,(name,code,r.get('error'))
 assert r['cleanup'] and not list(scratch.iterdir())
 assert all(r['cleanup_stats'][k]==0 for k in ['active_mappings','active_rw_bytes','active_reserved_bytes','release_failures'])
 if mode=='fork':assert r['resolved_max_forks']==p
 if kind=='control':assert r['lexer_sql_checks']>=count
 if not negative:assert all(x['oracle'] and x['cleanup'] and not x.get('error') for x in r['samples'])
 if obs=='on':
  for i in range(count):
   traces[str(i)]={op:json.loads((stage/f'child-{i:03d}-{op}.json').read_text()) for op in ['fork','api_startup','startup']}
   assert 'guest' in traces[str(i)]['startup']
 record={'arm':arm,'mode':mode,'parallel':p,'observer':obs,'rep':rep,'kind':kind,'negative':negative,'exit_code':code,'report':r,'traces':traces};records.append(record)
 (E/'observations.json').write_text(json.dumps(records,separators=(',',':'))+'\n')
 print(name,'expected FAIL' if negative else 'PASS',round(r['suite_ms'],2),flush=True)
for arm in P['arms']:
 run(arm,'fork',1,'off',0,'control',2)
 run(arm,'fork',1,'off',0,'negative',1,True)
cells=[tuple(c) for c in P['primary_cells']]
for mode,p,obs in cells:
 for arm in P['arms']:run(arm,mode,p,obs,-1,'warmup')
for rep in range(P['repetitions']):
 for mode,p,obs in cells[rep:]+cells[:rep]:
  arms=P['arms'] if (rep+cells.index((mode,p,obs)))%2==0 else list(reversed(P['arms']))
  for arm in arms:run(arm,mode,p,obs,rep)
assert len(records)==P['total_processes']
(E/'completion.json').write_text(json.dumps({'result':'COLLECTED','source_commit':I['source_commit'],'processes':len(records),'primary_processes':P['primary_processes'],'primary_children':P['primary_processes']*P['children'],'extra_trials':0,'budget':{'peak_bytes':guard.peak,'min_free_bytes':guard.minimum_free}},indent=2)+'\n')
