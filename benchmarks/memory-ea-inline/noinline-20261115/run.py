from pathlib import Path
import os,subprocess,json,hashlib,tarfile,time,re,difflib
W=Path(__file__).resolve().parents[1];S=W/'worktree';T=W/'temp';E=W/'evidence'
env=dict(os.environ,GOTOOLCHAIN='go1.26.10',CGO_ENABLED='0',GOMAXPROCS='8',GOGC='100');durations={}
def run(name,cmd,cwd=S,timeout=1200):
 a=time.monotonic()
 with(E/(name+'.txt')).open('w')as f:subprocess.run(list(map(str,cmd)),cwd=cwd,env=env,stdout=f,stderr=f,check=True,timeout=timeout)
 durations[name]=time.monotonic()-a;(E/'durations.json').write_text(json.dumps(durations,indent=2));print(name,'PASS',round(durations[name],2),flush=True)
j=json.loads(subprocess.check_output(['python3',S/'scripts/git_identity.py','--root',S,'inspect','HEAD']));assert j['source_commit']=='523a8883d434af381f7a9d00a2c6ae571eefc172';(E/'source.json').write_text(json.dumps(j,indent=2));run('toolchain',['go','version'])
with tarfile.open(S/'benchmarks/memory-ea-inline/suite-20261115/harness.tar.gz')as a:a.extractall(T,filter='data')
p=T/'maria-suite/go.mod';p.write_text(re.sub(r'(?m)^go .*$', 'go 1.26.0',p.read_text()).replace('<PRODUCT_WORKTREE>',str(S)))
p=S/'internal/generatedgo/code/base/base.go';original=p.read_text();x=original;a='\t\tWasm_trap_memory_oob()';assert x.count(a)==1;x=x.replace(a,'\t\tpanic("wasm: memory access out of bounds")');a='\n//go:noinline\nfunc Wasm_trap_memory_oob() { panic("wasm: memory access out of bounds") }\n';assert x.count(a)==1;x=x.replace(a,'');assert hashlib.sha256(x.encode()).hexdigest()=='0170988abb28903ff3824a0e5efbe7865b0ba4961a892de7ce5bfca842ba332a'
texts={'baseline':original,'direct':x,'noinline':x.replace('func MemoryEA(', '//go:noinline\nfunc MemoryEA(')};assert texts['noinline'].replace('//go:noinline\nfunc MemoryEA(', 'func MemoryEA(')==x
(E/'source-hashes.json').write_text(json.dumps({k:hashlib.sha256(v.encode()).hexdigest()for k,v in texts.items()},indent=2))
for label in ['direct','noinline']:
 dst=T/(label+'-base.go');dst.write_text(texts[label]);(E/(label+'-overlay.json')).write_text(json.dumps({'Replace':{str(p):str(dst)}}));(E/(label+'-source.diff')).write_text(''.join(difflib.unified_diff(original.splitlines(True),texts[label].splitlines(True),fromfile='baseline/base.go',tofile=label+'/base.go')))
bins={};asm={}
for label in ['baseline','direct','noinline']:
 extra=[]if label=='baseline'else['-overlay',E/(label+'-overlay.json')]
 run(label+'-base-tests',['go','test','-p','1','-v','-count=1',*extra,'./internal/generatedgo/code/base'])
 run(label+'-runtime',['go','test','-p','1','-v','-count=1','-tags=integration',*extra,'./tests/generatedmemory','./internal/generatedgo','-run','TestPureMemory32|TestProcessImage|TestWorkerTrapActualGuest','-timeout=3m'])
 run(label+'-build',['go','test','-c','-vet=off','-p','1',*extra,'-o',T/(label+'.test'),'./store'],cwd=T/'maria-suite')
 b=T/(label+'.test');bins[label]={'bytes':b.stat().st_size,'sha256':hashlib.sha256(b.read_bytes()).hexdigest()};asm[label]={}
 for fn in ['MemoryEA','Fn13460','Fn15594','Fn18056','Fn18187']:
  run(label+'-'+fn+'-asm',['go','tool','objdump','-s',r'\.'+fn+'$',b],timeout=120)
  z=(E/(label+'-'+fn+'-asm.txt')).read_text();assert z.startswith('TEXT ');asm[label][fn]={'memory_ea_calls':z.count('CALL github.com/masahitojp/mariamem/internal/generatedgo/code/base.MemoryEA(SB)'),'panic_calls':z.count('CALL runtime.gopanic(SB)')}
(E/'binaries.json').write_text(json.dumps(bins,indent=2));(E/'assembly-summary.json').write_text(json.dumps(asm,indent=2))
run('noinline-compiler',['go','build','-p','1','-overlay',E/'noinline-overlay.json','-gcflags=github.com/masahitojp/mariamem/internal/generatedgo/code/base=-m=2','-o',T/'base.a','./internal/generatedgo/code/base'])
z=(E/'noinline-compiler.txt').read_text();assert 'cannot inline MemoryEA: marked go:noinline' in z
for fn in ['Fn13460','Fn15594','Fn18056','Fn18187']:assert asm['baseline'][fn]['memory_ea_calls']==asm['noinline'][fn]['memory_ea_calls']>0
assert asm['direct']['Fn13460']['memory_ea_calls']==0
# Compare helper opcodes while masking address-bearing panic constants and call relocations.
def helper_ops(label):
 z=(E/(label+'-MemoryEA-asm.txt')).read_text();return [re.split(r'\s+',l.strip(),3)[3]for l in z.splitlines()[1:]if '0x' in l]
a=helper_ops('direct');b=helper_ops('noinline');assert len(a)==len(b)
# Normal fast path ends at first RET; no addresses/constants in this prefix.
a=a[:next(i for i,v in enumerate(a)if v.startswith('RET'))+1];b=b[:next(i for i,v in enumerate(b)if v.startswith('RET'))+1];assert a==b
(E/'stage1.json').write_text(json.dumps({'status':'PASS','normal_path_direct_equals_noinline':True,'normal_path_instruction_count':len(a),'compiler_noinline_confirmed':True,'selected_callers_retained':True},indent=2))
run('campaign',['/opt/homebrew/bin/python3.14',E/'measure.py'],timeout=900)
run('analysis',['/opt/homebrew/bin/python3.14',E/'analyze.py'],timeout=60)
