"""Guest E2E and test-only live relay compared with the verified native app."""
import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]


def validate_inputs():
    pins=json.loads((HERE/'input-pins.json').read_text())
    for name,h in pins['files'].items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=h:raise ValueError('native input changed: '+name)
    changed=subprocess.check_output(['git','diff','--name-only','bf3a29c292064ddbbd4c7b9a9c6e712504d0f4e4','HEAD','--',
        'python','internal','guest','cmd','release','go.mod','go.sum','mariamem.go','connection.go','snapshot.go','errors.go'],cwd=ROOT,text=True)
    if changed:raise ValueError('unapproved product runtime changes: '+changed)
    return pins


def browser_assessment(kind,code,counts,events,failures,reference):
    named=lambda name:[e for e in events if e['event']==name]
    if code!=1 or counts!=dict(tests=3,errors=0,failures=1,skipped=0):return False
    if len(failures)!=1 or failures[0]['name']!='test_02_fail_after_commit' or 'E2E_EXPECTED_FAILURE_AFTER_COMMIT' not in failures[0]['message']:return False
    for key in ['case_before','case_after']:
        actual=[{'name':e['name'],'rows':e['rows']} for e in named(key)]
        if actual!=reference[key]:return False
    starts,reaped=named('app_started'),named('app_reaped')
    expected=1 if kind=='python' else 3
    if len(starts)!=len(reaped) or len(starts)!=expected or {e['pid'] for e in starts}!={e['pid'] for e in reaped}:return False
    if not all(e['reaped'] for e in reaped):return False
    clean=named('guest_host_cleanup')
    if len(clean)!=1 or not clean[0]['reaped'] or not clean[0]['directory_removed']:return False
    if len(named('baseline_captured'))!=1 or not named('baseline_captured')[0]['source_consumed']:return False
    if len(named('browser_started'))!=1 or len(named('browser_closed'))!=1 or named('browser_started')[0]['version']!='141.0.7390.37':return False
    before=named('case_before')
    if len({e['child_id'] for e in before})!=3:return False
    if kind=='go':
        closes=named('guest_child_closed')
        return (len(closes)==3 and all(e['closed'] for e in closes) and
                {e['child_id'] for e in closes}=={e['child_id'] for e in before}
                and len({e['pid'] for e in before})==3 and all(e['exit_code']==0 for e in reaped))
    resets,closed=named('guest_reset'),named('relay_closed')
    return (len({e['pid'] for e in before})==len({e['http_url'] for e in before})==len({e['db_port'] for e in before})==1
            and len(resets)==3 and [e['generation'] for e in resets]==[1,2,3] and all(e['old_closed'] for e in resets)
            and [e['child_id'] for e in resets]==[e['child_id'] for e in before]
            and [e['port'] for e in resets]==[e['db_port'] for e in before]
            and len(closed)==1 and closed[0]['active']==closed[0]['forced_clients']==0
            and closed[0]['threads_stopped'] and closed[0]['child_closed'])


def parsed(directory):
    events=[json.loads(line) for line in (directory/'events.jsonl').read_text().splitlines()]
    xml=ET.parse(directory/'pytest.xml').getroot()
    counts={k:sum(int(s.get(k,0)) for s in xml.findall('.//testsuite')) for k in ['tests','errors','failures','skipped']}
    failures=[dict(name=c.get('name'),message=f.get('message','')) for c in xml.findall('.//testcase') for f in c.findall('failure')]
    return events,counts,failures


def main():
    p=argparse.ArgumentParser()
    for arg in ['host','go-app','go-owner','output']:p.add_argument('--'+arg,type=Path,required=True)
    p.add_argument('--expected-source-commit',required=True)
    p.add_argument('--mutation',choices=['skip-reset','restart-app'])
    args=p.parse_args();sys.path.insert(0,str(ROOT/'scripts'))
    from git_identity import verify_go_binary,require_commit
    require_commit(ROOT,args.expected_source_commit)
    builds={name:verify_go_binary(ROOT,getattr(args,name).resolve(),args.expected_source_commit) for name in ['host','go_app','go_owner']}
    import MySQLdb
    pins=validate_inputs();ref=json.loads((HERE/'native-reference.json').read_text())['interpreters'][f'{sys.version_info.major}.{sys.version_info.minor}']
    packages={n:importlib.metadata.version(n) for n in ['Django','mysqlclient','playwright','pytest']};assert packages==ref['packages']
    out=args.output.resolve();out.mkdir(parents=True)
    report=dict(result='FAIL',scope='Test-only consumer/relay over existing SDK, no product API change',source_commit=args.expected_source_commit,
        sdk_mode='source SDK with exact source/binary identity',python=sys.version,packages=packages,
        platform=dict(system=platform.system(),machine=platform.machine(),mysqlclient_library=MySQLdb.get_client_info()),native_reference=ref,
        input_pins=pins,binary_buildinfo=builds,binary_hashes={name:hashlib.sha256(getattr(args,name).read_bytes()).hexdigest() for name in builds},runs={})
    env=dict(os.environ,E2E_GUEST_HOST=str(args.host.resolve()),E2E_GO_APP=str(args.go_app.resolve()),E2E_GO_OWNER=str(args.go_owner.resolve()),
             PYTHONPATH=os.pathsep.join([str(ROOT/'python'),str(HERE)]),PYTHONDONTWRITEBYTECODE='1',PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',PYTEST_ADDOPTS='')
    try:
        for kind in ['python','go']:
            directory=out/kind;directory.mkdir()
            scenario=dict(env,E2E_KIND=kind,E2E_OUTPUT=str(directory),E2E_EVENTS=str(directory/'events.jsonl'),E2E_INJECT_FAILURE='1')
            if args.mutation and kind=='python':scenario['E2E_MUTATE_'+{'skip-reset':'SKIP_RESET','restart-app':'RESTART_APP'}[args.mutation]]='1'
            command=[sys.executable,'-m','pytest',str(HERE/'browser_cases.py'),'-q','--tb=short','--junitxml',str(directory/'pytest.xml')]
            with (directory/'pytest.txt').open('w') as log:process=subprocess.run(command,cwd=ROOT,env=scenario,stdout=log,stderr=subprocess.STDOUT,timeout=300)
            events,counts,failures=parsed(directory)
            accepted=browser_assessment(kind,process.returncode,counts,events,failures,ref['observation'][kind])
            if args.mutation and kind=='python':
                # Keep native data/process defect signatures, with explicit guest ownership checks.
                before=[e for e in events if e['event']=='case_before'];after=[e for e in events if e['event']=='case_after']
                cleanup=[e for e in events if e['event']=='guest_host_cleanup'];closed=[e for e in events if e['event']=='relay_closed']
                ownership=(len(cleanup)==len(closed)==1 and cleanup[0]['reaped'] and cleanup[0]['directory_removed'] and closed[0]['threads_stopped'] and closed[0]['active']==closed[0]['forced_clients']==0)
                if args.mutation=='skip-reset':
                    checks=[e for e in events if e['event']=='baseline_checked']
                    detected=(process.returncode==1 and counts==dict(tests=3,errors=2,failures=0,skipped=0) and len(checks)==3 and checks[1]['rows']==checks[2]['rows']==ref['observation']['python']['case_after'][0]['rows'])
                else:
                    starts=[e for e in events if e['event']=='app_started'];reaped=[e for e in events if e['event']=='app_reaped']
                    detected=(process.returncode==1 and counts==dict(tests=3,errors=0,failures=1,skipped=0) and len(starts)==len(reaped)==4 and all(e['reaped'] for e in reaped) and len(before)==3 and len({e['pid'] for e in before})==3 and [{'name':e['name'],'rows':e['rows']} for e in after]==ref['observation']['python']['case_after'] and len(failures)==1 and 'E2E_EXPECTED_FAILURE_AFTER_COMMIT' in failures[0]['message'])
                result='DETECTED' if ownership and detected and not accepted else 'MISSED_OR_UNRELATED_FAILURE'
            else:result='PASS' if accepted else 'FAIL'
            report['runs'][kind]=dict(result=result,exit_code=process.returncode,counts=counts)
            print(kind,report['runs'][kind],flush=True)
        directory=out/'live-controls';directory.mkdir()
        scenario=dict(env,E2E_KIND='python',E2E_OUTPUT=str(directory),E2E_EVENTS=str(directory/'events.jsonl'))
        with (directory/'pytest.txt').open('w') as log:
            process=subprocess.run([sys.executable,'-m','pytest',str(HERE/'live_checks.py'),'-q','--tb=short','--junitxml',str(directory/'pytest.xml')],cwd=ROOT,env=scenario,stdout=log,stderr=subprocess.STDOUT,timeout=300)
        events,counts,_=parsed(directory);clean=[e for e in events if e['event']=='guest_host_cleanup'];relays=[e for e in events if e['event']=='relay_closed']
        passed=(process.returncode==0 and counts==dict(tests=2,errors=0,failures=0,skipped=0) and len(clean)==len(relays)==2 and all(e['reaped'] and e['directory_removed'] for e in clean) and all(e['threads_stopped'] and e['forced_clients']==e['active']==0 for e in relays) and len([e for e in events if e['event']=='busy_control_pass'])==1 and len([e for e in events if e['event']=='failed_replace_control_pass'])==1)
        report['runs']['live-controls']=dict(result='PASS' if passed else 'FAIL',exit_code=process.returncode,counts=counts)
        expected='DETECTED' if args.mutation else 'PASS'
        if report['runs']['python']['result']==expected and all(report['runs'][k]['result']=='PASS' for k in ['go','live-controls']):report['result']='MUTATION_DETECTED' if args.mutation else 'PASS_GUEST_COMPARISON'
        print('live-controls',report['runs']['live-controls'],flush=True)
    finally:(out/'result.json').write_text(json.dumps(report,indent=2)+'\n')
    return 0 if report['result'] in ['PASS_GUEST_COMPARISON','MUTATION_DETECTED'] else 1


if __name__=='__main__':raise SystemExit(main())
