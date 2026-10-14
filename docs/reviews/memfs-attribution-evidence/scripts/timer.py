from pathlib import Path
import json,os,subprocess,sys,time
w=Path(__file__).resolve().parents[1];repo=w/'temp/observed';e=w/'evidence'
sys.path.insert(0,str(repo/'scripts'))
from git_identity import verify_go_binary
source=json.loads((e/'inputs.json').read_text())['source_commits']['observed']
binary=w/'temp/ownedprepared-observed';verify_go_binary(repo,binary,source)
name='resize-timed-p10-t8-fresh'
env=dict(os.environ,GOTOOLCHAIN='go1.26.8',GOMAXPROCS='2',TMPDIR=str(w/'temp/tmp'),
         MARIAMEM_MEMFS_AUDIT='1',MARIAMEM_MEMFS_RESIZE_TIMER='1',
         MARIAMEM_MEMFS_AUDIT_OUT=str(e/(name+'-audit.json')),
         MARIAMEM_MEMFS_PROCESS_HELPER=str(w/'temp/process-cost'))
env.pop('MARIAMEM_TIMING_DIR',None);env.pop('MARIAMEM_SNAPSHOT_DIRECT',None)
cmd=[str(binary),'-payload-mib','10','-tables','8','-lifecycle','fresh','-forks','1','-workers','1',
     '-workload','app-connections','-go-resources','-helper',str(w/'temp/process-cost'),'-out',str(e/(name+'.json')),'-label',source]
begin=time.monotonic()
with (e/(name+'.txt')).open('w') as log:r=subprocess.run(cmd,cwd=repo,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=180)
(e/'timer-receipt.json').write_text(json.dumps(dict(source_commit=source,command=cmd,returncode=r.returncode,seconds=time.monotonic()-begin,scope='one additional aggregate resize timer run under Decision section 7; no all-I/O profiling or new workload'),indent=2)+'\n')
if r.returncode:sys.exit(r.returncode)
data=json.loads((e/(name+'-audit.json')).read_text());assert data['resize_timer']
print('Timed resize aggregate ms',sum(s['resize_ns'] for n in data['nodes'] for s in n['phase_operation_stats'].values())/1e6)
for n in data['nodes']:
 for phase,s in n['phase_operation_stats'].items():
  if s['resize_ns']>100000:print(n['path'],phase,'ms',round(s['resize_ns']/1e6,3))
