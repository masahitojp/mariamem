from pathlib import Path
import subprocess,sys,os,json,hashlib,time,platform
s=Path(__file__).resolve().parents[2];w=s.parent;t=w/'temp';e=w/'evidence';b=Path(__file__).resolve().parent
sys.path.insert(0,str(s/'scripts'))
from experiment_disk import DiskGuard,run_guarded
i=json.loads((e/'inputs.json').read_text())
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=s,text=True).strip()==i['source_commit']
assert not subprocess.check_output(['git','status','--porcelain'],cwd=s)
assert hashlib.sha256((t/'probe').read_bytes()).hexdigest()==i['binary_sha256']
env={k:v for k,v in os.environ.items() if not k.startswith(('GO','MARIAMEM_','MYSQLMEM_','UPDATE_','LEXER'))}
env.update(GOMAXPROCS='8',GOGC='100')
(e/'host.json').write_text(json.dumps({'platform':platform.platform(),'cpu':subprocess.check_output(['sysctl','-n','machdep.cpu.brand_string'],text=True).strip(),'memory':int(subprocess.check_output(['sysctl','-n','hw.memsize'],text=True))},indent=2)+'\n')
guard=DiskGuard(w,12,6);records=[]
schedule=[(rep,mode) for rep in range(5) for mode in (['off','timed'] if rep%2==0 else ['timed','off'])]+[(0,'inventory')]
for rep,mode in schedule:
 name=f'{mode}-{rep}';p=e/(name+'.json');assert not p.exists()
 scratch=t/'scratch'/name;scratch.mkdir();v=dict(env,TMPDIR=str(scratch))
 with (e/(name+'.txt')).open('w') as log:
  code=run_guarded([str(t/'probe'),'-mode',mode,'-out',str(p)],guard,cwd=b,env=v,output=log,timeout=60)
 assert code==0,(name,code)
 r=json.loads(p.read_text());assert r['Success'] and not r['Error'] and len(r['Samples'])==5
 assert not list(scratch.iterdir()),('scratch',name)
 assert all(r['Cleanup'][k]==0 for k in ['active_mappings','active_rw_bytes','active_reserved_bytes','release_failures'])
 for x in r['Samples']:
  assert (mode=='off')==(len(x['Rows'] or [])==0)
  for row in x['Rows'] or []:
   assert row['result']==row['exception']==0
   assert (row['elapsed_ns']>0)==(mode=='timed')
   if mode=='inventory':
    data=bytes.fromhex(row['pair_hex']);assert len(data)==512 and hashlib.sha256(data).hexdigest()==row['pair_sha256']
 records.append({'rep':rep,'mode':mode,'report':p.name})
 (e/'records.json').write_text(json.dumps(records,indent=2)+'\n')
 print(name,'PASS',[(x['Kind'],len(x['Rows'] or []),round(sum(z['elapsed_ns'] for z in x['Rows'] or [])/1e6,3)) for x in r['Samples']],flush=True)
(e/'completion.json').write_text(json.dumps({'result':'COLLECTED','processes':11,'initializations':55,'source_commit':i['source_commit'],'extra_trials':0},indent=2)+'\n')
