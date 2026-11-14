from pathlib import Path
import os,subprocess,json,hashlib,time
E=Path(__file__).resolve().parent;T=E.parent/'temp';P=T/'native/product';source=P/'internal/generatedgo/runtime_instance.go';s=source.read_text();assert s.count('w.SetStderr(stderr)')==1;s=s.replace('w.SetStderr(stderr)','w.SetStderr(io.MultiWriter(stderr, os.Stderr))');patch=T/'negative-runtime.go';patch.write_text(s);overlay=T/'negative-overlay.json';overlay.write_text(json.dumps({'Replace':{str(source):str(patch)}}));env=os.environ.copy();env.update(GOCACHE=str(T/'gocache'),GOMODCACHE=str(T/'modcache'),GOMAXPROCS='8',GOGC='100',CGO_ENABLED='0',TMPDIR=str(T/'tmp'))
subprocess.run(['go','build','-p','1','-trimpath','-buildvcs=false','-overlay',str(overlay),'-o',str(T/'spike-negative'),'.'],cwd=T/'correct',env=env,check=True)
runenv=dict(env,MARIAMEM_BP_ZERO_MODE_INTERNAL='bad-descriptors');timeout=False;at=time.time()
with (E/'negative-descriptor.log').open('w') as f:
 try:r=subprocess.run([str(T/'spike-negative'),'-case','basic','-out',str(E/'negative-descriptor-raw.json')],env=runenv,stdout=f,stderr=subprocess.STDOUT,timeout=20);code=r.returncode
 except subprocess.TimeoutExpired:timeout=True;code=None
text=(E/'negative-descriptor.log').read_text();assert 'BP_ZERO_REJECT nonzero_descriptor' in text and (timeout or code!=0),text
raw=json.loads((E/'negative-descriptor-raw.json').read_text()) if (E/'negative-descriptor-raw.json').exists() else None
assert not raw or not raw['success']
(E/'negative-descriptor.json').write_text(json.dumps({'result':'REJECTED','explicit_check_marker':True,'exitcode':code,'timed_out':timeout,'elapsed_seconds':time.time()-at,'binary_sha256':hashlib.sha256((T/'spike-negative').read_bytes()).hexdigest(),'scope':'intentionally invalid descriptor initialization, stderr tee in this binary only; timeout does not prove graceful cleanup'},indent=2)+'\n');print('REJECTED missing descriptor clearing; timeout=',timeout,flush=True)
