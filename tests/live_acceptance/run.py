"""Exact-candidate public Live browser comparison, real mutations and SQL controls."""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import xml.etree.ElementTree as ET

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]


def parsed(directory):
    events=[json.loads(line) for line in (directory/'events.jsonl').read_text().splitlines()]
    xml=ET.parse(directory/'pytest.xml').getroot()
    counts={k:sum(int(s.get(k,0)) for s in xml.findall('.//testsuite')) for k in ['tests','errors','failures','skipped']}
    failures=[dict(name=c.get('name'),message=f.get('message','')) for c in xml.findall('.//testcase') for f in c.findall('failure')]
    return events,counts,failures


def assess(kind,code,counts,events,failures,reference,mutation=None):
    get=lambda name:[e for e in events if e['event']==name]
    cleanup=get('guest_host_cleanup');starts=get('app_started');reaped=get('app_reaped')
    if len(cleanup)!=1 or not cleanup[0]['reaped'] or not cleanup[0]['directory_removed']:return False
    if len(starts)!=len(reaped) or {e['pid'] for e in starts}!={e['pid'] for e in reaped} or not all(e['reaped'] for e in reaped):return False
    if len(get('baseline_captured'))!=1 or not get('baseline_captured')[0]['source_consumed']:return False
    if len(get('browser_started'))!=1 or get('browser_started')[0]['version']!='141.0.7390.37' or len(get('browser_closed'))!=1:return False
    if kind!='go-fork':
        closed=get('live_closed')
        if len(get('live_created'))!=1 or len(closed)!=1 or not closed[0]['close_returned'] or closed[0]['active_before_close']!=0:return False
        if closed[0]['status']['state']!='closed' or closed[0]['status']['active_connections']!=0:return False
    before,after=get('case_before'),get('case_after')
    normalized=lambda seq:[{'name':e['name'],'rows':e['rows']} for e in seq]
    intentional=(code==1 and counts==dict(tests=3,errors=0,failures=1,skipped=0) and len(failures)==1 and failures[0]['name']=='test_02_fail_after_commit' and 'E2E_EXPECTED_FAILURE_AFTER_COMMIT' in failures[0]['message'])
    if mutation=='skip-reset':
        checks=get('baseline_checked')
        return (code==1 and counts==dict(tests=3,errors=2,failures=0,skipped=0) and len(starts)==1 and len(checks)==3
                and checks[1]['rows']==checks[2]['rows']==reference['case_after'][0]['rows'] and not get('reset_committed'))
    if not intentional or normalized(before)!=reference['case_before'] or normalized(after)!=reference['case_after']:return False
    if kind=='go-fork':
        closed=get('guest_child_closed')
        return len(starts)==len(closed)==3 and all(e['closed'] for e in closed) and len({e['pid'] for e in before})==3 and {e['child_id'] for e in closed}=={e['generation'] for e in before} and all(e['exit_code']==0 for e in reaped)
    resets=get('reset_committed')
    if len(resets)!=3 or [e['generation'] for e in resets]!=[1,2,3] or [e['generation'] for e in before]!=[1,2,3]:return False
    if len({e['db_port'] for e in before})!=1 or [e['port'] for e in resets]!=[e['db_port'] for e in before]:return False
    if not all(e['status']['state']=='ready' for e in resets):return False
    if mutation=='restart-app':return len(starts)==4 and len({e['pid'] for e in before})==len({e['http_url'] for e in before})==3
    return len(starts)==1 and len({e['pid'] for e in before})==len({e['http_url'] for e in before})==1


def main():
    parser=argparse.ArgumentParser()
    for name in ['host','go-app','go-live-app','go-owner','output','native-reference']:parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--expected-source-commit',required=True)
    parser.add_argument('--mutation',choices=['skip-reset','restart-app'])
    args=parser.parse_args();sys.path.insert(0,str(ROOT/'scripts'))
    from git_identity import verify_go_binary
    binaries={key:verify_go_binary(ROOT,getattr(args,key).resolve(),args.expected_source_commit) for key in ['host','go_app','go_live_app','go_owner']}
    pins=json.loads((HERE/'native-input-pins.json').read_text())
    for name,h in pins['files'].items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==h,name
    derived=json.loads((HERE/'input-manifest.json').read_text())
    for name,h in derived['files'].items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==h,name
    reference=json.loads((HERE/'native-reference.json').read_text())['interpreters'][f'{sys.version_info.major}.{sys.version_info.minor}']
    native=json.loads((args.native_reference/'result.json').read_text())
    assert native['source_commit']==args.expected_source_commit and native['result']=='PASS_NATIVE_CONTROL'
    assert native['go_app_sha256']==hashlib.sha256(args.go_live_app.read_bytes()).hexdigest()
    native_events,_,_=parsed(args.native_reference/'go')
    for key in ['case_before','case_after']:
        assert [{'name':e['name'],'rows':e['rows']} for e in native_events if e['event']==key]==reference['observation']['go'][key]
    packages={n:importlib.metadata.version(n) for n in ['Django','mysqlclient','playwright','pytest']};assert packages==reference['packages']
    out=args.output.resolve();out.mkdir(parents=True)
    import MySQLdb
    report=dict(result='FAIL',source_commit=args.expected_source_commit,python=sys.version,packages=packages,
        platform=dict(system=platform.system(),machine=platform.machine(),mysqlclient_library=MySQLdb.get_client_info()),
        scope='Public Go/Python host-owned Live; original Go Fork control; source SDK',native_reference=native,
        prior_native_reference=reference,binary_buildinfo=binaries,binary_hashes={k:hashlib.sha256(getattr(args,k).read_bytes()).hexdigest() for k in binaries},runs={})
    env=dict(os.environ,E2E_GUEST_HOST=str(args.host.resolve()),E2E_GO_OWNER=str(args.go_owner.resolve()),
             PYTHONPATH=os.pathsep.join([str(ROOT/'python'),str(HERE)]),PYTHONDONTWRITEBYTECODE='1',PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',PYTEST_ADDOPTS='')
    try:
        for kind in ['python','go-live','go-fork']:
            directory=out/kind;directory.mkdir()
            scenario=dict(env,E2E_KIND=kind,E2E_OUTPUT=str(directory),E2E_EVENTS=str(directory/'events.jsonl'),E2E_INJECT_FAILURE='1',
                          E2E_GO_APP=str((args.go_app if kind=='go-fork' else args.go_live_app).resolve()))
            mutation=args.mutation if kind!='go-fork' else None
            if mutation:scenario['E2E_MUTATE_'+{'skip-reset':'SKIP_RESET','restart-app':'RESTART_APP'}[mutation]]='1'
            with (directory/'pytest.txt').open('w') as log:
                process=subprocess.run([sys.executable,'-m','pytest',str(HERE/'browser_cases.py'),'-q','--tb=short','--junitxml',str(directory/'pytest.xml')],cwd=ROOT,env=scenario,stdout=log,stderr=subprocess.STDOUT,timeout=300)
            events,counts,failures=parsed(directory)
            accepted=assess(kind,process.returncode,counts,events,failures,reference['observation']['python' if kind=='python' else 'go'],mutation)
            report['runs'][kind]=dict(result=('DETECTED' if mutation else 'PASS') if accepted else 'FAIL',exit_code=process.returncode,counts=counts)
            print(kind,report['runs'][kind],flush=True)
        directory=out/'live-controls';directory.mkdir()
        scenario=dict(env,E2E_KIND='python',E2E_OUTPUT=str(directory),E2E_EVENTS=str(directory/'events.jsonl'))
        with (directory/'pytest.txt').open('w') as log:
            process=subprocess.run([sys.executable,'-m','pytest',str(HERE/'live_checks.py'),'-q','--tb=short','--junitxml',str(directory/'pytest.xml')],cwd=ROOT,env=scenario,stdout=log,stderr=subprocess.STDOUT,timeout=300)
        events,counts,_=parsed(directory);get=lambda name:[e for e in events if e['event']==name]
        clean=get('guest_host_cleanup')
        passed=(process.returncode==0 and counts==dict(tests=4,errors=0,failures=0,skipped=0) and len(clean)==4 and all(e['reaped'] and e['directory_removed'] for e in clean)
                and len(get('busy_control_pass'))==2 and len(get('parent_lifetime_control_pass'))==len(get('failed_replace_control_pass'))==1)
        report['runs']['live-controls']=dict(result='PASS' if passed else 'FAIL',exit_code=process.returncode,counts=counts)
        expected='DETECTED' if args.mutation else 'PASS'
        if all(report['runs'][k]['result']==expected for k in ['python','go-live']) and all(report['runs'][k]['result']=='PASS' for k in ['go-fork','live-controls']):report['result']='MUTATION_DETECTED' if args.mutation else 'PASS_PUBLIC_LIVE'
        print('live-controls',report['runs']['live-controls'],flush=True)
    finally:(out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    return 0 if report['result'] in ['PASS_PUBLIC_LIVE','MUTATION_DETECTED'] else 1


if __name__=='__main__':raise SystemExit(main())
