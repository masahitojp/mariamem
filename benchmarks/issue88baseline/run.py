import os, pathlib, subprocess, json, hashlib, platform, time
w=pathlib.Path(os.environ['MARIAMEM_EXPERIMENT_TEMP']).parent; source=w/'worktree'; temp=w/'temp'; evidence=w/'evidence'
env=os.environ.copy(); env.update(CGO_ENABLED='0', GOMAXPROCS='8', GOGC='100', GOCACHE=str(temp/'gocache'), GOMODCACHE=str(temp/'gomodcache'))
for k in list(env):
    if k.startswith(('MARIAMEM_', 'LC_STAGE_', 'LEXER_')) and k not in ('MARIAMEM_EXPERIMENT_TEMP','MARIAMEM_EXPERIMENT_EVIDENCE'): env.pop(k)
def run(args,timeout=300):
    return subprocess.run(args,cwd=source,env=env,check=True,capture_output=True,text=True,timeout=timeout)
identity=json.loads(run(['python3','scripts/git_identity.py','inspect','HEAD']).stdout)
assert identity['object_type']=='commit'
assert not run(['git','status','--porcelain']).stdout
assert run(['git','diff','a3b2b6457147e2b8edbd31fec77ab6ec04f11b22','--','internal','guest','go.mod','go.sum']).stdout==''
inputs={'source':identity,'product_source_commit':'a3b2b6457147e2b8edbd31fec77ab6ec04f11b22','plan':json.loads((source/'benchmarks/issue88baseline/plan.json').read_text()),'host':{'platform':platform.platform(),'machine':platform.machine(),'go':run(['go','version']).stdout.strip(),'cpu':run(['sysctl','-n','machdep.cpu.brand_string']).stdout.strip(),'memory':run(['sysctl','-n','hw.memsize']).stdout.strip()},'runtime_diff_from_main':''}
(evidence/'inputs.json').write_text(json.dumps(inputs,indent=2)+'\n')
t=time.monotonic(); print('building baseline',flush=True)
try:
    r=run(['go','build','-trimpath','-o',str(temp/'baseline'),'./benchmarks/issue88baseline'],600)
except subprocess.CalledProcessError as e:
    (evidence/'build-failure.txt').write_text(e.stdout+e.stderr); raise
(evidence/'build.txt').write_text(r.stdout+r.stderr)
run(['cc','-O2','benchmarks/tools/process_cost.c','-o',str(temp/'process_cost')])
inputs['binary_sha256']=hashlib.sha256((temp/'baseline').read_bytes()).hexdigest(); inputs['build_seconds']=time.monotonic()-t; inputs['build_info']=run(['go','version','-m',str(temp/'baseline')]).stdout.replace(str(w),'<WORKSPACE>')
(evidence/'inputs.json').write_text(json.dumps(inputs,indent=2)+'\n')
for repeat in range(5):
    for mode in ('serial','hold'):
        print(f'measurement {repeat+1}/5 {mode}',flush=True)
        r=run([str(temp/'baseline'),'-mode',mode,'-helper',str(temp/'process_cost'),'-out',str(evidence/f'{mode}-{repeat}.json')],120)
        (evidence/f'{mode}-{repeat}.stderr.txt').write_text(r.stderr)
print('measurement complete',flush=True)
