from pathlib import Path
import json,os,subprocess,shutil,time,hashlib
W=Path(__file__).resolve().parents[1];S=W/'worktree';T=W/'temp';E=W/'evidence'
env=dict(os.environ,GOTOOLCHAIN='go1.26.10',CGO_ENABLED='0',GOMAXPROCS='8',GOGC='100')
changes=json.loads((E/'installed-changes.json').read_text());assert set(changes)<= {'code/base/base.go','provenance.json','image/layout.json'},changes
over={str(S/'internal/generatedgo'/p.relative_to(T/'installed')):str(p) for p in (T/'installed').rglob('*') if p.is_file() and p.suffix in ('.go','.s')}
(E/'candidate-overlay.json').write_text(json.dumps({'Replace':over},indent=2))
h=T/'harness';shutil.copytree(S/'benchmarks/memory-ea-inline/results-20261114/harness',h)
p=h/'go.mod';p.write_text(p.read_text().replace('<PRODUCT_WORKTREE>',str(S)).replace('go 1.27','go 1.26.0'))
for p in (h/'store').glob('*.go'):
 x=p.read_text();x=x.replace(' if err:=pgmem.ExperimentDump(os.Getenv("STAGES_FILE"));err!=nil{panic(err)}','');x=x.replace('  pgmem.ExperimentPhase(true)','').replace('  pgmem.ExperimentPhase(false)','');p.write_text(x)
def run(cmd,cwd,name,timeout):
 a=time.monotonic()
 with (E/(name+'.log')).open('w') as f:subprocess.run(cmd,cwd=cwd,env=env,stdout=f,stderr=f,check=True,timeout=timeout)
 print(name+' PASS',flush=True);return time.monotonic()-a
results={}
for label in ['baseline','candidate']:
 extra=['-overlay',str(E/'candidate-overlay.json')] if label=='candidate' else []
 run(['go','test','-p','1','-v','-count=1',*extra,'./internal/generatedgo/code/base'],S,label+'-base',300)
 run(['go','test','-p','1','-v','-count=1','-tags=integration',*extra,'./tests/generatedmemory','./internal/generatedgo','-run','TestPureMemory32|TestProcessImage|TestWorkerTrapActualGuest','-timeout=3m'],S,label+'-runtime',1200)
 seconds=run(['go','test','-c','-p','1',*extra,'-o',str(T/(label+'.test')),'./store'],h,label+'-build',1200)
 p=T/(label+'.test');results[label]={'build_seconds':seconds,'bytes':p.stat().st_size,'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
(E/'build-results.json').write_text(json.dumps(results,indent=2))
