import os,pathlib,subprocess,json,hashlib,platform,time,sys
w=pathlib.Path(sys.argv[1]).resolve();s=w/'worktree';t=w/'temp';e=w/'evidence';b=s/'benchmarks/issue88modelcase';env={k:v for k,v in os.environ.items() if not k.startswith(('MARIAMEM_','MYSQLMEM_','LC_STAGE_','LEXER_'))};env.update(CGO_ENABLED='0',GOMAXPROCS='8',GOGC='100',GOTOOLCHAIN='local',GOWORK='off',GOENV='off',GOFLAGS='',GOCACHE=str(t/'gocache'),GOMODCACHE=str(t/'gomodcache'),ISSUE88_POOL_MIB='16')
def run(args,cwd=s,timeout=600):
 r=subprocess.run(args,cwd=cwd,env=env,capture_output=True,text=True,timeout=timeout)
 if r.returncode:
  (e/'failure.txt').write_text(repr(args)+'\n'+r.stdout+r.stderr);r.check_returncode()
 return r
identity=json.loads(run(['python3','scripts/git_identity.py','inspect','HEAD']).stdout);assert identity['object_type']=='commit';assert not run(['git','status','--porcelain']).stdout;assert not run(['git','diff','a3b2b645','--','internal','guest','release','go.mod','go.sum']).stdout
plan=json.loads((s/'benchmarks/issue88samplephases/plan.json').read_text());inputs={'source':identity,'plan':plan,'host':{'platform':platform.platform(),'go':run(['go','version']).stdout.strip(),'cpu':run(['sysctl','-n','machdep.cpu.brand_string']).stdout.strip(),'memory':run(['sysctl','-n','hw.memsize']).stdout.strip()}}
(e/'inputs.json').write_text(json.dumps(inputs,indent=2)+'\n');run(['python3','benchmarks/issue88poolab/overlay.py',str(s),str(t/'overlay')]);overlay=str(t/'overlay/overlay.json');inputs['overlay']=json.loads((t/'overlay/hashes.json').read_text());print('BUILD diagnostic modelcase',flush=True);start=time.monotonic()
r=run(['go','test','-c','-trimpath','-mod=readonly','-overlay',overlay,'-o',str(t/'probe'),'./maria/store'],cwd=b,timeout=650);(e/'build.txt').write_text(r.stdout+r.stderr)
inputs.update(binary_sha256=hashlib.sha256((t/'probe').read_bytes()).hexdigest(),build_info=run(['go','version','-m',str(t/'probe')]).stdout.replace(str(w),'<WORKSPACE>'),build_seconds=time.monotonic()-start);(e/'inputs.json').write_text(json.dumps(inputs,indent=2)+'\n')
steps=[('warmup',-1,16,True),('warmup',-1,8,True),('observer_off',-1,16,False),('observer_off',-1,8,False)]+[('primary',pair,arm,True) for pair in range(5) for arm in ([16,8] if pair%2==0 else [8,16])]
obs=[]
for kind,pair,arm,enabled in steps:
 name=f'{kind}-p{pair}-pool{arm}';env.update(ISSUE88_POOL_MIB=str(arm),ISSUE88_SAMPLE_PHASES='1' if enabled else '0',MODELCASE_TRACE=str(e/(name+'-trace.json')),SAMPLE_PHASES_OUT=str(e/(name+'-sql.json')))
 print(name,flush=True);r=run([str(t/'probe'),'-test.parallel=8','-test.timeout=120s','-test.count=1'],cwd=b,timeout=130);(e/(name+'.txt')).write_text(r.stdout+r.stderr)
 trace=json.loads((e/(name+'-trace.json')).read_text());records=json.loads((e/(name+'-sql.json')).read_text()) or [];assert trace['meta']['read_cases']=='50' and trace['meta']['write_cases']=='20' and trace['meta']['test_exit']=='0' and trace['meta']['active_mappings_after']=='0'
 assert trace['meta']['innodb_buffer_pool_size']==str(arm*2**20) and trace['meta']['innodb_buffer_pool_size_max']==str(arm*2**20)
 if enabled:
  assert len(records)==21
  assert len({r['lane'] for r in records})==21
  for record in records:
   assert {k:len(v) for k,v in record['durations_us'].items()}==plan['per_loader_expected_counts']
   assert record['total_us']>=sum(sum(v) for v in record['durations_us'].values())
 else:assert not records
 obs.append({'phase':kind,'pair':pair,'pool_mib':arm,'trace':trace,'loaders':records});(e/'observations.json').write_text(json.dumps(obs,separators=(',',':'))+'\n')
print('ALL10 PRIMARY +2 WARMUP +2 SANITY PROCESSES PASS',flush=True)
