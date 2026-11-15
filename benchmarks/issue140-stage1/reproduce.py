from pathlib import Path
import os,sys,json,subprocess,tarfile,hashlib,time,platform
S=Path.cwd();T=Path(os.environ['MARIAMEM_EXPERIMENT_TEMP']);E=Path(os.environ['MARIAMEM_EXPERIMENT_EVIDENCE'])
SHA='2ef14ee2de5c16ffff715cf12f275b8f1338c253';HARNESS='d24087eedd21c6384c231fb119c8e98da7b370aa';INJECT='e556c36570e1be023f8a9c8243381c6605079592:benchmarks/uca-p8-attribution/reproduction/instrument.py'
def dump(p,v):p.write_text(json.dumps(v,indent=2)+'\n')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def git(*args):return subprocess.check_output(['git',*args],cwd=S)
def archive(ref,paths,dest):
 p=T/'archive.tar';p.write_bytes(git('archive',ref,*paths))
 with tarfile.open(p) as a:a.extractall(dest,filter='data')
 p.unlink()
def inventory(p):return {str(f.relative_to(p)):sha(f) for f in sorted(p.rglob('*')) if f.is_file()}
identity=json.loads(subprocess.check_output([sys.executable,'scripts/git_identity.py','inspect',SHA],cwd=S));assert identity['object_type']=='commit' and identity['source_commit']==SHA
root=T/'product';root.mkdir();archive(SHA,[],root);archive(HARNESS,['tests/timer_calibration/runner'],root)
runner=root/'tests/timer_calibration/runner';before=inventory(root/'internal/generatedgo')
inject=T/'instrument.py';inject.write_bytes(git('show',INJECT));subprocess.run([sys.executable,inject,S,runner],check=True)
p=runner/'maria/store/sample_observe.go';s=p.read_text();assert 'if duration >= 50000 {' in s
p.write_text(s.replace('if duration >= 50000 {','if phase == "prepare" || duration >= 50000 {').replace('json:"operations_ge50ms"','json:"prepare_calls_and_operations_ge50ms"'))
subprocess.run(['gofmt','-w',p],check=True)
env={k:v for k,v in os.environ.items() if not k.startswith(('GO','MARIAMEM_','MYSQLMEM_','GIT_','LC_STAGE_','LEXER_','CLOSE_DIAG_','ISSUE','MODELCASE_','SAMPLE_','FORK_STAGE','SHOP_','TIMER_','ANALYZE_'))}
env.update(GOCACHE=str(T/'gocache'),GOPATH=str(T/'gopath'),GOMODCACHE=str(T/'modcache'),GOTOOLCHAIN='go1.26.10',GOWORK='off',GOENV='off',GOFLAGS='',GOEXPERIMENT='',GOMAXPROCS='2',CGO_ENABLED='0',PYTHONDONTWRITEBYTECODE='1',TMPDIR=str(T/'tmp'),GOTMPDIR=str(T/'go-tmp'))
record=dict(source=identity,harness_commit=HARNESS,injection=INJECT,injection_sha256=sha(inject),runtime_inventory_sha256=hashlib.sha256(json.dumps(before,sort_keys=True).encode()).hexdigest(),guest_sha256=json.loads((root/'release/generated-go-inputs.json').read_text())['guest_sha256'],harness_files=inventory(runner),environment=dict(platform=platform.platform(),python=sys.version,go='go1.26.10'),capture_enabled=False,expected_processes=4)
dump(E/'inputs.json',record)
binary=T/'stage1.test'
cmd=['go','test','-mod=readonly','-p','1','-trimpath','-buildvcs=false','-c','-o',binary,'./maria/store']
record['build_command']=list(map(str,cmd));dump(E/'inputs.json',record)
with (T/'build.log').open('w') as log:subprocess.run(cmd,cwd=runner,env=env,stdout=log,stderr=subprocess.STDOUT,check=True,timeout=1200)
assert before==inventory(root/'internal/generatedgo')
record['binary_sha256']=sha(binary);record['buildinfo']=subprocess.check_output(['go','version','-m',binary],env=env,text=True);dump(E/'inputs.json',record)
rows=[];env.update(GOMAXPROCS='8',GOGC='100',ISSUE88_POOL_MIB='16',FORK_STAGES='0',SHOP_PARALLEL='8',ISSUE88_SAMPLE_PHASES='1',ISSUE68_CAPTURE='0',ISSUE68_CONTROL='0')
for i in range(4):
 d=T/f'run{i}';d.mkdir();scratch=d/'scratch';scratch.mkdir()
 local=dict(env,TMPDIR=str(scratch),MODELCASE_TRACE=str(d/'trace.json'),SAMPLE_PHASES_OUT=str(d/'sql.json'))
 start=time.monotonic()
 with (d/'console.txt').open('w') as log:r=subprocess.run(['/usr/bin/time','-l',binary,'-test.parallel=8','-test.timeout=140s','-test.count=1'],cwd=runner,env=local,stdout=log,stderr=subprocess.STDOUT,timeout=150)
 if r.returncode:
  (E/f'failure-{i}.txt').write_text((d/'console.txt').read_text());raise RuntimeError(f'run {i}: exit {r.returncode}')
 trace=json.loads((d/'trace.json').read_text());m=trace['meta'];spans=trace['spans'];sql=json.loads((d/'sql.json').read_text())
 for k,v in {'route':'Pipe','read_cases':'50','write_cases':'20','test_exit':'0','parallel':'8','fork_cap':'9','active_mappings_after':'0','innodb_buffer_pool_size':'16777216','innodb_read_io_threads':'1'}.items():assert m[k]==v,(i,k,m)
 for k,n in [('fork',21),('sample',21),('read',50),('write',20)]:assert sum(s['kind']==k for s in spans)==n,(i,k)
 assert len(sql)==21 and not list(scratch.iterdir()) and not (d/'captures').exists()
 for sample in sql:
  dd=sample['durations_us'];assert len(dd['prepare'])==3 and len(dd['order_insert'])==40 and len(dd['item_insert'])==len(dd['stock_update'])==100 and len(dd['commit'])==1
  calls=[x for x in sample['prepare_calls_and_operations_ge50ms'] if x['phase']=='prepare'];assert len(calls)==3
 row=dict(process=i,process_wall_ms=(time.monotonic()-start)*1000,trace=trace,loaders=sql,exit_code=0,scratch_empty=True)
 rows.append(row);dump(E/'observations.json',rows)
 long=[dict(process=i,db_id=s['db_id'],lane=s['lane'],**x) for s in sql for x in s['prepare_calls_and_operations_ge50ms'] if x['phase']=='prepare' and x['duration_us']>=100000]
 print('PROCESS',i,'PASS','long_prepare',len(long),flush=True)
long=[dict(process=r['process'],db_id=s['db_id'],lane=s['lane'],**x) for r in rows for s in r['loaders'] for x in s['prepare_calls_and_operations_ge50ms'] if x['phase']=='prepare' and x['duration_us']>=100000]
dump(E/'summary.json',dict(result='REOBSERVED' if long else 'NOT_REPRODUCED',source_commit=SHA,processes=4,cases=280,prepare_calls=252,long_prepare=long,max_prepare_us=max(x for r in rows for s in r['loaders'] for x in s['durations_us']['prepare']),suite_elapsed_ms=[r['trace']['elapsed_ms'] for r in rows]))
print((E/'summary.json').read_text(),flush=True)
