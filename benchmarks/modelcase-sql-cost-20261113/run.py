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
 leaf=sum('--- PASS: Test' in l and '/' in l for l in p.stdout.splitlines());row=dict(name=name,arm=arm,observe=observe,diagnostic=diagnostic,profile=profile,wall_ms=ms,returncode=p.returncode,leaf_pass=leaf);records.append(row);(out/'runs.json').write_text(json.dumps(records,indent=2));print(json.dumps(row),flush=True)
 return row
arms=[]
for arm in ['baseline','io4','cache256','querymem','textparams','pool64']:
 row=run('pilot-'+arm,arm,True,True)
 if row['returncode']:
  if arm=='baseline':raise SystemExit('baseline diagnostic failed')
  continue
 arms.append(arm)
for arm in arms:
 if run('warmup-'+arm,arm)['returncode']:raise SystemExit('warmup failed')
for i in range(3):
 for arm in (arms if i%2==0 else list(reversed(arms))):
  x=run(f'primary-{arm}-{i}',arm)
  if x['returncode'] or x['leaf_pass']!=70:raise SystemExit('primary failed')
for i in range(3):
 for mode in ([False,True] if i%2==0 else [True,False]):
  x=run(f'obs-{int(mode)}-{i}',observe=mode)
  if x['returncode'] or x['leaf_pass']!=70:raise SystemExit('observer control failed')
for scenario in ['TestRevenueByCategory','TestGetOrder','TestCreateOrder']:
 if run('profile-'+scenario,profile=scenario)['returncode']:raise SystemExit('profile failed')
(out/'binary.sha256').write_text(hashlib.sha256((r/'temp/maria.test').read_bytes()).hexdigest()+'\n')
