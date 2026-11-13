from pathlib import Path
import json,runpy,signal,sys
W=Path(__file__).resolve().parents[1]
R=W.parents[2]
sys.path.insert(0,str(R/'scripts'))
from experiment_workspace import exclusive,load,save
def timeout(signum,frame):raise TimeoutError('bounded measurement deadline/interruption')
signal.signal(signal.SIGALRM,timeout)
signal.signal(signal.SIGTERM,timeout)
with exclusive(W):
 record=load(W,R)
 assert record['state']=='completed' and json.loads((W/'evidence/build-handoff.json').read_text())['result']=='BUILD_READY'
 record.update(state='running',measurement_phase='manual measurement; full disk scans only outside timed processes')
 save(W,record)
 signal.alarm(900)
 try:
  runpy.run_path(str(W/'evidence/measure.py'),run_name='__main__')
 except BaseException:
  record.update(state='failed',measurement_phase='failed; preserve partial observations')
  raise
 else:record.update(state='completed',measurement_phase='complete')
 finally:
  signal.alarm(0)
  save(W,record)
