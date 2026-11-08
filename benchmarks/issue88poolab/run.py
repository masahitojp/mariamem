import os,pathlib,subprocess,json,hashlib,platform,time,sys
w=pathlib.Path(sys.argv[1]).resolve();s=w/'worktree';t=w/'temp';e=w/'evidence';env=os.environ.copy();env.update(CGO_ENABLED='0',GOMAXPROCS='8',GOGC='100',GOCACHE=str(t/'gocache'),GOMODCACHE=str(t/'gomodcache'),ISSUE88_POOL_MIB='16')
for k in list(env):
 if k.startswith(('MARIAMEM_','LC_STAGE_','LEXER_')) and k not in ('MARIAMEM_EXPERIMENT_TEMP','MARIAMEM_EXPERIMENT_EVIDENCE'):env.pop(k)
def run(args,timeout=600):
 r=subprocess.run(args,cwd=s,env=env,capture_output=True,text=True,timeout=timeout)
 if r.returncode:
  (e/'failure.txt').write_text(r.stdout+r.stderr);r.check_returncode()
 return r
identity=json.loads(run(['python3','scripts/git_identity.py','inspect','HEAD']).stdout);assert identity['object_type']=='commit';assert not run(['git','status','--porcelain']).stdout
assert not run(['git','diff','a3b2b645','--','internal','guest','release','go.mod','go.sum']).stdout
inputs={'source':identity,'product_source_commit':'a3b2b6457147e2b8edbd31fec77ab6ec04f11b22','plan':json.loads((s/'benchmarks/issue88poolab/plan.json').read_text()),'host':{'platform':platform.platform(),'go':run(['go','version']).stdout.strip(),'cpu':run(['sysctl','-n','machdep.cpu.brand_string']).stdout.strip(),'memory':run(['sysctl','-n','hw.memsize']).stdout.strip()}}
(e/'inputs.json').write_text(json.dumps(inputs,indent=2)+'\n')
run(['python3','benchmarks/issue88poolab/overlay.py',str(s),str(t/'overlay')]);overlay=str(t/'overlay/overlay.json')
print('selector tests / build',flush=True);at=time.monotonic();r=run(['go','test','-overlay',overlay,'-count=1','-run','^TestPoolSelector$','./internal/generatedgo/code/base']);(e/'selector-tests.txt').write_text(r.stdout+r.stderr)
r=run(['go','build','-trimpath','-overlay',overlay,'-o',str(t/'probe'),'./benchmarks/issue88poolab']);(e/'build.txt').write_text(r.stdout+r.stderr)
run(['cc','-O2','benchmarks/tools/process_cost.c','-o',str(t/'process_cost')])
inputs.update(binary_sha256=hashlib.sha256((t/'probe').read_bytes()).hexdigest(),build_seconds=time.monotonic()-at,build_info=run(['go','version','-m',str(t/'probe')]).stdout.replace(str(w),'<WORKSPACE>'),overlay=json.loads((t/'overlay/hashes.json').read_text()))
(e/'inputs.json').write_text(json.dumps(inputs,indent=2)+'\n')
cells=[('small','serial'),('small','hold'),('large','serial'),('large','hold')]
for pair in range(5):
 for fixture,mode in cells[pair%4:]+cells[:pair%4]:
  for arm in ([16,8] if pair%2==0 else [8,16]):
   env['ISSUE88_POOL_MIB']=str(arm);name=f'{fixture}-{mode}-pair{pair}-pool{arm}'
   print(name,flush=True)
   run([str(t/'probe'),'-fixture',fixture,'-mode',mode,'-helper',str(t/'process_cost'),'-out',str(e/(name+'.json'))],180)
print('ALL 40 PROCESSES COMPLETE',flush=True)
