"""Generate real atomic WASM lowering, then observe bounded heap/mmap patterns."""
import argparse,hashlib,json,os,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'scripts'))
from runtime_atomic_loads import apply
p=argparse.ArgumentParser();p.add_argument('--converter',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
out=a.output.resolve();out.mkdir(parents=True,exist_ok=False);module=out/'module';module.mkdir()
def u(n):
 b=[]
 while n>=128:b.append((n&127)|128);n>>=7
 return bytes(b+[n])
def vec(xs):return u(len(xs))+b''.join(xs)
def sec(k,b):return bytes([k])+u(len(b))+b
def typ(ps,rs):return b'\x60'+vec([bytes([v]) for v in ps])+vec([bytes([v]) for v in rs])
types=[typ([0x7f],[0x7f]),typ([0x7f,0x7f],[]),typ([0x7f,0x7f],[0x7f]),typ([0x7f,0x7f,0x7f],[0x7f]),typ([],[])]
funcs=[]
for name,t,opcode,align,params in [('Load8',0,0x12,0,1),('Load16',0,0x13,1,1),('Store8',1,0x19,0,2),('Store16',1,0x1a,1,2),('Add8',2,0x20,0,2),('Add16',2,0x21,1,2),('Cmp8',3,0x4a,0,3),('Cmp16',3,0x4b,1,3)]:
 code=b''.join(b'\x20'+u(i) for i in range(params))+b'\xfe'+u(opcode)+u(align)+u(0)
 funcs.append((name,t,code))
# NOP padding selects the converter's normal multi-package path, keeping the
# same exported-helper lowering as the real guest. No output is hand-edited.
funcs.append(('Padding',4,b'\x01'*(1<<20)))
wasm=b'\0asm\x01\0\0\0'+sec(1,vec(types))+sec(3,vec([u(t) for _,t,_ in funcs]))+sec(5,b'\x01\x03\x01\x02')+sec(7,vec([u(len(n))+n.encode()+b'\0'+u(i) for i,(n,_,_) in enumerate(funcs)]))+sec(10,vec([u(len(c)+2)+b'\0'+c+b'\x0b' for _,_,c in funcs]))
fixture=out/'atomic.wasm';fixture.write_bytes(wasm);converter=a.converter.resolve()
pins=json.loads((ROOT/'release/generated-go-translation.json').read_text())
assert hashlib.sha256(converter.read_bytes()).hexdigest()==pins['patched_converter_sha256'], 'converter differs from canonical fixed input'
subprocess.run([str(converter),'-pure','-i',str(fixture),'-out-dir',str(module/'fixture'),'-pkg','fixture','-import','example.com/feasibility/fixture'],check=True)
base=module/'fixture/base';f=base/'base.go';f.write_text(apply(f.read_text()))
for src in (ROOT/'scripts/runtime_correctness').glob('narrow_*'):
 if not src.name.endswith(('.go.txt', '.s.txt')):continue
 if src.name.endswith('_test.go.txt'):continue
 shutil.copy2(src,base/src.name.removesuffix('.txt'))
shutil.copy2(ROOT/'internal/generatedgo/code/base/memory_mapping.go',base/'memory_mapping.go')
shutil.copy2(Path(__file__).with_name('matrix_test.go.txt'),base/'matrix_test.go')
(module/'go.mod').write_text('module example.com/feasibility\n\ngo 1.26.0\n')
env=dict(os.environ,GOTOOLCHAIN='go1.26.8',GOWORK='off',GOENV='off',GOFLAGS='',GOEXPERIMENT='',GOMAXPROCS='2')
rows=[]
for race in (False,True):
 for backing in ('heap','mmap'):
  for bits in (8,16):
   cases=[(op,rel) for op in ('load','store','rmw','cmpxchg') for rel in ('neighbor','overlap')]+[('shadow','overlap')]
   for op,rel in cases:
    key=f'{op}-{rel}-{bits}-{backing}'+('-race' if race else '')
    r=subprocess.run(['go','test','-p','1',*(('-race',) if race else()),'-count=1','-v','-run','^TestMatrix$','./fixture/base'],cwd=module,env={**env,'STUDY_OP':op,'STUDY_RELATION':rel,'STUDY_BITS':str(bits),'STUDY_BACKING':backing},capture_output=True,text=True,timeout=180)
    log=r.stdout+r.stderr;(out/(key+'.txt')).write_text(log)
    observations=[json.loads(x.split('OBS ',1)[1]) for x in log.splitlines() if 'OBS ' in x]
    if '[build failed]' in log or '[setup failed]' in log or not observations:raise RuntimeError('No semantic observation: '+key+'\n'+log[-3000:])
    rows.append({'key':key,'race':race,'exit_code':r.returncode,'race_reports':log.count('WARNING: DATA RACE'),'observations':observations,'log_sha256':hashlib.sha256(log.encode()).hexdigest()});print(key,r.returncode,rows[-1]['race_reports'],flush=True)
   key=f'store-buffering-{bits}-{backing}'+('-race' if race else '')
   r=subprocess.run(['go','test','-p','1',*(('-race',) if race else()),'-count=1','-v','-run','^TestStoreBuffering$','./fixture/base'],cwd=module,env={**env,'STUDY_BITS':str(bits),'STUDY_BACKING':backing},capture_output=True,text=True,timeout=180)
   (out/(key+'.txt')).write_text(r.stdout+r.stderr);rows.append({'key':key,'race':race,'exit_code':r.returncode,'race_reports':(r.stdout+r.stderr).count('WARNING: DATA RACE'),'trials':1000})
report={'fixture_sha256':hashlib.sha256(wasm).hexdigest(),'converter_sha256':hashlib.sha256(converter.read_bytes()).hexdigest(),'scope':'Limited real-opcode lowering; no full guest census or general shared-memory proof','checks':rows}
(out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
