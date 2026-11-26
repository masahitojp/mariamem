#!/usr/bin/env python3
"""Portable fixed-source probe; run in an experiment workspace with --repo."""
import argparse,collections,gzip,hashlib,io,json,os,pathlib,platform,re,signal,statistics,subprocess,tarfile,time
SOURCE='e00b3ec41f9c5d4ca3f85db4ff73198dbf3613e9'
HARNESS='1977fff480c2f976bc23f4d2e1b8ff8db36ad128'
PATTERN='^Test(ListOrders|GetOrder|TopProducts|SearchProducts|RevenueByCategory|CreateOrder|CancelOrder|ShipOrder|DeleteUser|ApplyDiscount)$'
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--repo',type=pathlib.Path,required=True);ap.add_argument('--workspace',type=pathlib.Path,required=True);ap.add_argument('--allow-linux',action='store_true');a=ap.parse_args()
 repo=a.repo.resolve();w=a.workspace.resolve();w.mkdir(parents=True,exist_ok=True);out=w/'evidence';out.mkdir(exist_ok=True);tmp=w/'temp';tmp.mkdir(exist_ok=True)
 assert platform.system()=='Darwin' or a.allow_linux, 'Mac probe requires Darwin; --allow-linux only for matched reference'
 def git(*args):return subprocess.check_output(['git',*args],cwd=repo,text=True).strip()
 assert git('cat-file','-t',SOURCE)=='commit' and git('rev-parse','HEAD')==SOURCE
 assert not git('diff','HEAD','--'), 'tracked source modifications'
 assert not (tmp/'harness').exists(), 'fresh workspace required'
 data=(pathlib.Path(__file__).resolve().parent/'mac-harness.tar.gz').read_bytes()
 expected=json.loads((pathlib.Path(__file__).resolve().parent/'mac-plan.json').read_text())['harness_tar_gz_sha256']
 assert hashlib.sha256(data).hexdigest()==expected
 tarfile.open(fileobj=io.BytesIO(data),mode='r:gz').extractall(tmp/'harness',filter='data')
 suite=tmp/'harness/benchmarks/comparison-variance/harness/maria-suite';p=suite/'go.mod';p.write_text(p.read_text().replace('<MARIAMEM_SOURCE>',str(repo)))
 env=os.environ.copy();env.update(GOTOOLCHAIN='go1.27.4',CGO_ENABLED='0',GOMAXPROCS='8',GOGC='100',MODELCASE_MATCHED='1',MARIA_AUDIT_OF='1',REVENUE_PREAGG='1',MARIA_ASYNC_CLOSE='0')
 for key in ['MODELCASE_DSN','RESPONSE_PIPE','MARIAMEM_EXPERIMENT_SKIP_EMPTY_WRITE','SKIP_READ_BODY','GODEBUG','SAMPLE_PROFILE','PROFILE_DIR','TRIGGERS_OFF','SUM_EXPERIMENT','INSERT_STAGES','PROFILE_ONLY','MARIAMEM_TIMING_DIR']:env.pop(key,None)
 subprocess.run(['go','mod','tidy'],cwd=suite,env=env,check=True,timeout=300)
 binary=tmp/'maria.test';subprocess.run(['go','test','-c','-o',str(binary),'./store'],cwd=suite,env=env,check=True,timeout=1200)
 info=subprocess.check_output(['go','version','-m',str(binary)],env=env,text=True)
 assert 'go1.27.4' in info and 'CGO_ENABLED=0' in info
 report={'source_commit':SOURCE,'harness_source_commit':HARNESS,'harness_tar_gz_sha256':expected,'binary_sha256':hashlib.sha256(binary.read_bytes()).hexdigest(),'buildinfo':info,'go_mod':p.read_text(),'go_sum_sha256':hashlib.sha256((suite/'go.sum').read_bytes()).hexdigest(),'platform':platform.platform(),'machine':platform.machine(),'runs':[]}
 if platform.system()=='Darwin':
  report['hardware']=subprocess.check_output(['sysctl','hw.model','hw.memsize','hw.ncpu','hw.physicalcpu','machdep.cpu.brand_string'],text=True)
 else:report['hardware']=subprocess.check_output(['lscpu'],text=True)
 def save():
  with gzip.open(out/'mac-results.json.gz','wt') as f:json.dump(report,f,separators=(',',':'))
 save()
 for n,kind in enumerate(['precheck','warmup','measured','measured','measured','profile']):
  trace=tmp/'trace.json';e=env.copy();e['MODELCASE_TRACE']=str(trace)
  cmd=[str(binary),'-test.v','-test.timeout=90s','-test.parallel=1','-test.run='+('^TestMatchedSemantics$' if kind=='precheck' else PATTERN)]
  if kind=='profile':cmd += ['-test.cpuprofile='+str(out/'cpu-mac-p1.pprof')]
  start=time.monotonic();load=os.getloadavg()
  with (out/f'run-{n}.log').open('w') as log:
   child=subprocess.Popen(cmd,cwd=tmp,env=e,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
   try:
    while True:
     pid,status,usage=os.wait4(child.pid,os.WNOHANG)
     if pid:child.returncode=os.waitstatus_to_exitcode(status);break
     if time.monotonic()-start>100:raise TimeoutError('probe run timeout')
     time.sleep(.01)
   except BaseException:
    os.killpg(child.pid,signal.SIGKILL);os.wait4(child.pid,0);child.returncode=-9;raise
  wall=1000*(time.monotonic()-start)
  if child.returncode:raise RuntimeError(f'run {n} failed: see run-{n}.log')
  t=json.loads(trace.read_text());names=collections.Counter(s['name'] for s in t['spans']);kinds=collections.Counter(s['kind'] for s in t['spans'])
  assert all(0<=s['start_ms']<=s['end_ms']<=t['elapsed_ms']+.01 for s in t['spans'])
  if kind!='precheck':assert names['fork']==20 and names['sample']==21 and names['final_cleanup']==1 and kinds['read']==50 and kinds['write']==20
  phases=collections.defaultdict(list)
  for s in t['spans']:phases[s['name']].append(s['end_ms']-s['start_ms'])
  report['runs'].append({'kind':kind,'index':n,'parallel':1,'GOMAXPROCS':8,'suite_ms':t['elapsed_ms'],'process_ms':wall,'cpu_ms':1000*(usage.ru_utime+usage.ru_stime),'rss_kib':usage.ru_maxrss/(1024 if platform.system()=='Darwin' else 1),'load':load,'phase_medians_ms':{k:statistics.median(v) for k,v in phases.items()},'returncode':child.returncode,'trace':t});save()
  print(kind,f'{t["elapsed_ms"]:.1f}ms',flush=True)
 measured=[r for r in report['runs'] if r['kind']=='measured']
 summary={k:statistics.median(r[k] for r in measured) for k in ['suite_ms','process_ms','cpu_ms','rss_kib']}
 summary['phases']={k:statistics.median(r['phase_medians_ms'][k] for r in measured) for k in measured[0]['phase_medians_ms']}
 (out/'mac-summary.json').write_text(json.dumps(summary,indent=2)+'\n')
 for name,flags in [('cpu-mac-p1.txt',['-top']),('cpu-mac-p1-cum.txt',['-top','-cum']),('memory-ea.asm.txt',[])]:
  cmd=['go','tool','pprof',*flags,'-nodecount=25',str(binary),str(out/'cpu-mac-p1.pprof')] if flags else ['go','tool','objdump','-s',r'base\.MemoryEA$',str(binary)]
  (out/name).write_text(subprocess.check_output(cmd,env=env,text=True,stderr=subprocess.STDOUT))
 hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in out.iterdir() if p.is_file()}
 (out/'SHA256SUMS.json').write_text(json.dumps(hashes,indent=2)+'\n')
 print('COMPLETE: retain evidence/ before cleaning temp/',flush=True)
if __name__=='__main__':main()
