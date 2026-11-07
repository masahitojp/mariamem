from pathlib import Path
import subprocess,sys,os,json,hashlib,time,platform
s=Path(__file__).resolve().parents[2];w=s.parent;t=w/'temp';e=w/'evidence';b=Path(__file__).resolve().parent
sys.path.insert(0,str(s/'scripts'))
from experiment_disk import DiskGuard,run_guarded
i=json.loads((e/'inputs.json').read_text())
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=s,text=True).strip()==i['source_commit']
assert not subprocess.check_output(['git','status','--porcelain'],cwd=s)
for v,x in i['binaries'].items():assert hashlib.sha256((t/v).read_bytes()).hexdigest()==x['sha256']
env={k:v for k,v in os.environ.items() if not k.startswith(('GO','MARIAMEM_','MYSQLMEM_','UPDATE_','LP_'))};env.update(GOMAXPROCS='8',GOGC='100')
(e/'host.json').write_text(json.dumps({'platform':platform.platform(),'cpu':subprocess.check_output(['sysctl','-n','machdep.cpu.brand_string'],text=True).strip(),'memory':int(subprocess.check_output(['sysctl','-n','hw.memsize'],text=True))},indent=2)+'\n')
guard=DiskGuard(w,12,6);records=[]
def run(arm,mode,p,rep,kind='primary',count=48,negative=False):
 name=f'{arm}-{mode}-p{p}-r{rep}-{kind}';out=e/(name+'.json');assert not out.exists()
 scratch=t/'scratch'/name;scratch.mkdir()
 v=dict(env,LP_MODE=arm,TMPDIR=str(scratch));variant='diagnostic' if kind=='diagnostic' else 'normal'
 if kind=='control':v['LP_SQL']='1'
 traces=[]
 if kind=='diagnostic':
  trace=t/'traces'/name;trace.mkdir(parents=True);v['UPDATE_NOTIFY_DIR']=str(trace)
 command=[str(t/variant),'-mode',mode,'-parallel',str(p),'-count',str(count),'-out',str(out)]+(['-corrupt-seed'] if negative else [])
 with (e/(name+'.txt')).open('w') as log:
  code=run_guarded(command,guard,cwd=b,env=v,output=log,timeout=190)
 r=json.loads(out.read_text())
 if negative:assert code==1 and not r['success'] and 'pristine oracle' in r['error']
 else:assert code==0 and r['success'] and len(r['samples'])==count,(name,code,r.get('error'))
 assert r['cleanup'] and not list(scratch.iterdir())
 c=r['cleanup_stats'];assert all(c[k]==0 for k in ['active_mappings','active_rw_bytes','active_reserved_bytes','release_failures'])
 n=count+(mode=='fork')
 assert c['lp_copies']==(0 if arm=='original' else n)
 assert c['lp_original']==(638*n if arm=='original' else 0)
 assert c['lp_hits']==(0 if arm=='original' else 638*n)
 assert c['lp_verified']==(638*n if arm=='verify' else 0)
 assert c['lp_fallback']==c['lp_unknown_verified']==(n if arm=='verify' else 0)
 assert r['resolved_max_forks']==(p if mode=='fork' else 0)
 if kind=='control':assert r['lexer_sql_checks']>=count
 if not negative:assert all(x['oracle'] and x['cleanup'] and not x.get('error') for x in r['samples'])
 if kind=='diagnostic':
  for path in sorted(trace.glob('*.json')):
   tr=json.loads(path.read_text());assert not tr['truncated']
   dest=name+'-undo-'+path.name;(e/dest).write_bytes(path.read_bytes());traces.append(dest)
  assert len(traces)==count
 records.append({'arm':arm,'mode':mode,'parallel':p,'rep':rep,'kind':kind,'count':count,'negative':negative,'report':out.name,'exit_code':code,'trace_reports':traces})
 (e/'records.json').write_text(json.dumps(records,indent=2)+'\n')
 print(name,'expected FAIL' if negative else 'PASS',round(r['suite_ms'],2),flush=True)
for arm in ['original','verify']:
 for mode in ['fresh','fork']:run(arm,mode,1,0,'control',2)
for arm in ['original','prepared']:run(arm,'fork',1,0,'negative',1,True)
cells=[('fresh',1),('fork',1),('fresh',4),('fork',4)]
for mode,p in cells:
 for arm in ['original','prepared']:run(arm,mode,p,-1,'warmup')
for rep in range(5):
 for mode,p in cells[rep%4:]+cells[:rep%4]:
  arms=['original','prepared'] if (rep+cells.index((mode,p)))%2==0 else ['prepared','original']
  for arm in arms:run(arm,mode,p,rep)
for arm in ['original','prepared']:run(arm,'fork',4,0,'diagnostic')
assert len(records)==56
(e/'completion.json').write_text(json.dumps({'result':'COLLECTED','processes':56,'primary_processes':40,'primary_children':1920,'extra_trials':0,'source_commit':i['source_commit']},indent=2)+'\n')
