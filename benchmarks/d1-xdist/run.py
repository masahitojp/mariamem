"""Finite local worker spike; no build, benchmark or CI orchestration."""
import argparse
import json
import importlib.metadata
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / 'tests/django_prepared'))
import run as base


def run(host, output, workers, mode, dist):
    output.mkdir(parents=True)
    env = dict(os.environ, PYTEST_DISABLE_PLUGIN_AUTOLOAD='1', DJANGO_SETTINGS_MODULE='spike_settings',
               D1_XDIST_OUTPUT=str(output), D1_XDIST_WORKERS=str(workers), D1_XDIST_MODE=mode,
               MARIAMEM_PREPARED_HOST=str(host),
               PYTHONPATH=os.pathsep.join(map(str,[HERE, ROOT/'python', ROOT/'tests/django_prepared',
                   ROOT/'tests/e2e_native_control/pythonapp'])))
    command = [sys.executable, '-m', 'pytest', '-p', 'xdist.plugin', '-p', 'pytest_django.plugin',
               '-p', 'mariamem.django.pytest_plugin', str(HERE/'test_probe.py'), '-n', str(workers),
               '--max-worker-restart=0', '--dist='+dist, '-v', '--junitxml='+str(output/'junit.xml')]
    process = subprocess.Popen(command, env=env, cwd=ROOT, stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT, text=True, start_new_session=True)
    try:
        stdout,_ = process.communicate(timeout=180)
    except BaseException:
        os.killpg(process.pid, signal.SIGKILL)
        process.communicate()
        raise
    (output/'stdout.txt').write_text(stdout)
    records={p.stem:[json.loads(line) for line in p.read_text().splitlines()] for p in output.glob('*.jsonl')}
    pids={r['pid'] for rs in records.values() for r in rs if r['event']=='host'}
    deadline=time.monotonic()+5
    while any(base.alive(pid) for pid in pids) and time.monotonic()<deadline:
        time.sleep(.02)
    check=dict(host_reaped=not any(base.alive(pid) for pid in pids),
               host_per_worker=len(pids)==workers,
               controller_idle=not any(r['event']=='host' for r in records.get('controller',[])))
    active={worker:rs for worker,rs in records.items() if worker.startswith('gw')}
    check['all_workers_seen']=len(active)==workers
    check['prepared_once']=all(sum(r['event']=='prepared' for r in rs)==1 for rs in active.values())
    check['independent_sources']=len({r['port'] for rs in active.values() for r in rs if r['event']=='prepared'})==workers
    check['worker_names']=all(r['database']=='test_mariamem_'+w for w,rs in active.items() for r in rs if r['event']=='prepared')
    check['capture_consumes']=all(r['consumed'] for rs in active.values() for r in rs if r['event']=='capture')
    check['own_lineage']=all(r['host_pid']==next(x['pid'] for x in rs if x['event']=='host') for rs in active.values() for r in rs if r['event']=='fork')
    check['prepare_overlap']=sum(r['event']=='overlap' and r['boundary']=='prepare' for rs in active.values() for r in rs)==workers
    counts={key:len(ET.parse(output/'junit.xml').findall('.//'+key)) for key in ('testcase','failure','error')}
    bodies=[r for rs in active.values() for r in rs if r['event']=='body']
    check['twelve_tests']=counts['testcase']==12
    if mode=='prepare-failure':
        check['failure_observed']=process.returncode==1 and 'XDIST_GW0_PREPARE_FAILURE' in stdout and counts['error']>0
        check['failing_worker_refused']=not any(r['event']=='body' for r in active.get('gw0',[]))
        check['healthy_worker_runs']=len(bodies)>0
    elif mode=='no-restore':
        check['negative_oracle_detected']=process.returncode==1 and counts['failure']>0 and len(bodies)<12
    else:
        check['bodies_restored']=len(bodies)==12
        check['body_overlap']=sum(r['event']=='overlap' and r['boundary']=='body' for rs in active.values() for r in rs)==workers
        check['exit']=process.returncode==(1 if mode=='body-failure' else 0)
        check['failure_count']=counts['failure']==(3 if mode=='body-failure' else 0) and counts['error']==0
        check['class_data_once_per_worker']=all(sum(r['event']=='class-data' for r in rs)==int(any(r['event']=='body' and r['kind']=='atomic' for r in rs)) for rs in active.values())
        check['class_capture_count']=all(sum(r['event']=='capture' for r in rs)==1+len({r['kind'] for r in rs if r['event']=='body'}) for rs in active.values())
    result=dict(result='PASS' if all(check.values()) else 'FAIL', mode=mode,workers=workers,dist=dist,
                exit_code=process.returncode,checks=check,counts=counts,command=command)
    (output/'assessment.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2),flush=True)
    if not check['host_reaped']:
        try: os.killpg(process.pid,signal.SIGKILL)
        except ProcessLookupError: pass
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--mode',default='healthy')
    parser.add_argument('--workers',type=int,default=2)
    parser.add_argument('--dist',default='load')
    args=parser.parse_args()
    args.output=args.output.resolve()
    identity=base.check_host(args.host.resolve(),'b3b3b46a8807482ad3f96725af86e031fe369b01')
    result=run(args.host.resolve(),args.output,args.workers,args.mode,args.dist)
    paths=list(HERE.glob('*.py'))+list((ROOT/'python/mariamem/django').rglob('*.py'))
    paths+=list((ROOT/'tests/e2e_native_control/pythonapp/orders').rglob('*.py'))
    paths+=list((ROOT/'tests/django_prepared').glob('*.py'))
    (args.output/'inputs.json').write_text(json.dumps(dict(host=identity,
        source_commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True,cwd=ROOT).strip(),
        source_dirty=bool(subprocess.check_output(['git','status','--porcelain'],cwd=ROOT)),
        packages={name:importlib.metadata.version(name) for name in ['Django','pytest','pytest-django','pytest-xdist','execnet','mysqlclient']},
        python=sys.version,sha256={str(p.relative_to(ROOT)):base.digest(p) for p in paths}),indent=2)+'\n')
    return 0 if result['result']=='PASS' else 1


if __name__=='__main__':
    raise SystemExit(main())
