import os,pathlib,subprocess,json,hashlib,platform,time,sys
w=pathlib.Path(sys.argv[1]).resolve();s=w/'worktree';t=w/'temp';e=w/'evidence';env={k:v for k,v in os.environ.items() if not k.startswith(('MARIAMEM_','MYSQLMEM_','ISSUE','LC_STAGE_','LEXER_'))};env.update(GOTOOLCHAIN='local',GOWORK='off',GOENV='off',GOFLAGS='',CGO_ENABLED='0',GOMAXPROCS='8',GOGC='100',GOCACHE=str(t/'gocache'),GOMODCACHE=str(t/'gomodcache'),ISSUE88_POOL_MIB='16')
for k in list(env):
 if k.startswith(('MARIAMEM_','LC_STAGE_','LEXER_')) and k not in ('MARIAMEM_EXPERIMENT_TEMP','MARIAMEM_EXPERIMENT_EVIDENCE'):env.pop(k)
def run(args,timeout=600):
 r=subprocess.run(args,cwd=s,env=env,capture_output=True,text=True,timeout=timeout)
 if r.returncode:
  (e/'failure.txt').write_text(r.stdout+r.stderr);r.check_returncode()
 return r
identity=json.loads(run(['python3','scripts/git_identity.py','inspect','HEAD']).stdout);assert identity['object_type']=='commit';assert not run(['git','status','--porcelain']).stdout
assert not run(['git','diff','279fa530','--','internal','guest','release','go.mod','go.sum']).stdout
inputs={'source':identity,'product_source_commit':'279fa530d03cab1bd025df91bf5130bbf845a721','origin_guest_sha256':json.loads((s/'release/generated-go-inputs.json').read_text())['guest_sha256'],'plan':json.loads((s/'benchmarks/issue88largecurrent/plan.json').read_text()),'host':{'platform':platform.platform(),'go':run(['go','version']).stdout.strip(),'cpu':run(['sysctl','-n','machdep.cpu.brand_string']).stdout.strip(),'memory':run(['sysctl','-n','hw.memsize']).stdout.strip()}}
(e/'inputs.json').write_text(json.dumps(inputs,indent=2)+'\n')
run(['python3','benchmarks/issue88largecurrent/overlay.py',str(s),str(t/'overlay')]);overlay=str(t/'overlay/overlay.json')
print('selector tests / build',flush=True);at=time.monotonic();r=run(['go','test','-overlay',overlay,'-count=1','-run','^TestPoolSelector$','./internal/generatedgo/code/base']);(e/'selector-tests.txt').write_text(r.stdout+r.stderr)
r=run(['go','build','-trimpath','-overlay',overlay,'-o',str(t/'probe'),'./benchmarks/issue88largecurrent']);(e/'build.txt').write_text(r.stdout+r.stderr)
run(['cc','-O2','benchmarks/tools/process_cost.c','-o',str(t/'process_cost')])
inputs.update(binary_sha256=hashlib.sha256((t/'probe').read_bytes()).hexdigest(),build_seconds=time.monotonic()-at,build_info=run(['go','version','-m',str(t/'probe')]).stdout.replace(str(w),'<WORKSPACE>'),overlay=json.loads((t/'overlay/hashes.json').read_text()))
(e/'inputs.json').write_text(json.dumps(inputs,indent=2)+'\n')
cells=[('large','serial'),('large','hold')]
observations=[]
for pair in range(5):
 for fixture,mode in cells[pair%2:]+cells[:pair%2]:
  for arm in ([16,8] if pair%2==0 else [8,16]):
   env['ISSUE88_POOL_MIB']=str(arm);name=f'{fixture}-{mode}-pair{pair}-pool{arm}'
   print(name,flush=True)
   run([str(t/'probe'),'-fixture',fixture,'-mode',mode,'-helper',str(t/'process_cost'),'-out',str(e/(name+'.json'))],180)
   row=json.loads((e/(name+'.json')).read_text());row['pair']=pair;row['name']=name;observations.append(row);(e/'observations.json').write_text(json.dumps(observations,separators=(',',':'))+'\n')
print('ALL 20 PROCESSES COMPLETE',flush=True)
