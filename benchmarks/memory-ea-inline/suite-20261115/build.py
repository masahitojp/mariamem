from pathlib import Path
import os,subprocess,json,hashlib,tarfile,io,difflib
W=Path(__file__).resolve().parents[1];S=W/'worktree';T=W/'temp';E=W/'evidence'
env=dict(os.environ,GOTOOLCHAIN='go1.27.4',CGO_ENABLED='0',GOMAXPROCS='8',GOGC='100')
identity=json.loads(subprocess.check_output(['python3',S/'scripts/git_identity.py','--root',S,'inspect','HEAD']));assert identity['source_commit']=='25d70adf6c942bd147f43683916a5b1f9e09218d';(E/'source.json').write_text(json.dumps(identity,indent=2))
prefix='benchmarks/sample-guest-cost/results-20261114/harness/'
a=tarfile.open(fileobj=io.BytesIO(subprocess.check_output(['git','archive','c09941e25ea8ca9ae77ea032d61a3268b72c7e50',prefix],cwd=S)))
for m in a.getmembers():
 if m.isfile():
  p=T/m.name[len(prefix):];p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(a.extractfile(m).read())
for engine in ['maria','pg']:
 p=T/(engine+'-suite')/'go.mod';p.write_text(p.read_text().replace('<PRODUCT_WORKTREE>',str(S)))
 # Preserve all existing close oracles and make each close failure fail the process.
 p=T/(engine+'-suite')/'store/fixture_test.go';x=p.read_text();before=x
 x=x.replace('"sync"','"sync"\n"sync/atomic"')
 anchor='var fx *fixture';assert anchor in x;x=x.replace(anchor,'var closeErrors atomic.Int64\nfunc checkedClose(err error){if err!=nil {fmt.Fprintln(os.Stderr,"CLOSE ERROR:",err);closeErrors.Add(1)}}\n'+anchor)
 for a,b in [('fx.sharedDB.Close()','checkedClose(fx.sharedDB.Close())'),('db.Close()','checkedClose(db.Close())'),('s.Close()','checkedClose(s.Close())'),('snap.Close()','checkedClose(snap.Close())'),('srv.Close()','checkedClose(srv.Close())')]:
  # Replace only bare calls, leaving calls that already propagate error untouched.
  import re
  x=re.sub(r'(?m)(?<![\w.])'+re.escape(a)+r'(?=\s*[;})\n])',b,x)
 # Avoid wrapping db.Close inside fx.sharedDB.Close a second time (negative lookbehind handles it).
 x=x.replace('if err := checkedClose(srv.Close()); err != nil { return err }','if err := srv.Close(); err != nil { return err }')
 x=x.replace('code := m.Run()','code := m.Run()').replace('if err := fx.rec.Write(', 'if closeErrors.Load()!=0 {code=1}\n if err := fx.rec.Write(')
 if engine=='maria':
  mark='done=f.rec.Start("reader_fork"';assert mark in x;x=x.replace(mark,'if err:=srv.Close();err!=nil{return err}\n '+mark)
 (E/(engine+'-fixture.diff')).write_text(''.join(difflib.unified_diff(before.splitlines(True),x.splitlines(True))))
 p.write_text(x)
p=S/'internal/generatedgo/code/base/base.go';x=p.read_text();a='\t\tWasm_trap_memory_oob()';assert x.count(a)==1;x=x.replace(a,'\t\tpanic("wasm: memory access out of bounds")');a='\n//go:noinline\nfunc Wasm_trap_memory_oob() { panic("wasm: memory access out of bounds") }\n';assert x.count(a)==1;x=x.replace(a,'')
c=T/'candidate-base.go';c.write_text(x);prov=json.loads((S/'benchmarks/memory-ea-inline/runtime-20261114/installed-provenance.json').read_text());assert hashlib.sha256(c.read_bytes()).hexdigest()==prov['files_sha256']['code/base/base.go']
(E/'candidate-overlay.json').write_text(json.dumps({'Replace':{str(p):str(c)}},indent=2));(E/'candidate-source-sha256.txt').write_text(hashlib.sha256(c.read_bytes()).hexdigest())
results={}
for label,engine in [('baseline','maria'),('candidate','maria'),('pg','pg')]:
 extra=['-overlay',str(E/'candidate-overlay.json')] if label=='candidate' else []
 cmd=['go','test','-c','-vet=off','-p','1',*extra,'-o',str(T/(label+'.test')),'./store']
 with (E/(label+'-build.log')).open('w')as f:subprocess.run(cmd,cwd=T/(engine+'-suite'),env=env,stdout=f,stderr=f,check=True,timeout=1200)
 b=T/(label+'.test');results[label]={'sha256':hashlib.sha256(b.read_bytes()).hexdigest(),'bytes':b.stat().st_size};print(label+' BUILD PASS',flush=True)
(E/'binaries.json').write_text(json.dumps(results,indent=2))
r=subprocess.check_output(['go','list','-m','-json','github.com/shibukawa/pgmem'],cwd=T/'pg-suite',env=env);(E/'pg-module.json').write_bytes(r)
r=subprocess.check_output(['go','mod','download','-json','github.com/shibukawa/pgmem@v1.18.2'],cwd=T/'pg-suite',env=env);j=json.loads(r);assert j['Origin']['Hash']=='a61005d37d01e6671f814fe8ca828222e8147df4';(E/'pg-module-origin.json').write_bytes(r)
