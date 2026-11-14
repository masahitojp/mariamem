from pathlib import Path
import subprocess,sys,os,shutil,time,signal,json
E=Path(__file__).resolve().parent;X=E.parent;sys.path.insert(0,str(X.parents[2]/'scripts'));from experiment_disk import DiskGuard
assert json.loads((E/'canonical-check.json').read_text())['returncode']==0;assert json.loads((E/'validation-complete.json').read_text())['result']=='PASS';assert (E/'local-integration-disposition.json').exists()
assert json.loads((E/'ci-wrapper-check.json').read_text())['returncode']==0
guard=DiskGuard(X,min_free_gib=8,budget_gib=20)
before=guard.check();at=time.monotonic();low=shutil.disk_usage(X).free
cmd=[sys.executable,str(E/'light-monitor/measure.py')]
p=subprocess.Popen(cmd,start_new_session=True)
try:
 while p.poll() is None:
  low=min(low,shutil.disk_usage(X).free)
  if low<8*1024**3 or time.monotonic()-at>900:raise RuntimeError('disk-free reserve or timeout')
  time.sleep(.5)
 if p.returncode:raise SystemExit(p.returncode)
finally:
 if p.poll() is None:
  os.killpg(p.pid,signal.SIGTERM)
  try:p.wait(timeout=3)
  except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL);p.wait()
after=guard.check();(E/'light-monitor-budget.json').write_text(json.dumps({'before':before,'after':after,'minimum_free_bytes':low,'interval_seconds':.5,'recursive_scans_during_matrix':0,'scope':'Immutable existing binaries only; full budget scans are outside measured matrix'},indent=2)+'\n')
print('PASS fixed light-monitor matrix; budget/free checks passed')
