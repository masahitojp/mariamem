from pathlib import Path
import os,subprocess,json,hashlib,tarfile,time
W=Path(__file__).resolve().parents[1];S=W/'worktree';T=W/'temp';E=W/'evidence'
env=dict(os.environ,GOTOOLCHAIN='go1.26.10',CGO_ENABLED='0',GOMAXPROCS='8',GOGC='100')
def run(name,cmd,cwd=S,timeout=1200):
 a=time.monotonic()
 with (E/(name+'.log')).open('w') as f:subprocess.run(list(map(str,cmd)),cwd=cwd,env=env,stdout=f,stderr=f,check=True,timeout=timeout)
 print(name,'PASS',round(time.monotonic()-a,2),flush=True)
identity=json.loads(subprocess.check_output(['python3',S/'scripts/git_identity.py','--root',S,'inspect','HEAD']));assert identity['source_commit']=='a75cf08b60c53c4a8391ebe81afd96c170e5c667';(E/'source.json').write_text(json.dumps(identity,indent=2))
run('toolchain',['go','version'])
run('lower-build',['go','build','-o',T/'lower',S/'benchmarks/memory-ea-inline/shared-lowering-20261115/lower.go'])
mapping={}; hashes={}
for pkg,fn,expected in [('p3','Fn13460','63009c1d79f292d391640f27ef98c443441a7cf1dbe453d63ac98b47757d596f'),('p1','Fn15594','65aeac005aaf658052b0ec37978d1f6b5b2a87308a06fdd782ff01f48ed257ee')]:
 src=S/f'internal/generatedgo/code/{pkg}/{pkg}_pure.go';dst=T/(pkg+'.go');run('lower-'+pkg,[T/'lower',src,dst,fn]);h=hashlib.sha256(dst.read_bytes()).hexdigest();assert h==expected;(hashes.update({pkg:h}));mapping[str(src)]=str(dst)
(E/'transformed-hashes.json').write_text(json.dumps(hashes,indent=2));(E/'overlay.json').write_text(json.dumps({'Replace':mapping},indent=2))
with tarfile.open(S/'benchmarks/memory-ea-inline/suite-20261115/harness.tar.gz') as a:a.extractall(T,filter='data')
p=T/'maria-suite/go.mod';x=p.read_text();import re
x=re.sub(r'(?m)^go .*$', 'go 1.26.0',x).replace('<PRODUCT_WORKTREE>',str(S));p.write_text(x)
results={}
for label in ['baseline','candidate']:
 extra=['-overlay',str(E/'overlay.json')]if label=='candidate'else[]
 run(label+'-runtime',['go','test','-p','1','-v','-count=1','-tags=integration',*extra,'./tests/generatedmemory','./internal/generatedgo','-run','TestPureMemory32|TestProcessImage|TestWorkerTrapActualGuest','-timeout=3m'])
 run(label+'-build',['go','test','-c','-vet=off','-p','1',*extra,'-o',T/(label+'.test'),'./store'],cwd=T/'maria-suite')
 b=T/(label+'.test');results[label]={'bytes':b.stat().st_size,'sha256':hashlib.sha256(b.read_bytes()).hexdigest()};(E/'binaries.json').write_text(json.dumps(results,indent=2))
run('campaign',['/opt/homebrew/bin/python3.14',E/'measure.py'],timeout=900)
run('analysis',['/opt/homebrew/bin/python3.14',E/'analyze.py'],timeout=60)
