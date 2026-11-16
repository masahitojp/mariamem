from pathlib import Path
import os,sys,subprocess,re,json,hashlib,shutil
r=Path(__file__).resolve().parents[2];d=Path(__file__).resolve().parent;w=Path(sys.argv[1]).resolve();t=w/'temp';e=w/'evidence'
identity=json.loads(subprocess.check_output([sys.executable,str(r/'scripts/git_identity.py'),'--root',str(r),'inspect','HEAD']));assert not subprocess.check_output(['git','status','--porcelain'],cwd=r)
assert json.loads((r/'release/generated-go-inputs.json').read_text())['guest_sha256']=='77b2ab49a9927f15c899ad34f9f40e5f06ac42589b1d4f926fd0c5b0f1f19450'
t.mkdir(exist_ok=True);e.mkdir(exist_ok=True);over={};changes=[]
def replace(s,a,b,n=1):
 assert s.count(a)==n,(a,s.count(a));return s.replace(a,b)
def edit(n,s):
 original=s
 if n==16594:
  s=replace(s,'if base.Ui32(v18) <= base.Ui32(v17) {','if base.Ui32(v18) <= base.Ui32(v17) {\n base.PoolObserve(m,"reject_max",l0,0)')
  s=replace(s,'if v55-v57 < v74 {','if v55-v57 < v74 {\n base.PoolObserve(m,"reject_throttle",l0,0)')
  s=replace(s,'if v83&v81 != 0 {','if v83&v81 != 0 {\n base.PoolObserve(m,"reject_pending",l0,0)')
 elif n==16593:
  s=replace(s,'if base.Ui32(v8) < base.Ui32(v9-(v10+v11)) {','if base.Ui32(v8) < base.Ui32(v9-(v10+v11)) {\n base.PoolObserve(m,"reject_concurrency",l0,0)')
 elif n==16602:
  s=replace(s,'Fn16593(m, l0)','base.PoolObserve(m,"enqueue",l0,l1)\n Fn16593(m, l0)',2)
 elif n==16591:
  a='*(*int32)(unsafe.Add(mBase, base.MemoryEA(m, uint64(uint32(l0)), 156, 4))) = v279';s=replace(s,a,a+'\n base.PoolObserve(m,"dequeue",l0,v268)')
 elif n==16592:
  a='base.AtomicStore32_8(m, l0, int32(408), v25)';s=replace(s,a,'base.PoolGate(m,l0)\n'+a+'\n base.PoolMark(m,"pending_clear",l0,l1)')
  a='m.T0[v47].(func(*base.Module, int32))(m, v43)';s=replace(s,a,'base.PoolMark(m,"execute_begin",l0,v43)\n'+a+'\n base.PoolMark(m,"execute_end",l0,v43)')
 elif n in [16603,16604]:
  a='*(*int32)(unsafe.Add(mBase, base.MemoryEA(m, uint64(uint32(l0)), 372, 4))) = '+('v29 + int32(1)'if n==16603 else'v24 - int32(1)')
  s=replace(s,a,a+'\n base.PoolObserve(m,"'+('wait_accounted'if n==16603 else'wait_unaccounted')+'",l0,0)')
 elif n in [16600,16784,18171]:
  pos=s.index('{')+1;label={16600:'maintenance',16784:'page_wait',18171:'page_complete'}[n];s=s[:pos]+f'\nbase.PoolMark(m,"{label}_begin",l0,0)\ndefer base.PoolMark(m,"{label}_end",l0,0)\n'+s[pos:]
 changes.append({'function':n,'original_sha256':hashlib.sha256(original.encode()).hexdigest(),'overlay_sha256':hashlib.sha256(s.encode()).hexdigest()});return s
for p in (r/'internal/generatedgo/code').glob('p*/*pure.go'):
 s=p.read_text();old=s
 for n in [16594,16593,16602,16591,16592,16603,16604,16600,16784,18171]:
  m=re.search(r'^func Fn'+str(n)+r'\(.*?(?=^func |\Z)',s,re.M|re.S)
  if m:s=s[:m.start()]+edit(n,m[0])+s[m.end():]
 if s!=old:q=t/(p.parent.name+'.go');q.write_text(s);over[str(p)]=str(q)
p=r/'internal/generatedgo/code/base/base.go';s=p.read_text().replace('import (','import (\n pooltrace "runtime/trace"')+'\n'+(d/'helper.go.txt').read_text();q=t/'base.go';q.write_text(s);over[str(p)]=str(q)
p=r/'internal/generatedgo/main.go';s=p.read_text();a='rc := base.AtomicWait32At(m, uint64(addr), expected, duration)';s=replace(s,a,'base.PoolWorkerWait(m,"futex_begin",addr)\n'+a+'\n base.PoolWorkerWait(m,"futex_end",addr)');q=t/'main.go';q.write_text(s);over[str(p)]=str(q)
shutil.copytree(r/'benchmarks/comparison-variance/harness/maria-suite',t/'suite',dirs_exist_ok=True);p=t/'suite/go.mod';p.write_text(p.read_text().replace('<MARIAMEM_SOURCE>',str(r)))
(t/'overlay.json').write_text(json.dumps({'Replace':over}));assert len(changes)==10
inputs={'source_identity':identity,'product_source_commit':'6558ee8fb2211313a8aa0ea6070ac5256767811a','methods':changes,'overlays':{str(Path(k).relative_to(r)):{'original':hashlib.sha256(Path(k).read_bytes()).hexdigest(),'overlay':hashlib.sha256(Path(v).read_bytes()).hexdigest()}for k,v in over.items()}}
(e/'inputs.json').write_text(json.dumps(inputs,indent=2));env=dict(os.environ,GOTOOLCHAIN='go1.27.4',GOCACHE=str(t/'go-cache'),CGO_ENABLED='0',GOWORK='off',GOFLAGS='',GOENV='off')
with(e/'build.txt').open('w')as f:
 subprocess.run(['go','build','-o',str(t/'gotrace'),'cmd/trace'],cwd=r,env=env,stdout=f,stderr=f,check=True)
 subprocess.run(['go','test','-c','-p','1','-vet=off','-overlay',str(t/'overlay.json'),'-o',str(t/'suite.test'),'./store'],cwd=t/'suite',env=env,stdout=f,stderr=f,check=True)
inputs['binary_sha256']=hashlib.sha256((t/'suite.test').read_bytes()).hexdigest();inputs['buildinfo']=subprocess.check_output(['go','version','-m',str(t/'suite.test')],env=env,text=True);(e/'inputs.json').write_text(json.dumps(inputs,indent=2));print('BUILD_COMPLETE',flush=True)
