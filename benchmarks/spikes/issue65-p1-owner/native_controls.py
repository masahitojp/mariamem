"""Compile narrowly mutated host copies; unchanged native oracles must reject them."""
import argparse,importlib.util,json,subprocess
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--workspace',type=Path,required=True);a=p.parse_args();w=a.workspace.resolve();here=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('p1_baseline',here/'probe_baseline.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
product=w/'temp/host/product';main=product/'cmd/issue65-wire/main.go';owner=product/'internal/nativewire/owner.go';original={path:path.read_bytes() for path in (main,owner)};env=m.go_env(w);rows=[]
mutations=[('wrong_native_open_tuple',main,'kind: open, slot: s.id.slot, generation: s.id.generation, value: r.limit','kind: open, slot: 0, generation: 1, value: r.limit','TestOwnerHostIdentity','native session identity mismatch'),('early_native_retired',main,'r.completionOnce.Do(func() { close(entered) })','r.receiveFrame(frame{kind:retired,epoch:r.epoch,slot:0,generation:1});r.completionOnce.Do(func() { close(entered) })','TestOwnerNativeRetirementFence','RETIRED before Go completion'),('early_host_release',owner,'l.relays == Reader|Writer','l.relays&Writer != 0','TestOwnerHostRelayFence','native retirement forgave unjoined relay')]
try:
 for name,path,before,after,test,assertion in mutations:
  text=original[path].decode()
  if text.count(before)!=1:raise ValueError('native mutation anchor changed: '+name)
  path.write_text(text.replace(before,after));binary=w/'temp/host'/name
  subprocess.run(['go','test','-c','-p','1','-trimpath','-buildvcs=false','-o',str(binary),'./cmd/issue65-wire'],cwd=product,env=env,check=True,timeout=300)
  path.write_bytes(original[path])
  result=subprocess.run([str(binary),'-test.v','-test.run=^'+test+'$','-test.timeout=60s'],text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=75)
  (w/'evidence'/(name+'.txt')).write_text(result.stdout)
  if result.returncode==0 or assertion not in result.stdout:raise ValueError('native oracle failed to detect '+name)
  rows.append({'name':name,'test':test,'exit':result.returncode,'assertion':assertion,'binary_sha256':m.base.sha(binary)})
finally:
 for path,data in original.items():path.write_bytes(data)
(w/'evidence/native-controls.json').write_text(json.dumps({'cases':rows,'original_source_restored':all(path.read_bytes()==data for path,data in original.items())},indent=2)+'\n');print('PASS three detected native-route fault controls')
