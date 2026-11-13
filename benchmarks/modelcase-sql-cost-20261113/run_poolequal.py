from pathlib import Path
import os,subprocess,time,json,hashlib
r=Path(__file__).resolve().parents[1];out=r/'evidence';records=[]
env=os.environ.copy();env.update(GOMAXPROCS='8',GOGC='100')
def run(name,arm='baseline',observe=False,diagnostic=False,profile=None):
 e=env.copy();e['MARIAMEM_EXPERIMENT_POOL64']='1' if arm=='pool64' else '0';e.update(RESOURCE_ARM=arm if arm not in ['baseline','textparams'] else '',TEXT_PARAMS='1' if arm=='textparams' else '0',OBSERVE='1' if observe else '0',OBS_PATH=str(out/f'{name}-ops.json'),MODELCASE_TRACE=str(out/f'{name}-trace.json'))
 cmd=[str(r/'temp/maria.test'),'-test.v','-test.parallel=8','-test.timeout=120s']
 if diagnostic:e.update(DIAGNOSTICS='1',DIAG_PATH=str(out/f'{name}-diag.json'));cmd+=['-test.run=TestDiagnostics']
 if profile:cmd += [f'-test.run={profile}','-test.count=20',f'-test.cpuprofile={out/name}.pprof']
 t=time.monotonic_ns();p=subprocess.run(cmd,env=e,capture_output=True,text=True,timeout=130);ms=(time.monotonic_ns()-t)/1e6
 (out/f'{name}.log').write_text(p.stdout+p.stderr)
 leaf=sum('--- PASS: Test' in l and '/' in l for l in p.stdout.splitlines());row=dict(name=name,arm=arm,observe=observe,diagnostic=diagnostic,profile=profile,wall_ms=ms,returncode=p.returncode,leaf_pass=leaf);records.append(row);(out/'poolequal-runs.json').write_text(json.dumps(records,indent=2));print(json.dumps(row),flush=True)
 return row
# Bounded recovery of failed pool64 observer pilot; original records preserved.
for arm in ['baseline','pool64']:
 x=run('poolequal-pilot-'+arm,arm,True,True)
 if x['returncode']:raise SystemExit('recovery pilot failed')
 if run('poolequal-warmup-'+arm,arm)['returncode']:raise SystemExit('recovery warmup failed')
for i in range(3):
 for arm in (['baseline','pool64'] if i%2==0 else ['pool64','baseline']):
  x=run(f'poolequal-primary-{arm}-{i}',arm)
  if x['returncode'] or x['leaf_pass']!=70:raise SystemExit('recovery primary failed')
