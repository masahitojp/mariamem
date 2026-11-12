"""Fixed one-control/eight-natural diagnostic campaign. No result-selected retry."""
from pathlib import Path
import os,json,subprocess,sys,hashlib,platform,time
W=Path(sys.argv[1]).resolve();S=W/'worktree';T=W/'temp';E=W/'evidence';P=T/'execution/product';R=P/'tests/timer_calibration/runner'
sys.path.insert(0,str(S/'scripts'))
from experiment_disk import DiskGuard
# Guard scans run before/after processes, not concurrently with timed workload.
g=DiskGuard(W,6,8);g.check()
env={k:v for k,v in os.environ.items() if not k.startswith(('GO','MARIAMEM_','MYSQLMEM_','ISSUE','TIMER','SAMPLE','MODELCASE','READ_','FORK_STAGE'))}
env.update(GOTOOLCHAIN='go1.26.10',GOWORK='off',GOENV='off',GOFLAGS='',GOMAXPROCS='8',GOGC='100',ISSUE88_POOL_MIB='16',ISSUE88_SAMPLE_PHASES='1',ISSUE68_CAPTURE='1',TMPDIR=str(T/'run-scratch'))
(T/'run-scratch').mkdir(exist_ok=True)
identity=json.loads(subprocess.check_output([sys.executable,S/'scripts/git_identity.py','inspect','HEAD'],cwd=S))
assert not subprocess.check_output(['git','status','--porcelain'],cwd=S)
inputs={'source':identity,'plan':json.loads((S/'benchmarks/pool-worker-progress/plan.json').read_text()),'platform':platform.platform(),'binary_sha256':hashlib.sha256((T/'probe').read_bytes()).hexdigest(),'installation':json.loads((T/'execution/installation.json').read_text()),'overlay_sha256':hashlib.sha256((T/'overlay/overlay.json').read_bytes()).hexdigest()}
inputs['installation'].pop('generated_inventory');(E/'inputs.json').write_text(json.dumps(inputs,indent=2)+'\n')
rows=[]
for i in range(9):
 control=i==0;name='control' if control else f'natural-{i}'
 d=E/name;d.mkdir();env.update(ISSUE68_CONTROL='1' if control else '0',ISSUE68_CAPTURE_DIR=str(d),MODELCASE_TRACE=str(d/'trace.json'),SAMPLE_PHASES_OUT=str(d/'sql.json'),READ_OBSERVATION_OUT=str(d/'read.json'))
 print('RUN',name,flush=True);g.check()
 with (d/'console.txt').open('w') as f:subprocess.run([T/'probe','-test.parallel=8','-test.timeout=120s','-test.count=1'],cwd=R,env=env,stdout=f,stderr=subprocess.STDOUT,check=True,timeout=140)
 g.check();trace=json.loads((d/'trace.json').read_text());reads=json.loads((d/'read.json').read_text());sql=json.loads((d/'sql.json').read_text())
 assert trace['meta']['active_mappings_after']=='0' and trace['meta']['read_cases']=='50' and trace['meta']['write_cases']=='20'
 assert trace['meta']['fork_cap']=='9' and trace['meta']['parallel']=='8' and trace['meta']['route']=='Pipe'
 assert trace['meta']['innodb_buffer_pool_size']==trace['meta']['innodb_buffer_pool_size_max']==str(16*2**20) and trace['meta']['innodb_read_io_threads']=='1'
 assert len(sql)==21 and reads and all(r['closed'] and not r['truncated'] for r in reads)
 assert sum(len(r['ios'] or []) for r in reads)>0 and sum(len(r['progress'] or []) for r in reads)>0
 assert not list((T/'run-scratch').iterdir()),'owned scratch not empty'
 caps=[json.loads(x.read_text()) for x in d.glob('capture-*.json')];assert len(caps)<=1
 for c in caps:
  assert c['call_enter_us']<=c['snapshot_begin_us']<=c['snapshot_end_us']<=c['call_return_us'] and not c['truncated']
  assert c['bytes']==(d/c['profile_file']).stat().st_size
 if control:assert len(caps)==1 and caps[0]['phase']=='positive_control'
 longcalls=[{'db':l['db_id'],'lane':l['lane'],'phase':phase,'ordinal':j+1,'us':n} for l in sql for phase,values in l['durations_us'].items() for j,n in enumerate(values) if n>=100000]
 row={'name':name,'wall_ms':trace['elapsed_ms'],'long_calls':longcalls,'captures':len(caps),'read_requests':sum(len(r['ios'] or []) for r in reads),'progress_events':sum(len(r['progress'] or []) for r in reads)}
 rows.append(row);(E/'runs.json').write_text(json.dumps(rows,indent=2)+'\n');print('PASS',name,'longcalls',len(longcalls),'captures',len(caps),flush=True)
print('FINITE CAMPAIGN COMPLETE',flush=True)
