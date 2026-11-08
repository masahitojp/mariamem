import os,pathlib,subprocess,json,hashlib,platform,time,sys
w=pathlib.Path(sys.argv[1]).resolve();s=w/'worktree';t=w/'temp';e=w/'evidence';b=s/'benchmarks/issue88modelcase'
env={k:v for k,v in os.environ.items() if not k.startswith(('MARIAMEM_','MYSQLMEM_','LC_STAGE_','LEXER_'))};env.update(CGO_ENABLED='0',GOMAXPROCS='8',GOGC='100',GOTOOLCHAIN='local',GOWORK='off',GOENV='off',GOFLAGS='',GOCACHE=str(t/'gocache'),GOMODCACHE=str(t/'gomodcache'),ISSUE88_POOL_MIB='16')
def run(args,cwd=s,timeout=600):
 r=subprocess.run(args,cwd=cwd,env=env,capture_output=True,text=True,timeout=timeout)
 if r.returncode:
  (e/'failure.txt').write_text('COMMAND '+repr(args)+'\n'+r.stdout+r.stderr);r.check_returncode()
 return r
identity=json.loads(run(['python3','scripts/git_identity.py','inspect','HEAD']).stdout);assert not run(['git','status','--porcelain']).stdout
assert not run(['git','diff','a3b2b645','--','internal','guest','release','go.mod','go.sum']).stdout
pg=json.loads(run(['python3','scripts/git_identity.py','--root',str(t/'pgmem'),'inspect','v1.18.2']).stdout);assert pg['source_commit']=='a61005d37d01e6671f814fe8ca828222e8147df4' and pg['object_sha']=='145e5d2fc70983b89a4bdd8438e547fcd60244ed';assert not run(['git','status','--porcelain'],cwd=t/'pgmem').stdout
inputs={'source':identity,'pgmem_identity':pg,'plan':json.loads((b/'plan.json').read_text()),'host':{'platform':platform.platform(),'go':run(['go','version']).stdout.strip(),'cpu':run(['sysctl','-n','machdep.cpu.brand_string']).stdout.strip(),'memory':run(['sysctl','-n','hw.memsize']).stdout.strip()},'binaries':{}}
(e/'inputs.json').write_text(json.dumps(inputs,indent=2)+'\n')
run(['python3','benchmarks/issue88poolab/overlay.py',str(s),str(t/'overlay')]);overlay=str(t/'overlay/overlay.json');inputs['overlay']=json.loads((t/'overlay/hashes.json').read_text())
for engine in ('maria','postgres'):
 print('BUILD '+engine,flush=True);start=time.monotonic();cmd=['go','test','-c','-trimpath','-mod=readonly','-o',str(t/engine),'./'+engine+'/store']
 if engine=='maria':cmd[3:3]=['-overlay',overlay]
 r=run(cmd,cwd=b,timeout=700);(e/('build-'+engine+'.txt')).write_text(r.stdout+r.stderr)
 info=run(['go','version','-m',str(t/engine)]).stdout.replace(str(w),'<WORKSPACE>')
 inputs['binaries'][engine]={'sha256':hashlib.sha256((t/engine).read_bytes()).hexdigest(),'build_info':info,'build_seconds':time.monotonic()-start};(e/'inputs.json').write_text(json.dumps(inputs,indent=2)+'\n')
arms=['mariamem16','mariamem8','pgmem']
for repeat in range(-1,5):
 order=arms if repeat<0 else arms[repeat%3:]+arms[:repeat%3]
 for arm in order:
  engine='postgres' if arm=='pgmem' else 'maria';env['ISSUE88_POOL_MIB']='8' if arm=='mariamem8' else '16';name=f'{arm}-r{repeat}';env['MODELCASE_TRACE']=str(e/(name+'.json'))
  print(('WARMUP ' if repeat<0 else 'MEASURE ')+name,flush=True)
  r=run([str(t/engine),'-test.parallel=8','-test.timeout=120s','-test.count=1'],cwd=b,timeout=130)
  (e/(name+'.txt')).write_text(r.stdout+r.stderr)
  trace=json.loads((e/(name+'.json')).read_text());assert trace['meta']['read_cases']=='50' and trace['meta']['write_cases']=='20' and trace['meta']['test_exit']=='0'
  assert sum(x['kind']=='write' for x in trace['spans'])==20 and sum(x['kind']=='read' for x in trace['spans'])==50
  if engine=='maria':assert trace['meta']['active_mappings_after']=='0'
print('ALL 15 PRIMARY +3 WARMUP PROCESSES PASS',flush=True)

observations=[]
for repeat in range(-1,5):
 for arm in ('mariamem16','mariamem8','pgmem'):
  observations.append({'arm':arm,'repeat':repeat,'trace':json.loads((e/f'{arm}-r{repeat}.json').read_text())})
(e/'observations.json').write_text(json.dumps(observations,separators=(',',':'))+'\n')
