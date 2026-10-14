from pathlib import Path
import hashlib,json,os,subprocess,sys,time
w=Path(__file__).resolve().parents[1];repo=w/'temp/observed';e=w/'evidence'
sys.path.insert(0,str(repo/'scripts'))
from git_identity import require_commit,verify_go_binary
source='1c639ceb4516ff5e21ec245dfb319e0508698e8f';require_commit(repo,source)
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=repo,text=True).strip()==source
assert not subprocess.check_output(['git','status','--porcelain'],cwd=repo,text=True).strip()
env=dict(os.environ,GOTOOLCHAIN='go1.26.8',GOMAXPROCS='2',GOCACHE=str(w/'temp/gocache'),TMPDIR=str(w/'temp/tmp'),GOTMPDIR=str(w/'temp/go-tmp'))
env.pop('MARIAMEM_SNAPSHOT_DIRECT',None);env.pop('MARIAMEM_TIMING_DIR',None)
receipts=[]
def command(name,cmd,current=env):
 begin=time.monotonic()
 with (e/(name+'.txt')).open('w') as log:r=subprocess.run(cmd,cwd=repo,env=current,stdout=log,stderr=subprocess.STDOUT,timeout=1800)
 receipts.append(dict(source_commit=source,name=name,command=cmd,returncode=r.returncode,seconds=time.monotonic()-begin))
 (e/'events-receipts.json').write_text(json.dumps(receipts,indent=2)+'\n')
 if r.returncode:raise RuntimeError(name+' failed; stop')
command('events-contracts',['go','test','-race','-p','1','./internal/generatedgo/code/base','-run','TestMemFSAudit|TestMemFSGrowth|TestAllocation|TestPreparedGrowthOwnershipAndZeroFill|TestOwnedPrivateViewsGrowthAndRelease','-count=1','-v'],dict(env,MARIAMEM_MEMFS_AUDIT='1',MARIAMEM_MEMFS_GROWTH_EVENTS='1'))
binary=w/'temp/ownedprepared-events'
command('build-events',['go','build','-p','1','-buildvcs=true','-o',str(binary),'./benchmarks/ownedprepared'])
info=verify_go_binary(repo,binary,source)
(e/'events-inputs.json').write_text(json.dumps(dict(source_commit=source,binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),buildinfo=info,scope='one bounded 10 MiB/8-table Fresh input trace; only first 128 main-table resize calls; no optimization'),indent=2)+'\n')
name='growth-events-p10-t8-fresh'
current=dict(env,MARIAMEM_MEMFS_AUDIT='1',MARIAMEM_MEMFS_GROWTH_EVENTS='1',MARIAMEM_MEMFS_RESIZE_TIMER='1',MARIAMEM_MEMFS_AUDIT_OUT=str(e/(name+'-audit.json')),MARIAMEM_MEMFS_PROCESS_HELPER=str(w/'temp/process-cost'))
command(name,[str(binary),'-payload-mib','10','-tables','8','-lifecycle','fresh','-forks','1','-workers','1','-workload','app-connections','-go-resources','-helper',str(w/'temp/process-cost'),'-out',str(e/(name+'.json')),'-label',source],current)
d=json.loads((e/(name+'-audit.json')).read_text());nodes=[n for n in d['nodes'] if n['path'].endswith('/characterization.ibd')];assert len(nodes)==1
node=nodes[0];events=[]
for key in node['phase_operation_stats']:
 if key.startswith('_growth_event|'):
  _,phase,op,index,oldlen,oldcap,size,newcap=key.split('|');events.append(dict(phase=phase,op=op,index=int(index),oldlen=int(oldlen),oldcap=int(oldcap),size=int(size),newcap=int(newcap)))
events.sort(key=lambda x:x['index']);assert len(events)==52 and all(x['phase']=='fixture-sql' and x['op']=='allocate' for x in events)
def replay(divisor):
 length=capacity=allocated=copied=count=cleared=0
 for x in events:
  size=x['size']
  if size>capacity:
   growth=capacity if capacity<1<<20 else capacity//divisor
   capacity=max(capacity+growth,size);allocated+=capacity;copied+=length;count+=1
  elif size>length:cleared+=size-length
  length=size
 return dict(capacity_allocation_bytes=allocated,old_logical_copied_bytes=copied,allocation_count=count,final_logical_bytes=length,final_capacity_bytes=capacity,final_spare_bytes=capacity-length,explicit_clear_bytes=cleared)
current=replay(4);candidate=replay(2)
stats=node['phase_operation_stats']['fixture-sql:allocate']
assert current['capacity_allocation_bytes']==stats['initial_capacity_bytes']+stats['realloc_capacity_bytes']
assert current['old_logical_copied_bytes']==stats['old_logical_copied_bytes']
assert current['final_capacity_bytes']==node['capacity_bytes']
out=dict(source_commit=source,events=events,current_125=current,candidate_150=candidate,allocated_saving_bytes=current['capacity_allocation_bytes']-candidate['capacity_allocation_bytes'],copy_saving_bytes=current['old_logical_copied_bytes']-candidate['old_logical_copied_bytes'],scope='arithmetic on exact requested EOFs; no candidate implementation, physical/RSS/GC/suite benefit inferred')
(e/'growth-model.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out,indent=2)[-1700:])
