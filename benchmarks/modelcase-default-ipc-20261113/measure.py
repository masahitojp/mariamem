from pathlib import Path
import os,subprocess,json,time,hashlib
r=Path(__file__).resolve().parents[1];o=r/'evidence';rows=[];env=os.environ.copy();env.update(GOMAXPROCS='8',GOGC='100')
for repeat in range(-1,5):
 for name in (['pgmem','maria'] if repeat%2 else ['maria','pgmem']):
  e=env.copy();e['MODELCASE_TRACE']=str(o/f'comparison-{name}-{repeat}.json');t=time.monotonic_ns()
  p=subprocess.run([str(r/'temp'/f'{name}.test'),'-test.v','-test.parallel=8','-test.timeout=120s'],env=e,capture_output=True,text=True,timeout=130)
  x={'target':name,'repeat':repeat,'wall_ms':(time.monotonic_ns()-t)/1e6,'returncode':p.returncode,'leaf_pass':sum('--- PASS: Test' in l and '/' in l for l in p.stdout.splitlines())};rows.append(x);(o/f'comparison-{name}-{repeat}.log').write_text(p.stdout+p.stderr);(o/'comparison-runs.json').write_text(json.dumps(rows,indent=2));print(json.dumps(x),flush=True)
  if x['returncode'] or x['leaf_pass']!=70:raise SystemExit('correctness failure; stop')
(o/'comparison-binary-hashes.json').write_text(json.dumps({n:hashlib.sha256((r/'temp'/f'{n}.test').read_bytes()).hexdigest() for n in ['maria','pgmem']},indent=2))
