from pathlib import Path
import os,subprocess,json,hashlib,sys
E=Path(__file__).resolve().parent;X=E.parent;T=X/'temp';variant=sys.argv[1];product=X/'worktree' if variant=='baseline' else T/'native/product';env=os.environ.copy();env.update(GOCACHE=str(T/'gocache'),GOMODCACHE=str(T/'modcache'),GOMAXPROCS='8',GOGC='100',CGO_ENABLED='0')
for name in ['correct','fault','recovery']:
 if variant=='baseline' and name=='correct':continue
 H=T/name;f=H/'go.mod';s=f.read_text();s=s[:s.index('replace github.com/masahitojp/mariamem')]+f'replace github.com/masahitojp/mariamem => {product}\n';f.write_text(s);replace={}

 if name=='fault':
  runtime=product/'internal/generatedgo/runtime_instance.go';text=runtime.read_text();assert text.count('w.SetFS(entropyFS{fs})')==1;text=text.replace('w.SetFS(entropyFS{fs})','w.SetFS(newBPFaultFS(fs))');patched=T/'fault-runtime-instance.go';patched.write_text(text);replace[str(runtime)]=str(patched);replace[str(product/'internal/generatedgo/buffer_fault_experiment.go')]=str(T/'buffer_fault_experiment.go')
 if name=='recovery':
  generated=(product/'internal/generatedgo/code/generated.go').read_text();key='var wasm2goData_data_bin = []byte("';a=generated.index(key)+len(key);z=generated.index('")',a);data=bytes.fromhex(generated[a:z].replace('\\x',''));message=b'InnoDB: Starting crash recovery from checkpoint LSN=';offset=data.find(message);assert offset>=0 and data.find(message,offset+1)==-1;address=8388608+offset;token=f'int32({address})';matches=[]
  for f in (product/'internal/generatedgo/code').glob('p*/p*_pure.go'):
   text=f.read_text()
   if token in text:matches.append((f,text))
  assert len(matches)==1 and matches[0][1].count(token)==1
  f,text=matches[0];lines=text.splitlines();line=next(i for i,l in enumerate(lines) if token in l);assert lines[line].strip().startswith('Fn') and f'(m, {token},' in lines[line];lines.insert(line,'\tbase.NoteBPRecovery()');patched=T/f'{variant}-recovery-code.go';patched.write_text('\n'.join(lines)+'\n');replace[str(f)]=str(patched);replace[str(product/'internal/generatedgo/code/base/buffer_recovery_witness.go')]=str(T/'buffer_recovery_witness.go');(E/f'{variant}-recovery-witness-site.json').write_text(json.dumps({'source':str(f),'line':line+1,'address':address,'message':message.decode(),'surrounding':matches[0][1].splitlines()[line-6:line+12]},indent=2))
  server=product/'internal/host/server.go';text=server.read_text();assert text.count('if purpose == shutdownDiscard {')==1;text=text.replace('if purpose == shutdownDiscard {','if purpose == shutdownDiscard || os.Getenv("MARIAMEM_BP_CRASH_FIXTURE_INTERNAL") == "1" {');patched=T/'recovery-server.go';patched.write_text(text);replace[str(server)]=str(patched)
 overlay=T/f'{variant}-{name}-overlay.json';overlay.write_text(json.dumps({'Replace':replace}));cmd=['go','build','-p','1','-trimpath','-buildvcs=false']
 if replace:cmd+=['-overlay',str(overlay)]
 out=T/f'{variant}-{name}';cmd+=['-o',str(out),'.'];print('building',variant,name,flush=True);subprocess.run(cmd,cwd=H,env=env,check=True)
 (E/f'{variant}-{name}-binary.json').write_text(json.dumps({'sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'overlays':{str(p):hashlib.sha256(Path(v).read_bytes()).hexdigest() for p,v in replace.items()}},indent=2)+'\n')
