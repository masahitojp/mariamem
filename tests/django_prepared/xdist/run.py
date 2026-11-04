"""Installed/source entry oracle for local process-owned Django workers."""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import run as serial

CASES = [('healthy',2,'load'), ('healthy',4,'load'), ('reverse',2,'load'),
         ('healthy',2,'loadscope'), ('body-failure',2,'load'),
         ('prepare-failure',2,'load'), ('no-restore',2,'load'),
         ('idle',4,'loadscope'), ('no-db',2,'load'), ('collect-only',2,'load'),
         ('crash',2,'load'), ('restart',2,'load'), ('cleanup-failure',2,'load'),
         ('refuse-auto',2,'load'), ('refuse-remote',2,'load')]


def run_case(host, out, mode, workers, dist, installed):
    out.mkdir(parents=True)
    scratch=out/'tmp';scratch.mkdir()
    paths=[HERE,HERE.parent,ROOT/'tests/e2e_native_control/pythonapp']
    if not installed:
        paths.insert(0,ROOT/'python')
    db_workers=2 if mode=='idle' else workers
    env=dict(os.environ,PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',DJANGO_SETTINGS_MODULE='worker_settings',
             D1_XDIST_OUTPUT=str(out),D1_DB_WORKERS=str(db_workers),D1_XDIST_MODE=mode,
             MARIAMEM_PREPARED_HOST=str(host),TMPDIR=str(scratch),
             PYTHONPATH=os.pathsep.join(map(str,paths)))
    args=['-n',str(workers),'--dist='+dist,'--max-worker-restart='+('1' if mode=='restart' else '0')]
    if mode=='collect-only': args.append('--collect-only')
    if mode=='refuse-auto': args=['-n','auto']
    if mode=='refuse-remote': args=['--dist=load','--tx=ssh=not-supported']
    command=[sys.executable,'-m','pytest','-p','xdist.plugin','-p','pytest_django.plugin',
             '-p','mariamem.django.pytest_plugin',str(HERE/'parallel_cases.py'),'-v',
             '--junitxml='+str(out/'junit.xml'),*args]
    process=subprocess.Popen(command,env=env,cwd=ROOT,stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT,text=True,start_new_session=True)
    try:
        stdout,_=process.communicate(timeout=180)
    except BaseException:
        os.killpg(process.pid,signal.SIGKILL);process.communicate();raise
    (out/'stdout.txt').write_text(stdout)
    records={p.stem:[json.loads(line) for line in p.read_text().splitlines()] for p in out.glob('*.jsonl')}
    all_events=[e for events in records.values() for e in events]
    pids={e['pid'] for e in all_events if e['event']=='host'}
    deadline=time.monotonic()+15
    while any(serial.alive(pid) for pid in pids) and time.monotonic()<deadline:
        time.sleep(.02)
    checks=dict(host_reaped=not any(serial.alive(pid) for pid in pids),
                controller_idle=not any(e['event']=='host' for e in records.get('controller',[])),
                declarations_idle=all(e['source_absent'] for e in all_events if e['event']=='declaration_checked'))
    captures=[e for e in all_events if e['event']=='capacity-capture']
    forks=[e for e in all_events if e['event']=='capacity-fork']
    checks['cap1_every_capture']=all(e['requested']==e['resolved']==1 for e in captures)
    checks['finite_fork_waits']=all(e['resolved']==1 and e['timeout']==30 for e in forks)
    active={w:events for w,events in records.items() if any(e['event']=='host' for e in events)}
    bodies=[e for e in all_events if e['event']=='body']
    failures=[];errors=[];tests=[]
    if (out/'junit.xml').exists():
        tree=ET.parse(out/'junit.xml');tests=tree.findall('.//testcase')
        failures=tree.findall('.//failure');errors=tree.findall('.//error')
    if mode.startswith('refuse-'):
        checks['usage_error']=process.returncode==4 and 'ERROR' in stdout
        checks['no_host']=not pids
    elif mode in ('no-db','collect-only'):
        checks['success']=process.returncode==0
        checks['no_host']=not pids
        checks['simple_body']=sum(e['event']=='simple-body' for e in all_events)==int(mode=='no-db')
    else:
        expected_hosts=2 if mode=='idle' else 3 if mode=='restart' else workers
        checks['host_per_active_worker']=len(pids)==len(active)==expected_hosts
        checks['prepared_once']=all(sum(e['event']=='prepared' for e in events)==1 for events in active.values())
        checks['independent_sources']=len({e['port'] for e in all_events if e['event']=='prepared'})==expected_hosts
        checks['worker_names']=all(e['database']=='test_mariamem_'+w for w,events in active.items() for e in events if e['event']=='prepared')
        checks['capture_consumes']=all(e['consumed'] for e in all_events if e['event']=='capture')
        checks['capacity_capture_observed']=len(captures)==sum(e['event']=='capture' for e in all_events)
        checks['capacity_fork_observed']=len(forks)==sum(e['event']=='fork' for e in all_events)
        checks['own_lineage']=all(e['host_pid']==next(x['pid'] for x in events if x['event']=='host') for events in active.values() for e in events if e['event']=='fork')
        if mode=='prepare-failure':
            checks['original_failure']=process.returncode==1 and errors and all('XDIST_GW0_PREPARE_FAILURE' in e.get('message','') for e in errors) and not failures
            checks['refused_worker']=not any(e['event'] in ('body','capture','fork') for e in records['gw0'])
            checks['healthy_peer']=len(bodies)==12-len(errors)>0
        elif mode=='no-restore':
            checks['negative_detected']=process.returncode==1 and not errors and len(failures)>0 and len(bodies)<12
            checks['restoration_assertions']=all('assert [] == [2]' in e.get('message','') or 'assert ((99,),) == ((17,),)' in e.get('message','') for e in failures)
        elif mode in ('crash','restart'):
            checks['worker_failure_retained']=(process.returncode==1 and len(failures)+len(errors)==1
                and all("worker 'gw0' crashed while running" in e.get('message','') for e in failures+errors))
            checks['hard_kill']=sum(e['event']=='worker_kill' for e in all_events)==1
            if mode=='restart':
                checks['fresh_replacement']=len([e for e in records.get('gw2',[]) if e['event']=='prepared'])==1
                checks['replacement_runs']=any(e['event']=='body' for e in records.get('gw2',[]))
                checks['remaining_tests']=len(tests)==12
        elif mode=='cleanup-failure':
            checks['original_cleanup_error']=(process.returncode==1 and any('XDIST_CHILD_CLEANUP_FAILURE' in e.get('message','') for e in failures+errors))
            checks['only_owned_failures']=all('XDIST_CHILD_CLEANUP_FAILURE' in e.get('message','') or 'mariamem cleanup failed; further test admission stopped' in e.get('message','') for e in failures+errors)
            checks['debt_stops_worker']=sum(e['event']=='body' for e in records['gw0'])==1 and 'admission stopped' in stdout
            checks['peer_continues']=any(e['event']=='body' for w,events in active.items() if w!='gw0' for e in events)
        else:
            count=13 if mode=='idle' else 12
            checks['all_tests']=len(tests)==count and len(bodies)==12
            checks['exit']=process.returncode==(1 if mode=='body-failure' else 0)
            checks['expected_failures']=len(failures)==(3 if mode=='body-failure' else 0) and not errors
            if mode=='body-failure':
                checks['failure_identity']=all('PREPARED_BODY_FAILURE' in e.get('message','') for e in failures)
            checks['commits']=sum(e['event']=='commit-observed' for e in all_events)==3
            checks['class_data_once']=all(sum(e['event']=='class-data' for e in events)==int(any(e['event']=='body' and e['kind']=='atomic' for e in events)) for events in active.values())
            checks['class_capture_count']=all(sum(e['event']=='capture' for e in events)==1+len({e['kind'] for e in events if e['event']=='body'}) for events in active.values())
            if mode=='idle':
                checks['unused_workers_no_host']=len(records)==workers+1 and sum(e['event']=='simple-body' for e in all_events)==1
            else:
                checks['prepare_overlap']=sum(e['event']=='overlap' and e['boundary']=='prepare' for e in all_events)==workers
                checks['body_overlap']=sum(e['event']=='overlap' and e['boundary']=='body' for e in all_events)==workers
    checks={key:bool(value) for key,value in checks.items()}
    result=dict(result='PASS' if all(checks.values()) else 'FAIL',mode=mode,workers=workers,dist=dist,
                exit_code=process.returncode,checks=checks,counts=dict(tests=len(tests),failures=len(failures),errors=len(errors)))
    (out/'assessment.json').write_text(json.dumps(result,indent=2)+'\n')
    print(out.name,result['result'],{k:v for k,v in checks.items() if not v},flush=True)
    if not checks['host_reaped']:
        try: os.killpg(process.pid,signal.SIGKILL)
        except ProcessLookupError: pass
    # A hard-killed Python worker cannot run TemporaryDirectory finalizers.
    # The parent oracle owns only this case's TMPDIR and disposes it after PIDs
    # exit. This is test-job cleanup, not a production scratch-recovery claim.
    if checks['host_reaped']:
        shutil.rmtree(scratch)
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host',type=Path,required=True)
    parser.add_argument('--host-source-commit',required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--installed',action='store_true')
    parser.add_argument('--case',help='Only run this mode for focused diagnosis')
    args=parser.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=False)
    identity=serial.check_host(args.host.resolve(),args.host_source_commit)
    paths=list((ROOT/'python/mariamem/django').rglob('*.py'))+list(HERE.glob('*.py'))+list(HERE.parent.glob('*.py'))
    paths+=list((ROOT/'tests/e2e_native_control/pythonapp/orders').rglob('*.py'))
    inputs=dict(installed=args.installed,host=identity,python=sys.version,
        source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        source_dirty=bool(subprocess.check_output(['git','status','--porcelain'],cwd=ROOT)),
        packages={p:importlib.metadata.version(p) for p in ['Django','pytest','pytest-django','pytest-xdist','execnet','mysqlclient']},
        sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in paths})
    (out/'inputs.json').write_text(json.dumps(inputs,indent=2)+'\n')
    cases=[c for c in CASES if args.case is None or c[0]==args.case]
    if not cases: parser.error('unknown case')
    results=[run_case(args.host.resolve(),out/f'{mode}-{n}-{dist}',mode,n,dist,args.installed) for mode,n,dist in cases]
    summary=dict(result='PASS' if all(r['result']=='PASS' for r in results) else 'FAIL',cases=results)
    (out/'assessment.json').write_text(json.dumps(summary,indent=2)+'\n')
    return int(summary['result']!='PASS')


if __name__=='__main__':
    raise SystemExit(main())
