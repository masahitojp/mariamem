import json, os, subprocess, sys, time, hashlib
from datetime import datetime, timezone
from pathlib import Path
root=Path(__file__).resolve().parents[4]
sys.path.insert(0,str(root/'scripts'))
from experiment_disk import DiskGuard, run_guarded
from git_identity import verify_go_binary
w=Path(__file__).resolve().parents[1]; src=w/'temp/source'; ev=w/'evidence'
source=json.loads((ev/'inputs.json').read_text())['source_commit']
verify_go_binary(src,w/'temp/ownedprepared',source)
env=os.environ.copy()
for k in ('GOGC','GOMEMLIMIT','GODEBUG','GOFLAGS','MARIAMEM_TIMING_DIR'): env.pop(k,None)
env.update(GOTOOLCHAIN='go1.26.8',GOMAXPROCS='2',CGO_ENABLED='1',GOCACHE=str(w/'temp/go-cache'),GOTMPDIR=str(w/'temp/go-tmp'),TMPDIR=str(w/'temp/os-tmp'))
guard=DiskGuard(w,min_free_gib=8,budget_gib=6)
records=[]
schedule=[('pilot',i,m,0,1,'none') for i,m in enumerate(['original','direct'])]
for kind in ['off','metrics']:
    schedule += [(kind,i,m,100,16,'none') for i,m in enumerate(['original','direct','direct','original'])]
schedule += [('cpu',i,m,100,16,'cpu') for i,m in enumerate(['original','direct'])]
schedule += [('trace',i,m,100,16,'trace') for i,m in enumerate(['direct','original'])]
for kind,i,mode,payload,n,profile in schedule:
    if time.time() > datetime(2026,10,14,14,58,37,tzinfo=timezone.utc).timestamp(): raise RuntimeError('four-hour wall deadline reached')
    label=f'{kind}-{i}-{mode}'; out=ev/(label+'.json')
    if out.exists(): raise RuntimeError('refuse to overwrite a prior scenario')
    cmd=[str(w/'temp/ownedprepared'),'-payload-mib',str(payload),'-forks',str(n),'-workers','1','-tables','1','-lifecycle','fork','-workload','crud','-out',str(out),'-label',label]
    if kind!='off': cmd += ['-child-audit',str(ev/(label+'-audit.json')),'-child-profile',profile]
    current=dict(env,MARIAMEM_SNAPSHOT_DIRECT='1' if mode=='direct' else '0')
    begin=time.time()
    print('START',label,flush=True)
    with (ev/(label+'.log')).open('w') as log:
        rc=run_guarded(cmd,guard,cwd=src,env=current,output=log,interval=5,timeout=180)
    row={'label':label,'kind':kind,'mode':mode,'command':cmd,'returncode':rc,'process_wall_seconds':time.time()-begin}
    records.append(row)
    (ev/'campaign.json').write_text(json.dumps(records,indent=2))
    if rc: raise RuntimeError('scenario failure; stop and retain')
    d=json.loads(out.read_text()); ops=d['operations']
    for prefix in ('fork_ready_','mutation_','child_close_'):
        assert sum(o['name'].startswith(prefix) for o in ops)==n
    row.update(snapshot_seconds=sum(o['seconds'] for o in ops if o['name']=='snapshot'),prepare_seconds=sum(o['seconds'] for o in ops if o['name'] in ('prepare_start','prepare_setup')),child_wall_seconds=d['instance_suite_wall_seconds'],suite_product_seconds=d['suite_product_seconds'],suite_cpu_seconds=d['suite_cpu_seconds'])
    (ev/'campaign.json').write_text(json.dumps(records,indent=2))
    print(json.dumps({k:v for k,v in row.items() if k!='command'}),flush=True)
(ev/'campaign-guard.json').write_text(json.dumps(guard.__dict__,default=str,indent=2))
print('campaign complete',flush=True)
