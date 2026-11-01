"""Fixed macOS follow-up: identical host binary, phase marks and isolated one-DB RSS."""
import argparse,ctypes,hashlib,json,os,platform,statistics,subprocess,sys,time
from pathlib import Path
W=Path(__file__).resolve().parents[1];C=W/'worktree';T=W/'temp';E=W/'evidence';B=C/'benchmarks/forkcompare'
sys.path.insert(0,str(C/'scripts'))
from git_identity import ReleasePin,require_commit,verify_release_pin
from experiment_disk import DiskGuard,run_guarded,stop_group
class Usage(ctypes.Structure):
 _fields_=[('uuid',ctypes.c_uint8*16)]+[(n,ctypes.c_uint64) for n in ('user_time','system_time','pkg_idle_wkups','interrupt_wkups','pageins','wired_size','resident_size','phys_footprint','proc_start_abstime','proc_exit_abstime')]
libproc=ctypes.CDLL('/usr/lib/libproc.dylib',use_errno=True);libproc.proc_pid_rusage.argtypes=[ctypes.c_int,ctypes.c_int,ctypes.c_void_p];libproc.proc_pid_rusage.restype=ctypes.c_int

def rss(pid):
 u=Usage()
 if libproc.proc_pid_rusage(pid,0,ctypes.byref(u))!=0:raise OSError(ctypes.get_errno(),'proc_pid_rusage')
 return u.resident_size

def save(p,d):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(d,indent=2,sort_keys=True)+'\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def stages(trace):
 assert trace and trace['operation']=='startup' and trace.get('guest'), 'missing guest timing file'
 g=trace['guest'];assert g['clock']=='guest_monotonic';events={e['name']:e['offset_ns'] for e in g['events']}
 names=['open_begin','server_init_complete','routine_schema_complete']
 assert all(n in events for n in names) and events[names[0]]<=events[names[1]]<=events[names[2]]
 return dict(server_init_ms=(events[names[1]]-events[names[0]])/1e6,post_init_to_routine_ms=(events[names[2]]-events[names[1]])/1e6,open_to_routine_ms=(events[names[2]]-events[names[0]])/1e6)
def validate(r,io,n,p):
 assert r['success'] and r['cleanup_complete'] and r['root_closed_before_forks']
 assert r['parallel']==p and r['count']==n and r['gomaxprocs']==8
 expected=dict(read=io,write=2,purge=1,native_aio=0)
 assert r['io_profile']==expected;stages(r['startup_trace'])
 assert len(r['samples'])==n and {s['index'] for s in r['samples']}==set(range(n))
 for s in r['samples']:
  assert s['oracle'] and s['cleanup_complete'] and s['io_profile']==expected
  stages(s['startup_trace'])

def main():
 p=argparse.ArgumentParser();p.add_argument('--phase',choices=['build','measure'],required=True);a=p.parse_args()
 commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=C,text=True).strip();require_commit(C,commit)
 assert not subprocess.check_output(['git','status','--porcelain'],cwd=C)
 pins=json.loads((B/'source-pins.json').read_text());verify_release_pin(T/'product',ReleasePin(**pins['mariamem']))
 assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=T/'product',text=True).strip()==pins['mariamem']['source_commit']
 assert not subprocess.check_output(['git','status','--porcelain'],cwd=T/'product')
 env={k:v for k,v in os.environ.items() if not k.startswith(('MARIAMEM_','MYSQLMEM_','GODEBUG','GOMEMLIMIT','GOGC','GOFLAGS'))}
 env.update(GOTOOLCHAIN='local',CGO_ENABLED='0',GOMAXPROCS='8',GOCACHE=str(T/'go-cache'),GOMODCACHE=str(T/'go-mod'),GOTMPDIR=str(T/'go-tmp'),TMPDIR=str(T/'scratch'))
 for n in ['go-cache','go-mod','go-tmp','scratch','bin']:(T/n).mkdir(parents=True,exist_ok=True)
 version=subprocess.check_output(['go','version'],text=True,env=env).strip();assert version=='go version go1.27.3 darwin/arm64'
 assert platform.mac_ver()[0]=='27.2'
 guard=DiskGuard(W,min_free_gib=16,budget_gib=8);binary=T/'bin/read4-queue'
 if a.phase=='build':
  subprocess.run([sys.executable,str(B/'queue-overlay.py')],check=True)
  with (E/'build.txt').open('w') as log:
   code=run_guarded(['go','build','-overlay',str(T/'overlay.json'),'-p','1','-mod=readonly','-trimpath','-buildvcs=true','-o',str(binary),'./maria'],guard,cwd=B,env=env,output=log,timeout=1200)
  assert code==0
  info=subprocess.check_output(['go','version','-m',binary],text=True,env=env);assert 'vcs.revision='+commit in info and 'vcs.modified=false' in info
  save(E/'inputs.json',dict(harness_source_commit=commit,products=pins,go=version,os=platform.mac_ver()[0],cpu='Apple M1',memory_bytes=17179869184,binary_sha256=sha(binary),build_info=info.replace(str(W),'<WORKSPACE>'),overlays=json.loads((E/'overlay-hashes.json').read_text()),plan=json.loads((B/'queue-plan.json').read_text())))
  print('BUILD PASS',flush=True);return
 inputs=json.loads((E/'inputs.json').read_text());assert inputs['harness_source_commit']==commit and sha(binary)==inputs['binary_sha256']
 own=rss(os.getpid());ps=int(subprocess.check_output(['ps','-o','rss=','-p',str(os.getpid())]))*1024;assert abs(own-ps)<8*1024**2
 records=[];deadline=time.monotonic()+600
 def run(io,kind,rep,n,p):
  assert time.monotonic()<deadline,'fixed measurement time budget'
  label=f'{a.phase}/{kind}-{rep:02d}-io{io}';out=E/(label+'.json');assert not out.exists()
  sync=T/'sync'/label;scratch=T/'scratch'/label;traces=E/(label+'-traces')
  for d in [sync,scratch,traces]:d.mkdir(parents=True)
  out.parent.mkdir(parents=True,exist_ok=True);identity=E/(label+'-data.json')
  childenv=dict(env,TMPDIR=str(scratch),MARIAMEM_TIMING_DIR=str(traces),MARIAMEM_EXPERIMENT_READ_IO=str(io),MARIAMEM_EXPERIMENT_DATA_IDENTITY=str(identity),MARIAMEM_EXPERIMENT_HOLD='1' if kind=='memory' else '0')
  cmd=[str(binary),'-out',str(out),'-route','tcp','-parallel',str(p),'-count',str(n),'-sync-dir',str(sync)]
  samples=[];held=[];proc=None;guard.check()
  with (E/(label+'.stderr.txt')).open('w') as log:
   try:
    proc=subprocess.Popen(cmd,cwd=B,env=childenv,stdout=log,stderr=subprocess.STDOUT,start_new_session=True);end=time.monotonic()+100
    while not (sync/'ready').exists():
     assert proc.poll() is None and time.monotonic()<end,'no ready handshake';time.sleep(.01)
    baseline=rss(proc.pid);begin=time.monotonic();(sync/'go').write_text('go')
    while not (sync/'done').exists():
     assert proc.poll() is None and time.monotonic()<end,'no done handshake'
     if kind=='memory' and (sync/'held').exists() and not (sync/'release').exists():
      for _ in range(3):held.append(rss(proc.pid));time.sleep(.005)
      (sync/'release').write_text('release')
     samples.append(dict(offset_ms=(time.monotonic()-begin)*1000,rss_bytes=rss(proc.pid)));time.sleep(.02)
    proc.wait(timeout=30);assert proc.returncode==0
   finally:
    if proc is not None:stop_group(proc)
  guard.check();r=json.loads(out.read_text());validate(r,io,n,p)
  assert not (E/(label+'.stderr.txt')).read_bytes() and not any(scratch.iterdir())
  trace=json.loads(Path(str(out)+'.trace.json').read_text());assert trace['dropped']==0 and trace['events']
  bindings=[x for x in trace['events'] if x['kind']=='instance_child'];assert len(bindings)==n+1
  assert len({x['instance'] for x in bindings})==n+1 and sorted(x['a'] for x in bindings)==[-1]+list(range(n))
  groups={}
  for event in trace['events']:
   if event['kind']=='concurrency_store':groups.setdefault(event['instance'],[]).append([event['a'],event['b']])
  for binding in bindings:
   expected=[[0,16]] if binding['a']==-1 else [[0,16],[4,4],[0,16],[4,4],[0,16]]
   assert groups[binding['instance']]==expected,(binding,groups[binding['instance']])
  data=json.loads(identity.read_text());assert data['read_io']==str(io) and data['changed_bytes']==int(io==4)
  assert (data['before_sha256']==data['effective_sha256'])==(io==1)
  mem=dict(baseline_rss_bytes=baseline,held_rss_bytes=held,held_rss_median_bytes=statistics.median(held) if held else None,sampled_peak_rss_bytes=max(s['rss_bytes'] for s in samples),interval_ms=20,held_interval_ms=5,samples=samples)
  if kind=='memory':assert len(held)==3
  save(E/(label+'-memory.json'),mem)
  records.append(dict(read_io=io,kind=kind,repetition=rep,children=n,parallel=p,report=label+'.json',memory=label+'-memory.json',data_identity=label+'-data.json',binary_sha256=inputs['binary_sha256']))
  save(E/(a.phase+'-records.json'),records);print('PASS',label,round(r['batch_ms'],2),'ms',flush=True)
 for rep in range(3):run(4,'queue',rep,48,8)
 save(E/(a.phase+'-completion.json'),dict(result='PASS',processes=len(records),children=sum(r['children'] for r in records),single_binary_sha256=inputs['binary_sha256']))
if __name__=='__main__':main()
