"""Run two bounded P4 observations; keep compact per-startup attribution."""
from pathlib import Path
import hashlib,json,os,platform,subprocess,sys,time
S=Path(sys.argv[1]).resolve();W=S.parent;T=W/'temp';E=W/'evidence'
p=json.loads((E/'inputs.json').read_text())
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=S,text=True).strip()==p['harness_source_commit']
assert not subprocess.check_output(['git','status','--porcelain'],cwd=S)
assert hashlib.sha256((T/'bin-current').read_bytes()).hexdigest()==p['binary_sha256']
env={k:v for k,v in os.environ.items() if not k.startswith(('GO','MARIAMEM_','MYSQLMEM_','LC_STAGE_','LEXER_','CLOSE_DIAG_','ISSUE','MODELCASE_','SAMPLE_DIAG','FORK_STAGE','SHOP_PARALLEL'))}
env.update(GOMAXPROCS='8',GOGC='100',ISSUE88_POOL_MIB='16',SHOP_PARALLEL='4',FORK_STAGES='1')
records=[]
for repeat in range(2):
 scratch=T/f'uca-run-{repeat}';scratch.mkdir();trace=T/f'uca-trace-{repeat}.json';stages=T/f'uca-stages-{repeat}.json';timing=T/f'uca-timing-{repeat}';timing.mkdir()
 local=dict(env,TMPDIR=str(scratch),MODELCASE_TRACE=str(trace),FORK_STAGE_PATH=str(stages),MARIAMEM_TIMING_DIR=str(timing))
 with (T/f'uca-run-{repeat}.txt').open('w') as log:
  result=subprocess.run([str(T/'bin-current'),'-test.parallel=4','-test.timeout=140s','-test.count=1'],cwd=T/'runner',env=local,stdout=log,stderr=subprocess.STDOUT,timeout=150)
 assert result.returncode==0,(repeat,result.returncode)
 data=json.loads(trace.read_text());d=json.loads(stages.read_text());m=data['meta']
 assert m['read_cases']=='50' and m['write_cases']=='20' and m['active_mappings_after']=='0' and m['fork_cap']=='5'
 assert not list(scratch.iterdir());assert len(d)==22
 for k,n in [('read',50),('write',20),('fork',21),('sample',21)]:assert sum(x['kind']==k for x in data['spans'])==n
 record=dict(repeat=repeat,meta=m,elapsed_ms=data['elapsed_ms'],exit_code=0,scratch_empty=True,startups={lane:{'common_details':v['startup']['common_details'],'common_counts':v['startup']['common_counts']} for lane,v in d.items()})
 records.append(record);(E/'uca-observations.json').write_text(json.dumps(records,separators=(',',':'))+'\n');print('PASS',repeat,flush=True)
(E/'uca-host.json').write_text(json.dumps(dict(platform=platform.platform(),cpu=subprocess.check_output(['sysctl','-n','machdep.cpu.brand_string'],text=True).strip(),memory_bytes=int(subprocess.check_output(['sysctl','-n','hw.memsize'],text=True))),indent=2)+'\n')
