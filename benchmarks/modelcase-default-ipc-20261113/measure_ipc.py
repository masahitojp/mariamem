from pathlib import Path
import subprocess,os,time,json,hashlib
r=Path(__file__).resolve().parents[1];o=r/'evidence';rows=[];env=os.environ.copy();env.update(GOMAXPROCS='8',GOGC='100')
def run(name,on,scenario=None):
 e=env.copy();e['MODELCASE_TRACE']=str(o/f'{name}-trace.json')
 if on:
  d=o/(name+'-ipc');d.mkdir();e['IPC_DIAG_DIR']=str(d)
 cmd=[str(r/'temp/maria-ipc.test'),'-test.v','-test.parallel=8','-test.timeout=120s']
 if scenario:cmd += [f'-test.run={scenario}','-test.count=20',f'-test.cpuprofile={o/name}.pprof']
 t=time.monotonic_ns();p=subprocess.run(cmd,env=e,capture_output=True,text=True,timeout=130)
 x=dict(name=name,on=on,scenario=scenario,wall_ms=(time.monotonic_ns()-t)/1e6,returncode=p.returncode,leaf_pass=sum('--- PASS: Test' in l and '/' in l for l in p.stdout.splitlines()));(o/f'{name}.log').write_text(p.stdout+p.stderr);rows.append(x);(o/'ipc-runs.json').write_text(json.dumps(rows,indent=2));print(json.dumps(x),flush=True)
 if p.returncode:raise SystemExit('IPC correctness failure; stop')
 if scenario is None and x['leaf_pass']!=70:raise SystemExit('test count mismatch')
 if on:
  ledgers=[json.loads(p.read_text()) for p in d.glob('db-*.json')]
  if len(ledgers)!=22 or any(l['exit_error'] for l in ledgers):raise SystemExit('guest joined completion mismatch')
  (o/f'{name}-completion.json').write_text(json.dumps({'guest_instances_joined':len(ledgers),'all_exit_success':True},indent=2))
for on in [False,True]:run('ipc-warmup-'+str(int(on)),on)
for i in range(3):
 for on in ([False,True] if i%2==0 else [True,False]):run(f'ipc-{int(on)}-{i}',on)
for scenario in ['TestRevenueByCategory','TestGetOrder','TestCreateOrder']:run('ipc-profile-'+scenario,False,scenario)
(o/'ipc-binary.sha256').write_text(hashlib.sha256((r/'temp/maria-ipc.test').read_bytes()).hexdigest()+'\n')
