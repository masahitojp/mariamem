from pathlib import Path
import hashlib,json,os,platform,subprocess,sys,time

work=Path(__file__).resolve().parents[1];temp=work/'temp';evidence=work/'evidence'
sys.path.insert(0,str(temp/'control/scripts'))
from git_identity import require_commit,verify_go_binary
roots={m:temp/m for m in ('control','observed')}
sources={'control':'a8137b8b444f86068d3128a291e3a848adfdfd56','observed':'c3a527d26ceaaad74f5480ac1469ed586716366c'}
env=dict(os.environ,GOTOOLCHAIN='go1.26.8',GOMAXPROCS='2',GOCACHE=str(temp/'gocache'),TMPDIR=str(temp/'tmp'),GOTMPDIR=str(temp/'go-tmp'))
for key in ('MARIAMEM_TIMING_DIR','MARIAMEM_SNAPSHOT_DIRECT','MARIAMEM_MEMFS_AUDIT','MARIAMEM_MEMFS_AUDIT_OUT','MARIAMEM_MEMFS_PROCESS_HELPER'):env.pop(key,None)
for m,r in roots.items():
 require_commit(r,sources[m]);assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=r,text=True).strip()==sources[m]
 assert not subprocess.check_output(['git','status','--porcelain'],cwd=r,text=True).strip()
inputs=dict(source_commits=sources,platform=platform.platform(),gomaxprocs=2,
 toolchain=subprocess.check_output(['go','version'],env=env,text=True).strip(),
 runner_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),trials=3,
 cells=[dict(payload_mib=p,tables=t,lifecycle=l) for p,t in ((0,1),(10,8)) for l in ('fresh','fork')],
 observed_scope='Experimental exact-preimage generated support instrumentation, UNQUALIFIED. No optimization or canonical provenance refresh.',
 coverage='4 KiB lower/upper bitmap; max 1 GiB/file; shrink clips coverage and advances epoch; no content/nonzero scan',
 env={k:env.get(k) for k in ('GOMAXPROCS','GOTOOLCHAIN','GOGC','GOMEMLIMIT','GODEBUG','GOFLAGS')})
(evidence/'inputs.json').write_text(json.dumps(inputs,indent=2)+'\n')
builds=[]
def command(name,cmd,cwd,current=env):
 print(name,flush=True);begin=time.monotonic()
 with (evidence/(name+'.txt')).open('w') as log:r=subprocess.run(cmd,cwd=cwd,env=current,stdout=log,stderr=subprocess.STDOUT,timeout=1800)
 builds.append(dict(name=name,command=cmd,source_commit=sources['observed'] if cwd==roots['observed'] else sources['control'],returncode=r.returncode,seconds=time.monotonic()-begin))
 (evidence/'builds.json').write_text(json.dumps(builds,indent=2)+'\n')
 if r.returncode:raise RuntimeError(name+' failed; stop')
command('observer-contracts',['go','test','-race','-p','1','./internal/generatedgo/code/base','-run','TestMemFSAudit|TestMemFSGrowth|TestOwnedPrivateViewsGrowthAndRelease|TestPreparedGrowthOwnershipAndZeroFill|TestAllocation','-count=1','-v'],roots['observed'],dict(env,MARIAMEM_MEMFS_AUDIT='1'))
command('process-helper',['cc','-O2','-o',str(temp/'process-cost'),str(roots['control']/'benchmarks/tools/process_cost.c')],roots['control'])
inputs['binaries']={}
for mode in ('control','observed'):
 binary=temp/('ownedprepared-'+mode)
 command('build-'+mode,['go','build','-p','1','-buildvcs=true','-o',str(binary),'./benchmarks/ownedprepared'],roots[mode])
 inputs['binaries'][mode]=dict(sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),buildinfo=verify_go_binary(roots[mode],binary,sources[mode]))
 inputs['binaries'][mode]['guest_sha256']=json.loads((roots[mode]/'internal/generatedgo/provenance.json').read_text())['guest_sha256']
 inputs['binaries'][mode]['harness_sha256']=hashlib.sha256((roots[mode]/'benchmarks/ownedprepared/main.go').read_bytes()).hexdigest()
 (evidence/'inputs.json').write_text(json.dumps(inputs,indent=2)+'\n')
records=[]
for cell in inputs['cells']:
 for trial in range(3):
  for mode in (('control','observed') if trial%2==0 else ('observed','control')):
   p,t,l=cell['payload_mib'],cell['tables'],cell['lifecycle'];label=f'p{p}-t{t}-{l}-{trial}-{mode}'
   output=evidence/(label+'.json');audit=evidence/(label+'-audit.json')
   cmd=[str(temp/('ownedprepared-'+mode)),'-payload-mib',str(p),'-tables',str(t),'-lifecycle',l,'-forks','1','-workers','1','-workload','app-connections','-go-resources','-helper',str(temp/'process-cost'),'-out',str(output),'-label',sources[mode]]
   current=dict(env)
   if mode=='observed':current.update(MARIAMEM_MEMFS_AUDIT='1',MARIAMEM_MEMFS_AUDIT_OUT=str(audit),MARIAMEM_MEMFS_PROCESS_HELPER=str(temp/'process-cost'))
   start=time.monotonic()
   with (evidence/(label+'.txt')).open('w') as log:r=subprocess.run(cmd,cwd=roots[mode],env=current,stdout=log,stderr=subprocess.STDOUT,timeout=180)
   row=dict(name=label,mode=mode,trial=trial,**cell,command=cmd,returncode=r.returncode,wall_seconds=time.monotonic()-start)
   records.append(row);(evidence/'campaign.json').write_text(json.dumps(records,indent=2)+'\n')
   if r.returncode:raise RuntimeError(label+' failed; stop')
   data=json.loads(output.read_text());row.update(suite_product_seconds=data['suite_product_seconds'],suite_cpu_seconds=data['suite_cpu_seconds'],peak_rss_bytes=data['go_resource_observation']['process_peak_rss_bytes'],cumulative_alloc_bytes=data['go_resource_observation']['cumulative_alloc_bytes'])
   assert data['forks']==1 and data['workers']==1
   if mode=='observed':
    obs=json.loads(audit.read_text());assert not obs['resize_timer']
    assert all(not n['coverage_limit_exceeded'] for n in obs['nodes'])
    assert all(not f.get('process_error') for f in obs['frames'])
    assert all(all('primary_bytes' in v for v in f.get('process_counters',{}).values()) for f in obs['frames'])
   assert row['peak_rss_bytes']<8*1024**3
   (evidence/'campaign.json').write_text(json.dumps(records,indent=2)+'\n')
   print(label,'suite',round(row['suite_product_seconds'],3),'RSS MiB',round(row['peak_rss_bytes']/2**20,1),flush=True)
print('24 cases complete; no optimization performed',flush=True)
