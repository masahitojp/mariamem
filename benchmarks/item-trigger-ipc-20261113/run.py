from pathlib import Path
import os,subprocess,time,json,resource,sys
r=Path(__file__).resolve().parents[1];o=r/'evidence';rows=[];env=os.environ.copy();env.update(GOMAXPROCS='8',GOGC='100');env.pop('MODELCASE_DSN',None);env.pop('IPC_DIAG_DIR',None);env.pop('MARIAMEM_EXPERIMENT_SKIP_EMPTY_WRITE',None)
def guard():subprocess.run([sys.executable,str(r/'worktree/scripts/experiment_disk.py'),'--work-dir',str(r),'--min-free-gib','12','--budget-gib','10'],capture_output=True,check=True)
def run(name,arm='full',parallel=8,kind='isolated',observe=True):
 guard();e=env.copy();e.update(TRIGGER_ARM=arm,ITEM_ATTRIBUTION='1' if observe else '0',ITEM_EVENTS_PATH=str(o/f'{name}-events.json'),MODELCASE_TRACE=str(o/f'{name}-trace.json'),LOAD_PARALLEL=str(parallel),VERIFY_PREFIX='1' if kind=='pilot' else '0',ATTRIB_ORACLE='0' if kind=='anchor' else '1',ATTRIB_ONLY='1' if kind=='isolated' else '0')
 cmd=[str(r/'temp/maria.test'),'-test.v','-test.parallel='+str(parallel),'-test.timeout=120s']
 if kind=='isolated':cmd+=['-test.run=TestAttribution']
 u=resource.getrusage(resource.RUSAGE_CHILDREN);t=time.monotonic_ns();p=subprocess.run(cmd,env=e,capture_output=True,text=True,timeout=130);wall=(time.monotonic_ns()-t)/1e6;v=resource.getrusage(resource.RUSAGE_CHILDREN)
 row={'name':name,'arm':arm,'parallel':parallel,'kind':kind,'observe':observe,'wall_ms':wall,'cpu_ms':((v.ru_utime-u.ru_utime)+(v.ru_stime-u.ru_stime))*1000,'returncode':p.returncode,'leaf_pass':sum('--- PASS: Test' in l and '/' in l for l in p.stdout.splitlines())};rows.append(row);(o/f'{name}.output.txt').write_text(p.stdout+p.stderr);(o/'runs.json').write_text(json.dumps(rows,indent=2));print(json.dumps(row),flush=True);guard()
 if p.returncode or (kind!='isolated' and row['leaf_pass']!=70):raise SystemExit('correctness failure; stop, retain observation')
 if observe:
  d=json.loads((o/f'{name}-events.json').read_text());expected=18 if kind=='isolated' else 22
  if len(d['ledgers'])!=expected or any(not l['joined'] or l['exit_error'] or l['parse_error'] for l in d['ledgers']):raise SystemExit('joined/framing capture failed')
  from analyze import process
  process(row)
for arm in ['full','incremental','none']:run('pilot-'+arm,arm,1,'pilot')
for p in [1,8]:
 for arm in ['full','incremental','none']:run(f'warmup-p{p}-{arm}',arm,p)
for i in range(3):
 for p in ([1,8] if i%2==0 else [8,1]):
  order=[['full','incremental','none'],['none','incremental','full'],['incremental','full','none']][i]
  for arm in order:run(f'primary-p{p}-{arm}-{i}',arm,p)
for i in range(3):
 for observe in ([False,True] if i%2==0 else [True,False]):run(f'anchor-{int(observe)}-{i}',kind='anchor',observe=observe)
