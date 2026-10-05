#!/usr/bin/env python3
"""Exact-source correctness and native consumer acceptance; no release or benchmarks."""
import argparse, hashlib, json, os, platform, resource, shutil, subprocess, sys, tarfile, time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def digest(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
 parser=argparse.ArgumentParser(description=__doc__)
 parser.add_argument('--converter',type=Path)
 parser.add_argument('--skip-consumers',action='store_true')
 args=parser.parse_args()
 temp=Path(os.environ['MARIAMEM_EXPERIMENT_TEMP']).resolve(); evidence=Path(os.environ['MARIAMEM_EXPERIMENT_EVIDENCE']).resolve()
 env=dict(os.environ,GOTOOLCHAIN='go1.26.8',GOWORK='off',GOENV='off',GOFLAGS='',GOEXPERIMENT='')
 go=Path(subprocess.check_output(['go','env','GOROOT'],env=env,text=True).strip())/'bin/go'
 env['PATH']=str(go.parent)+os.pathsep+env['PATH']
 sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
 report={'source_commit':sha,'platform':platform.platform(),'architecture':platform.machine(),'go':subprocess.check_output([go,'version'],text=True).strip(),'phases':[],'result':'FAIL','release':False}
 def save(): (evidence/'platform.json').write_text(json.dumps(report,indent=2)+'\n')
 def limits():
  resource.setrlimit(resource.RLIMIT_CORE,(0,0));resource.setrlimit(resource.RLIMIT_CPU,(180,200));resource.setrlimit(resource.RLIMIT_NOFILE,(256,256))
 def run(name,cmd,cwd=ROOT,extra=None,timeout=900):
  print('RUN',name,flush=True); row={'name':name,'peak_rss_bytes':0,'peak_primary_bytes':0};report['phases'].append(row);save();start=time.monotonic()
  with (evidence/(name+'.log')).open('wb') as log:
   p=subprocess.Popen(list(map(str,cmd)),cwd=cwd,env=dict(env,**(extra or {})),stdout=log,stderr=subprocess.STDOUT,preexec_fn=limits)
   try:
    while p.poll() is None:
     if time.monotonic()-start>timeout: raise RuntimeError(name+': timeout')
     helper=temp/'process-cost'
     if helper.exists():
      pairs=[tuple(map(int,x.split())) for x in subprocess.check_output(['ps','-A','-o','pid=,ppid='],text=True).splitlines() if len(x.split())==2];ids={p.pid}
      for _ in pairs:
       old=len(ids);ids.update(a for a,b in pairs if b in ids)
       if len(ids)==old: break
      counters=json.loads(subprocess.check_output([helper,*map(str,ids)],text=True));rss=sum(v.get('rss_bytes',0) for v in counters.values());physical=sum(v.get('primary_bytes',0) for v in counters.values())
      row['peak_rss_bytes']=max(row['peak_rss_bytes'],rss);row['peak_primary_bytes']=max(row['peak_primary_bytes'],physical)
      if rss>6*2**30 or physical>8*2**30: raise RuntimeError(name+': resource budget')
     time.sleep(.2)
   finally:
    if p.poll() is None: p.kill();p.wait()
  row.update(exit_code=p.returncode,elapsed_seconds=time.monotonic()-start);save();print('END',name,p.returncode,flush=True)
  if p.returncode or 'no tests to run' in (evidence/(name+'.log')).read_text(errors='replace'): raise RuntimeError(name+': validation failed; evidence retained')
 try:
  if platform.system()=='Linux':
   info=dict(line.rstrip().split('=',1) for line in Path('/etc/os-release').read_text().splitlines() if '=' in line)
   assert info['ID'].strip('"')=='ubuntu' and info['VERSION_ID'].strip('"')=='24.04' and platform.machine()=='x86_64'
  else: assert platform.system()=='Darwin' and platform.machine()=='arm64'
  run('build-counter',['cc','-O2',ROOT/'benchmarks/tools/process_cost.c','-o',temp/'process-cost'])
  run('verify-provenance',[sys.executable,ROOT/'scripts/verify_generated_runtime.py'])
  converter=args.converter
  if converter is None:
   sys.path.insert(0,str(ROOT/'scripts'))
   from build_generated_guest import download
   archive=download(json.loads((ROOT/'release/generated-go-toolchain.json').read_text())['archives']['converter'],ROOT/'build/downloads')
   src=temp/'converter-source';src.mkdir()
   with tarfile.open(archive) as tar: tar.extractall(src,filter='data')
   src=next(src.iterdir());manifest=json.loads((ROOT/'release/generated-go-translation.json').read_text())
   for name,expected in manifest['patches_sha256'].items():
    patch=ROOT/'benchmarks/spikes/wasm2go'/name;assert digest(patch)==expected
    run('patch-'+name,['git','apply','--unidiff-zero',patch],cwd=src)
   converter=temp/'converter'
   run('build-converter',[go,'build','-p','1','-trimpath','-buildvcs=false','-o',converter,'./cmd/wasm2go'],cwd=src)
  fixture=ROOT/'benchmarks/spikes/memory-candidate'
  run('memory32-regression',[sys.executable,fixture/'check_fixture.py','--converter',converter,'--output',temp/'regression'])
  # Same immutable matrix, now exercised with the production anonymous owner.
  project=temp/'mapped-fixture';shutil.copytree(temp/'regression',project);pkg=project/'module/fixture'
  (pkg/'memory_mapping.go').write_text((ROOT/'internal/generatedgo/code/base/memory_mapping.go').read_text().replace('package base','package fixture',1))
  (pkg/'mapped.go').write_text('package fixture\nfunc NewMapped()(*Module,func()error){b,e:=NewMemoryMapping(65536,3*65536);if e!=nil{panic(e)};m:=NewWithMemory(b.Bytes(),65536);m.prepareMemoryGrow=b.Grow;return m,b.Close}\n')
  p=project/'module/main.go';s=p.read_text().replace('m := fixture.New()','m, release := fixture.NewMapped()');s=s.replace('\t}\n\tm, release := fixture.NewMapped()','\t\tif e:=release();e!=nil{panic(e)}\n\t}\n\tm, release := fixture.NewMapped()');s=s.replace('\tbase := &m.Memory()[0]','\tdefer func(){if e:=release();e!=nil{panic(e)};stats:=fixture.MemoryMappingStats();if stats["active_mappings"]!=0 || stats["creates"]!=stats["releases"]{panic("mapping leak")};fmt.Fprintln(os.Stderr,"mapped ownership PASS",stats)}()\n\tbase := &m.Memory()[0]');p.write_text(s)
  run('mapped-memory32-regression',[go,'run','.',project/'inputs/matrix.json'],cwd=project/'module')
  actual=[json.loads(line) for line in (evidence/'mapped-memory32-regression.log').read_text().splitlines() if line.startswith('{')];golden=json.loads((fixture/'reference-results.json').read_text());assert [[v[k] for k in golden['keys']] for v in actual]==golden['rows'];report['fixture_cases']=len(actual);report['trap_cases']=sum(v['trap'] for v in actual)
  run('focused-runtime-race',[go,'test','-race','-p','1','-v','-count=1','-timeout=180s','./internal/generatedgo/code/base','./internal/generatedgo','./internal/guest','./internal/host','./internal/mysqlwire','./internal/snapshot'],extra={'CGO_ENABLED':'1'})
  run('generated-product-smoke',[go,'test','-p','1','-tags=integration','-v','-count=1','-timeout=180s','./tests/generatedmemory'])
  run('normal-product-smoke',[go,'test','-p','1','-tags=integration','-v','-count=1','-timeout=300s','./tests/godefault'])
  report['correctness']='PASS';save()
  if not args.skip_consumers:
   run('build-installed-wheel',[sys.executable,ROOT/'scripts/build_alpha.py','--ci-candidate'],timeout=1200)
   target='darwin-arm64' if platform.system()=='Darwin' else 'ubuntu24.04-x86_64'
   # The isolated consumer cache is cold. Serialize Go compilation so it stays
   # inside the same RSS budget; correctness phases above retain normal settings.
   run('external-consumers',[sys.executable,ROOT/'scripts/generated_release_acceptance.py','--candidate-sha',sha,'--platform',target,'--output',evidence/'consumers.json'],extra={'GOMAXPROCS':'1'},timeout=1800)
   consumers=json.loads((evidence/'consumers.json').read_text());assert consumers['result']=='PASS';report['consumers']={'result':'PASS','gorm_cases':consumers['gorm_cases'],'sqlalchemy_cases':consumers['sqlalchemy_cases'],'wheel_sha256':consumers['wheel_sha256']}
  report['result']='PASS'
 finally: save()
if __name__=='__main__': main()
