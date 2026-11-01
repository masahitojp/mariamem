"""Finite framework prototype campaign, not product/runtime acceptance."""
import hashlib, json, os, platform, subprocess, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = Path(os.environ['MARIAMEM_EXPERIMENT_TEMP']) / 'campaign'
OUT.mkdir()
results = []
healthy = ['AtomicCases', 'TransactionalCases']
cases = [
 ('healthy', healthy, {}, 0, 4, None),
 ('reverse', healthy, {}, 0, 4, None),
 ('expected-failure', ['TransactionalCases'], {'D1_EXPECT_FAILURE':'1'}, 1, 2, 'D1_EXPECTED_FAILURE_AFTER_COMMIT'),
 ('setup-failure', ['SetupFailure','TransactionalCases'], {}, 1, 2, 'D1_EXPECTED_CLASS_SETUP_FAILURE'),
 ('setup-skip', ['SetupSkip','TransactionalCases'], {}, 0, 2, 'D1_EXPECTED_CLASS_SETUP_SKIP'),
 ('cleanup-debt', healthy, {'D1_FAIL_CLEANUP':'1'}, 1, 1, 'D1_CLEANUP_DEBT'),
 ('prepare-failure', healthy, {'D1_FAIL_PREPARE':'1'}, 1, 0, 'D1_PREPARE_FAILURE'),
 ('capture-failure', healthy, {'D1_FAIL_CAPTURE':'1'}, 1, 0, 'D1_EXPECTED_CAPTURE_FAILURE'),
 ('no-restore-control', ['TransactionalCases'], {'D1_NO_RESTORE':'1'}, 1, 1, 'AssertionError'),
]
for runner in ['manage','pytest']:
 for name, classes, flags, code, bodies, marker in cases:
  directory = OUT / (runner+'-'+name); directory.mkdir()
  env = dict(os.environ, **flags, D1_SCRATCH=str(directory), D1_EVENTS=str(directory/'events.jsonl'),
             DJANGO_SETTINGS_MODULE='d1_settings', PYTEST_DISABLE_PLUGIN_AUTOLOAD='1', PYTHONDONTWRITEBYTECODE='1',
             PYTHONPATH=os.pathsep.join([str(HERE),str(ROOT/'tests/e2e_native_control/pythonapp')]))
  if runner == 'manage':
   command = [sys.executable,'-m','django','test',*['test_cases.'+c for c in classes],'--noinput','-v','1']
   if name == 'reverse': command.append('--reverse')
  else:
   nodes = ['test_cases.py::'+c for c in classes]
   if name == 'reverse': nodes = ['test_cases.py::'+c+'::test_'+n for c in classes for n in ['02','01']]
   command = [sys.executable,'-m','pytest','-p','pytest_django.plugin',*nodes,'-q','-r','a','-p','no:cacheprovider']
  result = subprocess.run(command,cwd=HERE,env=env,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,timeout=30)
  (directory/'output.txt').write_text(result.stdout)
  events = [json.loads(s) for s in (directory/'events.jsonl').read_text().splitlines()]
  actual_bodies = sum(e['event']=='body' for e in events)
  remaining = list(directory.glob('*.sqlite')); failures = []
  if result.returncode != code: failures.append('exit')
  if actual_bodies != bodies: failures.append('body-count')
  if marker and marker not in result.stdout: failures.append('original-error/skip-marker')
  if any(e['event']=='BAD_BODY' for e in events): failures.append('class-failure-admission')
  if remaining: failures.append('remaining-DB')
  if sum(e['event']=='prepare' for e in events)!=1: failures.append('preparation-count')
  if name in ['healthy','reverse'] and sum(e['event']=='setUpTestData' for e in events)!=1: failures.append('class-data-count')
  row=dict(runner=runner,case=name,result='FAIL' if failures else 'PASS',raw_exit=result.returncode,
           expected_exit=code,bodies=actual_bodies,expected_bodies=bodies,failures=failures,
           remaining_databases=[p.name for p in remaining],command=command)
  results.append(row); print(json.dumps(row),flush=True)
summary=dict(scope='Django/SQLite ownership prototype only',python=sys.version,platform=platform.platform(),
 source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
 prototype_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in HERE.glob('*.py')},
 results=results,result='PASS' if all(r['result']=='PASS' for r in results) else 'FAIL')
(OUT/'assessment.json').write_text(json.dumps(summary,indent=2)+'\n')
raise SystemExit(0 if summary['result']=='PASS' else 1)
