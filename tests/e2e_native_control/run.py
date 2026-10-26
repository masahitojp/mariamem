"""Native reference browser campaigns; never a mariamem/live-support receipt."""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import uuid
import xml.etree.ElementTree as ET

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]


def assess(kind,code,counts,events,failures):
    named=lambda name:[e for e in events if e['event']==name]
    if code!=1 or counts!={'tests':3,'errors':0,'failures':1,'skipped':0}:return False
    if len(failures)!=1 or failures[0]['name']!='test_02_fail_after_commit' or 'E2E_EXPECTED_FAILURE_AFTER_COMMIT' not in failures[0]['message']:return False
    before,after=named('case_before'),named('case_after')
    names=['test_01_commit_order','test_02_fail_after_commit','test_03_next_case_sees_only_baseline']
    if [e['name'] for e in before]!=names or [e['name'] for e in after]!=names:return False
    baseline=[['SEED',2,'ready']]
    if any(e['rows']!=baseline for e in before):return False
    if [e['rows'] for e in after]!=[baseline+[['ORDER-A',3,'ready']],baseline+[['FAILED-A',4,'ready']],baseline]:return False
    starts,ready,reaped,removed=map(named,['app_started','app_ready','app_reaped','schema_removed'])
    expected=1 if kind=='python' else 3
    if not all(len(e)==expected for e in [starts,ready,reaped,removed]):return False
    if {e['pid'] for e in starts}!={e['pid'] for e in reaped} or not all(e['reaped'] for e in reaped):return False
    if {e['schema'] for e in starts}!={e['schema'] for e in removed}:return False
    if not all(e['db_version'].startswith('12.3.3-MariaDB') for e in ready):return False
    if len(named('browser_started'))!=1 or len(named('browser_closed'))!=1:return False
    if kind=='python':
        if len({e['pid'] for e in before})!=1 or len({e['http_url'] for e in before})!=1 or len(named('native_reset'))!=3:return False
        migrations=named('migration_chain')
        if len(migrations)!=1 or migrations[0]['revisions']!=['0001_initial','0002_status']:return False
    else:
        if len({e['schema'] for e in before})!=3 or len({e['pid'] for e in before})!=3:return False
    return True


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--host',default='127.0.0.1')
    p.add_argument('--port',type=int,required=True)
    p.add_argument('--go-app',type=Path,required=True)
    p.add_argument('--expected-source-commit',required=True)
    p.add_argument('--mutation',choices=['skip-reset','restart-app'])
    args=p.parse_args()
    sys.path.insert(0,str(ROOT/'scripts'))
    from git_identity import require_commit,inspect_ref,verify_go_binary
    require_commit(ROOT,args.expected_source_commit)
    assert inspect_ref(ROOT,'HEAD').source_commit==args.expected_source_commit
    assert not subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True).strip()
    buildinfo=verify_go_binary(ROOT,args.go_app.resolve(),args.expected_source_commit)
    out=args.output.resolve();out.mkdir(parents=True) # refuse stale outputs
    import MySQLdb
    report=dict(result='FAIL',scope='native MariaDB reference; no mariamem or live API executed',
        source_commit=args.expected_source_commit,host_platform=platform.platform(),python=sys.version,
        packages={n:importlib.metadata.version(n) for n in ['Django','mysqlclient','playwright','pytest']},
        native_client_library=MySQLdb._mysql.get_client_info(),go_app_sha256=hashlib.sha256(args.go_app.read_bytes()).hexdigest(),
        go_buildinfo=buildinfo,inputs={str(f.relative_to(ROOT)):hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(HERE.rglob('*')) if f.is_file() and '__pycache__' not in f.parts},runs={})
    try:
        for kind in ['python','go']:
            directory=out/kind;directory.mkdir()
            env=dict(os.environ,E2E_KIND=kind,E2E_OUTPUT=str(directory),E2E_EVENTS=str(directory/'events.jsonl'),
                     E2E_DB_HOST=args.host,E2E_DB_PORT=str(args.port),E2E_RUN_TOKEN=uuid.uuid4().hex[:12],
                     E2E_GO_APP=str(args.go_app.resolve()),E2E_INJECT_FAILURE='1',PYTHONDONTWRITEBYTECODE='1',
                     PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',PYTEST_ADDOPTS='')
            if args.mutation and kind=='python':env['E2E_MUTATE_'+{'skip-reset':'SKIP_RESET','restart-app':'RESTART_APP'}[args.mutation]]='1'
            command=[sys.executable,'-m','pytest',str(HERE/'browser_cases.py'),'-q','--tb=short','--junitxml',str(directory/'pytest.xml')]
            with (directory/'pytest.txt').open('w') as log:
                process=subprocess.run(command,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT,timeout=240)
            events=[json.loads(line) for line in (directory/'events.jsonl').read_text().splitlines()]
            xml=ET.parse(directory/'pytest.xml').getroot()
            counts={k:sum(int(s.get(k,0)) for s in xml.findall('.//testsuite')) for k in ['tests','errors','failures','skipped']}
            failures=[dict(name=c.get('name'),message=f.get('message','')) for c in xml.findall('.//testcase') for f in c.findall('failure')]
            accepted=assess(kind,process.returncode,counts,events,failures)
            if args.mutation and kind=='python':
                report['runs'][kind]=dict(result='DETECTED' if not accepted else 'MISSED',exit_code=process.returncode,counts=counts)
            else:report['runs'][kind]=dict(result='PASS' if accepted else 'FAIL',exit_code=process.returncode,counts=counts)
            print(kind,report['runs'][kind],flush=True)
        expected='DETECTED' if args.mutation else 'PASS'
        if report['runs']['python']['result']==expected and report['runs']['go']['result']=='PASS':report['result']='MUTATION_DETECTED' if args.mutation else 'PASS_NATIVE_CONTROL'
    finally:
        (out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    return 0 if report['result'] in ['PASS_NATIVE_CONTROL','MUTATION_DETECTED'] else 1


if __name__=='__main__':raise SystemExit(main())
