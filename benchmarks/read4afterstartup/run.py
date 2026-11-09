"""One-host read1/read4 screening; no runtime sampler, adoption, or publication."""
import hashlib,json,os,pathlib,platform,subprocess,sys,time
w=pathlib.Path(sys.argv[1]).resolve();s=w/'worktree';t=w/'temp';e=w/'evidence';b=s/'benchmarks/issue88modelcase';d=s/'benchmarks/read4afterstartup'
env={k:v for k,v in os.environ.items() if not k.startswith(('MARIAMEM_','MYSQLMEM_','ISSUE','LC_STAGE_','LEXER_'))}
env.update(CGO_ENABLED='0',GOMAXPROCS='8',GOGC='100',GOTOOLCHAIN='local',GOWORK='off',GOENV='off',GOFLAGS='',GOCACHE=str(t/'gocache'),GOMODCACHE=str(t/'gomodcache'),ISSUE88_POOL_MIB='16',ISSUE88_SAMPLE_PHASES='1')
def run(args,cwd=s,timeout=900):
 r=subprocess.run(args,cwd=cwd,env=env,capture_output=True,text=True,timeout=timeout)
 if r.returncode:
  (e/'failure.txt').write_text(repr(args)+'\n'+r.stdout+r.stderr);r.check_returncode()
 return r
identity=json.loads(run(['python3','scripts/git_identity.py','inspect','HEAD']).stdout)
assert not run(['git','status','--porcelain']).stdout
plan=json.loads((d/'plan.json').read_text())
assert not run(['git','diff',plan['base_commit'],'--','internal','guest','release','go.mod','go.sum']).stdout
assert platform.system()=='Darwin' and platform.machine()=='arm64'
inputs={'source':identity,'plan':plan,'host':{'platform':platform.platform(),'go':run(['go','version']).stdout.strip(),'cpu':run(['sysctl','-n','machdep.cpu.brand_string']).stdout.strip(),'memory':run(['sysctl','-n','hw.memsize']).stdout.strip()},'measurement_environment':{k:env[k] for k in ('GOMAXPROCS','GOGC','CGO_ENABLED','GOTOOLCHAIN','ISSUE88_POOL_MIB','ISSUE88_SAMPLE_PHASES')}}
# Intervene only at the existing argv handoff. Read1 validates but does not mutate.
p=s/'internal/generatedgo/code/p5/p5_pure.go';old=p.read_text();needle='v107 = Fn5739(m, int32(25), v8)';assert old.count(needle)==1
new=old.replace(needle,'v107 = Fn5739(m, base.PoolArgv(m, int32(25), v8), v8)');o=t/'overlay';o.mkdir(parents=True,exist_ok=True);(o/'p5_pure.go').write_text(new)
replaces={str(p):str(o/'p5_pure.go'),str(s/'internal/generatedgo/code/base/read4_selector.go'):str(d/'selector.go.txt'),str(s/'internal/generatedgo/code/base/read4_selector_test.go'):str(d/'selector_test.go.txt')}
(o/'overlay.json').write_text(json.dumps({'Replace':replaces},indent=2)+'\n')
inputs['overlay']={'generated_path':str(p.relative_to(s)),'before_sha256':hashlib.sha256(old.encode()).hexdigest(),'after_sha256':hashlib.sha256(new.encode()).hexdigest(),'selector_sha256':hashlib.sha256((d/'selector.go.txt').read_bytes()).hexdigest()}
(e/'inputs.json').write_text(json.dumps(inputs,indent=2)+'\n')
print('Focused selector tests',flush=True)
r=run(['go','test','-overlay',str(o/'overlay.json'),'-run','^TestReadSetting','./internal/generatedgo/code/base'],timeout=180);(e/'unit.txt').write_text(r.stdout+r.stderr)
print('Build one binary',flush=True);start=time.monotonic()
r=run(['go','test','-c','-trimpath','-mod=readonly','-overlay',str(o/'overlay.json'),'-o',str(t/'probe'),'./maria/store'],cwd=b,timeout=900);(e/'build.txt').write_text(r.stdout+r.stderr)
inputs.update(binary_sha256=hashlib.sha256((t/'probe').read_bytes()).hexdigest(),build_seconds=time.monotonic()-start,build_info=run(['go','version','-m',str(t/'probe')]).stdout.replace(str(w),'<WORKSPACE>'))
(e/'inputs.json').write_text(json.dumps(inputs,indent=2)+'\n')
steps=[('warmup',-1,1),('warmup',-1,4)]
for pair in range(5):
 for arm in ((1,4) if pair%2==0 else (4,1)): steps.append(('natural',pair,arm))
observations=[]
for index,(kind,pair,arm) in enumerate(steps):
 name=f'{index:02d}-{kind}-read{arm}';env.update(ISSUE140_READ_THREADS=str(arm),MODELCASE_TRACE=str(e/(name+'-trace.json')),SAMPLE_PHASES_OUT=str(e/(name+'-sql.json')))
 print(name,flush=True)
 r=run([str(t/'probe'),'-test.parallel=8','-test.timeout=120s','-test.count=1'],cwd=b,timeout=130);(e/(name+'.txt')).write_text(r.stdout+r.stderr)
 trace=json.loads((e/(name+'-trace.json')).read_text());sql=json.loads((e/(name+'-sql.json')).read_text());meta=trace['meta']
 assert meta['read_cases']=='50' and meta['write_cases']=='20' and meta['active_mappings_after']=='0' and meta['test_exit']=='0'
 assert meta['innodb_read_io_threads']==str(arm) and meta['innodb_buffer_pool_size']==meta['innodb_buffer_pool_size_max']==str(16*2**20)
 assert len(sql)==21 and sum(x['kind']=='fork' for x in trace['spans'])==21
 assert sum(len(x['durations_us']['prepare']) for x in sql)==63
 observations.append({'name':name,'kind':kind,'pair':pair,'read_threads':arm,'trace':trace,'loaders':sql,'result':'PASS'})
 (e/'observations.json').write_text(json.dumps(observations,separators=(',',':'))+'\n')
 print('PASS wall_ms',trace['elapsed_ms'],'cpu_ms',meta['cpu_ms'],flush=True)
print('COMPLETE: two warmups and five alternating pairs; no additional samples',flush=True)
