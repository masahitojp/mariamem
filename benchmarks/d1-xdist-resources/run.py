"""Bounded whole-process-tree RSS/time campaign; ps RSS is not physical footprint."""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import signal
import statistics
import subprocess
import sys
import threading
import time
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[2]
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'scripts'))
from git_identity import require_commit

def processes():
    # Read only PID/PPID/RSS/executable, and retain only this sample's descendants.
    text=subprocess.check_output(['ps','-axo','pid=,ppid=,rss=,comm='],text=True)
    return {int(p):dict(ppid=int(parent),rss=int(rss),comm=comm)
            for line in text.splitlines() if len(parts:=line.strip().split(None,3))==4
            for p,parent,rss,comm in [parts]}

def alive(pid):
    try:os.kill(pid,0)
    except ProcessLookupError:return False
    return True

def sample(root,known):
    table=processes();ids={root}
    ids.update(pid for pid,comm in known.items() if pid in table and table[pid]['comm']==comm)
    while True:
        more={pid for pid,proc in table.items() if proc['ppid'] in ids}
        if more<=ids:break
        ids|=more
    selected={pid:table[pid] for pid in ids if pid in table}
    known.update({pid:proc['comm'] for pid,proc in selected.items()})
    totals={'controller':0,'workers':0,'hosts':0,'other':0}
    counts={key:0 for key in totals}
    for pid,proc in selected.items():
        role=('controller' if pid==root else 'hosts' if 'mariamem-host' in proc['comm']
              else 'workers' if 'python' in proc['comm'].lower() else 'other')
        totals[role]+=proc['rss']/1024
        counts[role]+=1
    return dict(total_mib=sum(totals.values()),roles_mib=totals,process_counts=counts)

def run_case(host,out,profile,size,workers,repetition):
    dest=out/f'{profile}-{size}-{workers}-{repetition}';dest.mkdir()
    scratch=dest/'tmp';scratch.mkdir()
    env=dict(os.environ,PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',DJANGO_SETTINGS_MODULE='timing_settings',
        D1_RESOURCE_PROFILE=profile,D1_TIMING_OUT=str(dest),D1_TIMING_SIZE=str(size),
        MARIAMEM_PREPARED_HOST=str(host),MARIAMEM_PREPARED_EVENTS=str(dest/'declaration.jsonl'),
        TMPDIR=str(scratch),PYTHONPATH=os.pathsep.join(map(str,[HERE,ROOT/'python',ROOT/'tests/django_prepared',ROOT/'tests/e2e_native_control/pythonapp'])))
    command=[sys.executable,'-m','pytest','-p','xdist.plugin','-p','pytest_django.plugin','-p','mariamem.django.pytest_plugin',
        str(HERE/'test_workload.py'),'-q','--junitxml='+str(dest/'junit.xml')]
    if workers:command+=['-n',str(workers),'--dist=loadscope','--max-worker-restart=0']
    known={};samples=[];done=threading.Event();ending=[]
    with (dest/'stdout.txt').open('w') as stream:
        start=time.perf_counter()
        proc=subprocess.Popen(command,cwd=ROOT,env=env,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
        def wait():
            proc.wait();ending.append(time.perf_counter());done.set()
        waiter=threading.Thread(target=wait);waiter.start()
        while not done.is_set():
            samples.append(dict(elapsed=time.perf_counter()-start,**sample(proc.pid,known)))
            if time.perf_counter()-start>240:
                os.killpg(proc.pid,signal.SIGKILL);waiter.join();raise TimeoutError(str(dest))
            done.wait(.1)
        waiter.join()
    wall=ending[0]-start
    assert proc.returncode==0,(dest,(dest/'stdout.txt').read_text()[-2000:])
    tree=ET.parse(dest/'junit.xml');tests=tree.findall('.//testcase')
    assert len(tests)==8*size and not tree.findall('.//failure') and not tree.findall('.//error')
    reports=[json.loads(p.read_text()) for p in dest.glob('*.json')]
    active=[r for r in reports if r['host_pids']]
    host_pids=[pid for r in active for pid in r['host_pids']]
    assert len(host_pids)==(workers or 1)
    assert set(host_pids)<=set(known),'sampler missed a root host'
    deadline=time.monotonic()+10
    while any(alive(pid) for pid in known) and time.monotonic()<deadline:time.sleep(.02)
    assert not any(alive(pid) for pid in known),'owned process still alive'
    peak=max(samples,key=lambda r:r['total_mib'])
    row=dict(profile=profile,tests=8*size,workers=workers,repetition=repetition,wall_seconds=wall,
        peak_sum_rss_mib=peak['total_mib'],roles_at_peak_mib=peak['roles_mib'],process_counts_at_peak=peak['process_counts'],
        sampled_processes=len(known),sample_count=len(samples),host_roots=len(host_pids),all_processes_exited=True,
        prepare_seconds=[r['prepare_seconds'] for r in active],forks=sum(r['counts'].get('fork',0) for r in active))
    (dest/'rss.json').write_text(json.dumps(samples,indent=2)+'\n')
    (dest/'result.json').write_text(json.dumps(row,indent=2)+'\n')
    print(json.dumps(row),flush=True)
    return row

def main():
    p=argparse.ArgumentParser();p.add_argument('--host',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--pilot',action='store_true');a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True)
    source=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip();require_commit(ROOT,source)
    assert not subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True)
    host=a.host.resolve();info=subprocess.check_output(['go','version','-m',str(host)],text=True)
    host_source='d99f07cd16a8a11c1644225206a3d1fcc0a39edd';require_commit(ROOT,host_source)
    assert 'vcs.revision='+host_source in info and 'vcs.modified=false' in info
    inputs=dict(source_commit=source,host_source_commit=host_source,host_sha256=hashlib.sha256(host.read_bytes()).hexdigest(),
        platform=platform.platform(),python=sys.version,sampling='ps RSS KiB, 100ms wait plus ps execution; sum may double-count shared pages',
        versions={name:importlib.metadata.version(name) for name in ['Django','pytest','pytest-django','pytest-xdist','execnet','mysqlclient']})
    (out/'inputs.json').write_text(json.dumps(inputs,indent=2)+'\n')
    rows=[]
    for size in ([2] if a.pilot else [2,6,15,30]):
        for rep in range(1 if a.pilot else 3):
            modes=[0,2,4];modes=modes[rep:]+modes[:rep]
            for profile in (['light','heavy'] if rep%2==0 else ['heavy','light']):
                for workers in modes:
                    rows.append(run_case(host,out,profile,size,workers,rep))
                    (out/'samples.json').write_text(json.dumps(rows,indent=2)+'\n')
    summary=[]
    for profile in ('light','heavy'):
        for tests in sorted({r['tests'] for r in rows}):
            for workers in (0,2,4):
                subset=[r for r in rows if r['profile']==profile and r['tests']==tests and r['workers']==workers]
                summary.append(dict(profile=profile,tests=tests,workers=workers,n=len(subset),
                    wall_median=statistics.median(r['wall_seconds'] for r in subset),
                    wall_min=min(r['wall_seconds'] for r in subset),wall_max=max(r['wall_seconds'] for r in subset),
                    peak_rss_median=statistics.median(r['peak_sum_rss_mib'] for r in subset),
                    peak_rss_max=max(r['peak_sum_rss_mib'] for r in subset),
                    prepare_max_median=statistics.median(max(r['prepare_seconds']) for r in subset)))
    (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
if __name__=='__main__':main()
