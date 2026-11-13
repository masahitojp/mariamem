from pathlib import Path
import os,subprocess,json,re
r=Path(__file__).resolve().parents[1];rows=[];env=os.environ.copy();env.update(GOMAXPROCS='8',GOGC='100',MARIA_AUDIT_OF='1',MODELCASE_MATCHED='1',TRIGGERS_OFF='1',LOAD_PARALLEL='1')
for arm in ['pg','standard','stdlib','native']:
 e=env.copy();e.update(PROBE_ENGINE='pg' if arm=='pg' else 'maria',MYSQL_CLIENT_PATH=arm,MODELCASE_TRACE=str(r/f'evidence/pilot-{arm}-trace.json'));p=subprocess.run([str(r/'temp'/('pg.test' if arm=='pg' else 'maria.test')),'-test.v','-test.run','^TestInsertOnly$','-test.timeout=120s'],env=e,capture_output=True,text=True,timeout=130);(r/f'evidence/pilot-{arm}.txt').write_text(p.stdout+p.stderr);row={'arm':arm,'returncode':p.returncode,'leaf_pass':sum('--- PASS: TestInsertOnly/' in z for z in p.stdout.splitlines()),'sessions':sorted(set(re.findall(r'measurement session (.*)',p.stdout)))};rows.append(row);(r/'evidence/pilots.json').write_text(json.dumps(rows,indent=2));print(json.dumps(row),flush=True)
 if p.returncode or row['leaf_pass']!=8:raise SystemExit('pilot failed; stop')
sessions=[x['sessions'] for x in rows if x['arm']!='pg'];assert sessions[0]==sessions[1]==sessions[2],sessions
print('PASS all pilots and Maria session settings equal')
