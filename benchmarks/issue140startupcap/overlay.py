from pathlib import Path
import sys,json,hashlib,re,subprocess
s,o=map(lambda p:Path(p).resolve(),sys.argv[1:]);subprocess.run(['python3',str(s/'benchmarks/issue140readsetting/overlay.py'),str(s),str(o)],check=True);mapping=json.loads((o/'overlay.json').read_text());d=s/'benchmarks/issue140startupcap';records=[]
def body(t,fn):return re.search(r'^func '+fn+r'\(.*?(?=\nfunc |\Z)',t,re.M|re.S).group()
bindings=json.loads((d/'source-functions.json').read_text())
for fn,info in bindings.items():assert hashlib.sha256(body((s/info['path']).read_text(),fn).encode()).hexdigest()==info['sha256']
def edit(path,fn,changes):
 p=s/path;original=p.read_text();text=Path(mapping['Replace'].get(str(p),str(p))).read_text();before=body(text,fn);after=before
 for a,b in changes:assert after.count(a)==1,(fn,a);after=after.replace(a,b,1)
 text=text.replace(before,after,1);out=o/('cap-'+str(len(records))+'.go');out.write_text(text);mapping['Replace'][str(p)]=str(out);records.append({'path':path,'function':fn,'original_sha256':hashlib.sha256(original.encode()).hexdigest(),'original_function_sha256':hashlib.sha256(body(original,fn).encode()).hexdigest(),'overlaid_sha256':hashlib.sha256(text.encode()).hexdigest()})
edit(bindings['Fn17499']['path'],'Fn17499',[('m.T0[v13].(func(*base.Module, int32, int32))(m, v9, v11)','m.T0[v13].(func(*base.Module, int32, int32))(m, v9, base.StartupCapArg(m,v9,v11,"load"))')])
edit(bindings['Fn18569']['path'],'Fn18569',[('m.T0[v19427].(func(*base.Module, int32, int32))(m, v19423, v19425)','m.T0[v19427].(func(*base.Module, int32, int32))(m, v19423, base.StartupCapArg(m,v19423,v19425,"recovery"))')])
p=s/bindings['Fn16604']['path'];text=Path(mapping['Replace'].get(str(p),str(p))).read_text();b=body(text,'Fn16604');needle='*(*int32)(unsafe.Add(mBase, base.MemoryEA(m, uint64(uint32(l0)), 344, 4))) = v25';assert b.count(needle)==2;a=b.replace(needle,needle+'\nbase.ResolveStartupCap(m,l0,v25,v20,v17)');out=o/'cap-resolved.go';out.write_text(text.replace(b,a,1));mapping['Replace'][str(p)]=str(out)
# Registration occurs even when the expensive read observer is disabled.
p=s/'internal/generatedgo/code/base/read_observe.go';text=Path(mapping['Replace'][str(p)]).read_text();needle='func RegisterReadObservation(m *Module, db string) func() {';assert text.count(needle)==1;text=text.replace(needle,needle+'\nRegisterStartupCap(m,db)',1);out=o/'cap-read.go';out.write_text(text);mapping['Replace'][str(p)]=str(out)
for name in ('cap.go','cap_test.go'):mapping['Replace'][str(s/'internal/generatedgo/code/base'/name)]=str(d/(name+'.txt'))
p=s/'benchmarks/issue88modelcase/maria/store/fixture_test.go';text=Path(mapping['Replace'][str(p)]).read_text();needle='must(base.WriteReadObservation(os.Getenv("READ_OBSERVATION_OUT")))';assert text.count(needle)==1;text=text.replace(needle,needle+'\n must(base.WriteStartupCaps(os.Getenv("STARTUP_CAP_OUT")))',1);out=o/'cap-fixture.go';out.write_text(text);mapping['Replace'][str(p)]=str(out)
(o/'overlay.json').write_text(json.dumps(mapping,indent=2)+'\n')
records.extend({'path':str(Path(p).relative_to(s)),'before_sha256':hashlib.sha256(Path(p).read_bytes()).hexdigest() if Path(p).exists() else None,'after_sha256':hashlib.sha256(Path(q).read_bytes()).hexdigest()} for p,q in sorted(mapping['Replace'].items()))
(o/'cap-hashes.json').write_text(json.dumps(records,indent=2)+'\n')
