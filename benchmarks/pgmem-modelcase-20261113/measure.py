import os,json,time,subprocess
from pathlib import Path
r=Path(__file__).resolve().parents[1];out=r/'evidence'; rows=[]
e=os.environ.copy();e.update(GOMAXPROCS='8',GOGC='100')
for repeat in range(-1,5):
 for target in (['pgmem','maria'] if repeat%2 else ['maria','pgmem']):
  trace=out/f'{target}-{repeat}.json';e['MODELCASE_TRACE']=str(trace)
  t=time.monotonic_ns();p=subprocess.run([str(r/'temp'/f'{target}.test'),'-test.v','-test.parallel=8','-test.timeout=120s'],env=e,capture_output=True,text=True,timeout=130);wall=(time.monotonic_ns()-t)/1e6
  (out/f'{target}-{repeat}.log').write_text(p.stdout+p.stderr)
  row=dict(target=target,repeat=repeat,wall_ms=wall,returncode=p.returncode,leaf_pass=sum(1 for l in p.stdout.splitlines() if '--- PASS: Test' in l and '/' in l))
  rows.append(row);(out/'runs.json').write_text(json.dumps(rows,indent=2));print(json.dumps(row),flush=True)
  if p.returncode or row['leaf_pass']!=70:raise SystemExit('pilot/measurement failed; retained, no extra repeats')
