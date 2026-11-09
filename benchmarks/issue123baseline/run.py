from pathlib import Path
import subprocess,sys,json,hashlib,os,time,platform
s=Path(__file__).resolve().parents[2];w=s.parent;t=w/'temp';e=w/'evidence';b=Path(__file__).resolve().parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
inputs=json.loads((e/'inputs.json').read_text());plan=json.loads((b/'plan.json').read_text())
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=s,text=True).strip()==inputs['harness_and_candidate_source_commit']
assert not subprocess.check_output(['git','status','--porcelain'],cwd=s)
for v,i in inputs['binaries'].items():assert sha(t/('bin-'+v))==i['sha256']
env={k:v for k,v in os.environ.items() if not k.startswith(('GO','MARIAMEM_','MYSQLMEM_','UPDATE_','ISSUE','FORKSTAGES_','LEXER_','PYTEST'))};env.update(GOMAXPROCS='8',GOGC='100')
(e/'host.json').write_text(json.dumps({'platform':platform.platform(),'cpu':subprocess.check_output(['sysctl','-n','machdep.cpu.brand_string'],text=True).strip(),'memory_bytes':int(subprocess.check_output(['sysctl','-n','hw.memsize'],text=True))},indent=2)+'\n')
# Record potential competing processes before primary timing; not a performance exclusion rule.
ps=subprocess.check_output(['ps','-axo','pid,etime,%cpu,command'],text=True)
(e/'process-preflight.txt').write_text('\n'.join(line.replace(str(w),'<WORKSPACE>') for line in ps.splitlines() if any(x in line for x in ('/compile ', 'go build', 'go test', 'experiment_workspace.py', 'campaign.py', 'build.py', 'run.py')))+'\n')
records=[]
def run(variant,mode,p,rep,kind='primary',count=48,negative=False):
 name=f'{variant}-{mode}-p{p}-r{rep}-{kind}';out=e/(name+'.json');assert not out.exists()
 scratch=t/'scratch'/name;scratch.mkdir();v=dict(env,TMPDIR=str(scratch))
 if variant=='pages':v['MARIAMEM_STATIC_IMAGE_EXPERIMENT']='1'
 cmd=[str(t/('bin-'+variant)),'-mode',mode,'-parallel',str(p),'-count',str(count),'-out',str(out)]+(['-corrupt-seed'] if negative else [])
 at=time.monotonic()
 with (e/(name+'.txt')).open('w') as log:r=subprocess.run(cmd,cwd=b,env=v,stdout=log,stderr=subprocess.STDOUT,timeout=190)
 report=json.loads(out.read_text());external=(time.monotonic()-at)*1000
 rec={'variant':variant,'mode':mode,'parallel':p,'rep':rep,'kind':kind,'negative':negative,'count':count,'exit_code':r.returncode,'external_process_ms':external,'report':report}
 records.append(rec);(e/'observations.json').write_text(json.dumps(records,separators=(',',':'))+'\n')
 assert report['cleanup'] and not list(scratch.iterdir()),(name,'cleanup')
 assert report['mode']==mode and report['parallel']==p and report['count']==count and report['gomaxprocs']==8
 assert 0<report['max_active']<=p and all(report['cleanup_stats'][k]==0 for k in ['active_mappings','active_rw_bytes','active_reserved_bytes','release_failures'])
 assert report['resolved_max_forks']==(p if mode=='fork' else 0)
 if variant=='pages':
  im=report['image_stats'];assert im['enabled'] and im['closed'] and im['owned_fds']==0 and im['builds']==1 and im['page_only'] and im['initialized_page_bytes']>0
 if negative:assert r.returncode==1 and not report['success'] and 'pristine oracle' in report['error'],(name,report)
 else:
  assert r.returncode==0 and report['success'] and len(report['samples'])==count,(name,report)
  assert {x['index'] for x in report['samples']}==set(range(count))
  assert all(x['oracle'] and x['cleanup'] and not x.get('error') for x in report['samples'])
  assert '12.3.3' in report['samples'][0]['version']
 for x in report['samples']:
  names=[z['name'] for z in x['spans']];assert len(names)==len(set(names))
  assert all(x['begin_ms']<=z['begin_ms']<=z['end_ms']<=x['end_ms'] for z in x['spans'])
  if not negative:assert {'start_or_fork','connect','select1','count_sum','update','verify_update','retire','close'}<=set(names) and ('seed' in names)==(mode=='fresh')
 print(name,'expected FAIL' if negative else 'PASS','suite',round(report['suite_ms'],2),flush=True)
arms=['baseline','current','pages']
for arm in arms:
 for mode in ['fresh','fork']:
  run(arm,mode,1,-2,'pilot',2);run(arm,mode,1,-2,'negative',1,True)
cells=[('fresh',1),('fork',1),('fresh',4),('fork',4)]
for mode,p in cells:
 for arm in arms:run(arm,mode,p,-1,'warmup')
for rep in range(5):
 for mode,p in cells[rep%4:]+cells[:rep%4]:
  k=(rep+cells.index((mode,p)))%3
  for arm in arms[k:]+arms[:k]:run(arm,mode,p,rep)
assert len(records)==84
(e/'completion.json').write_text(json.dumps({'result':'COLLECTED','processes':84,'primary_processes':60,'extra_repetitions':0,'candidate_source_commit':inputs['harness_and_candidate_source_commit']},indent=2)+'\n')
