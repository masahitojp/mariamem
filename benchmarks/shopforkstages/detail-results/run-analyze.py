from pathlib import Path
import hashlib,json,math,os,subprocess,time
W=Path(__file__).resolve().parents[1];T=W/'temp';E=W/'evidence'
inputs=json.loads((E/'inputs.json').read_text());binary=T/'bin-current'
assert hashlib.sha256(binary.read_bytes()).hexdigest()==inputs['binary_sha256']
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=W/'worktree',text=True).strip()==inputs['harness_source_commit']
scratch=T/'analyze-scratch';scratch.mkdir(exist_ok=True);trace=T/'analyze-timing';trace.mkdir(exist_ok=True)
env={k:v for k,v in os.environ.items() if not k.startswith(('GO','MARIAMEM_','MYSQLMEM_','ISSUE','MODELCASE_','FORK_STAGE','SHOP_PARALLEL','TIMER_','ANALYZE_'))}
env.update(GOMAXPROCS='8',GOGC='100',TMPDIR=str(scratch),TIMER_ANALYZE_PROBE='1',ANALYZE_PROBE_PATH=str(E/'analyze.json'),FORK_STAGES='1',FORK_STAGE_PATH=str(E/'analyze-stages.json'),SHOP_PARALLEL='4',MARIAMEM_TIMING_DIR=str(trace),ISSUE88_POOL_MIB='16')
with (E/'analyze-console.txt').open('w') as log:
 proc=subprocess.run([str(binary),'-test.timeout=60s'],cwd=T/'runner',env=env,stdout=log,stderr=subprocess.STDOUT,timeout=75)
assert proc.returncode==0,proc.returncode
raw=json.loads((E/'analyze.json').read_text());assert raw['subsequent_select']=='PASS' and raw['active_mappings_after']==0 and not list(scratch.iterdir())
assert len(raw['rows'])==6
from assess_analyze import assess
result=assess(raw,inputs)
(E/'analyze-assessment.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
