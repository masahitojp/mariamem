#!/usr/bin/env python3
"""Exploratory direct-guest cost; independent processes, no API/Fork emulation."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import subprocess
import time
import tempfile

from sql_execution import Guest


def distribution(values):
    s = sorted(values)
    def quantile(p):
        n = (len(s)-1)*p
        lo = int(n)
        return s[lo] + (s[min(lo+1,len(s)-1)]-s[lo])*(n-lo)
    return dict(n=len(s),min=s[0],p50=quantile(.5),p90=quantile(.9),p95=quantile(.95),p99=quantile(.99),max=s[-1])


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--binary',type=Path,required=True)
    p.add_argument('--cost-helper',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--runs',type=int,default=10)
    p.add_argument('--workers',type=int,nargs='+',default=[1])
    p.add_argument('--production-native-dir',type=Path,
                   help='paired released Wasmer control; verifies manifest once before trials')
    a = p.parse_args()
    if a.runs < 1 or any(n < 1 for n in a.workers): p.error('positive trial/worker counts required')
    binary = a.binary.resolve()
    helper = a.cost_helper.resolve()
    native = a.production_native_dir.resolve() if a.production_native_dir else None
    if native:
        manifest = json.loads((native/'manifest.json').read_text())
        for name,digest in manifest['sha256'].items():
            if hashlib.sha256((native/name).read_bytes()).hexdigest() != digest:
                raise ValueError('production native hash mismatch: '+name)
        if binary != native/'wasmer-headless': p.error('control binary must be the verified native runtime')
    report = dict(schema_version=1,completed=False,exploratory=True,
                  boundary='direct generated guest process; existing guest framing; no public Go host, trust verification or MySQL wire',
                  memory_counter='macOS RSS and physical footprint via existing process_cost.c',
                  binary_bytes=binary.stat().st_size,
                  binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
                  helper_sha256=hashlib.sha256(helper.read_bytes()).hexdigest(),
                  diagnostics=False,trials=[])
    if native:
        report['boundary']='direct released Wasmer guest process; same guest framing; no public Go host or per-Start verification'
        report['production_manifest']=manifest
    a.output.parent.mkdir(parents=True,exist_ok=True)
    def save(): a.output.write_text(json.dumps(report,indent=2)+'\n')
    def counters(guests):
        r = subprocess.run([str(helper),*[str(g.proc.pid) for g in guests]],capture_output=True,text=True,check=True)
        data = json.loads(r.stdout)
        if any('error' in row for row in data.values()): raise RuntimeError(data)
        return data
    try:
        for n in a.workers:
            for trial in range(a.runs):
                guests=[]; logs=[]; directories=[]
                started = time.perf_counter()
                row = dict(workers=n,trial=trial,completed=False)
                report['trials'].append(row)
                try:
                    for i in range(n):
                        log = a.output.with_name(f'{a.output.stem}-{n}-{trial}-{i}.log').open('wb')
                        logs.append(log)
                        command = [str(binary),'measure']
                        env = None
                        if native:
                            import os
                            directory = tempfile.TemporaryDirectory(prefix='wasmer-control-',dir=a.output.parent)
                            directories.append(directory)
                            work = Path(directory.name)
                            (work/'snapshot-out').mkdir()
                            env = os.environ.copy()
                            env['WASMER_DIR']=str(work/'home')
                            command = [str(binary),'run',str(native/'mariamem.wasmu'),'--no-tty',
                                       '--volume',str(work/'snapshot-out')+':/snapshot-out']
                        guests.append(Guest(command,log,env=env))
                    def ready(g):
                        r = g.frame()['result']
                        assert r == {'ready':True,'api_version':2,'max_sessions':16,'snapshot_version':1}
                        return time.perf_counter()-started
                    with ThreadPoolExecutor(max_workers=n) as pool:
                        row['ready_seconds_by_db'] = list(pool.map(ready,guests))
                    row['group_ready_seconds'] = max(row['ready_seconds_by_db'])
                    row['slow_path'] = row['group_ready_seconds'] >= .5
                    sample_start = time.perf_counter()
                    row['ready_counters'] = counters(guests)
                    row['ready_counter_interval_seconds'] = [sample_start-started,time.perf_counter()-started]
                    def sql(g):
                        assert g.call(1)['ok']
                        r = g.call(2,'SELECT 1')
                        assert r['ok'] and r['rows'][0][0]['$h'] == '31'
                        return time.perf_counter()-started
                    with ThreadPoolExecutor(max_workers=n) as pool:
                        row['first_sql_seconds_by_db'] = list(pool.map(sql,guests))
                    row['group_first_sql_seconds'] = max(row['first_sql_seconds_by_db'])
                    for key in ('rss_bytes','primary_bytes','cpu_seconds'):
                        row['ready_'+key] = sum(v[key] for v in row['ready_counters'].values())
                    row['incremental_rss_bytes_per_db'] = row['ready_rss_bytes']/n
                    row['incremental_primary_bytes_per_db'] = row['ready_primary_bytes']/n
                    time.sleep(.1)
                    with ThreadPoolExecutor(max_workers=n) as pool:
                        row['exit_codes'] = list(pool.map(lambda g:g.stop(),guests))
                    assert row['exit_codes'] == [0]*n
                    row['after_close_active_processes'] = sum(g.proc.poll() is None for g in guests)
                    row['after_close_guest_rss_bytes'] = 0 # all processes reaped; not in-process heap reclamation
                    row['completed'] = True
                finally:
                    for g in guests:
                        if g.proc.poll() is None: g.proc.kill(); g.proc.wait()
                        g.proc.stdin.close();g.proc.stdout.close()
                    for log in logs: log.close()
                    for directory in directories: directory.cleanup()
                    save()
                print('workers',n,'trial',trial,'ready_ms',round(row['group_ready_seconds']*1000,2),
                      'SQL_ms',round(row['group_first_sql_seconds']*1000,2),
                      'footprint_MiB_per_DB',round(row['incremental_primary_bytes_per_db']/2**20,2),flush=True)
        report['summary']={str(n):{key:distribution([r[key] for r in report['trials'] if r['workers']==n])
                           for key in ('group_ready_seconds','group_first_sql_seconds','ready_rss_bytes',
                                       'ready_primary_bytes','incremental_rss_bytes_per_db',
                                       'incremental_primary_bytes_per_db','ready_cpu_seconds')}
                           for n in a.workers}
        report['completed']=True
        report['slow_path_threshold_seconds']=.5
        report['clusters']={}
        for n in a.workers:
            group=[r for r in report['trials'] if r['workers']==n]
            report['clusters'][str(n)]={}
            for label,slow in [('fast',False),('slow',True)]:
                cluster=[r for r in group if r['slow_path']==slow]
                report['clusters'][str(n)][label]=dict(count=len(cluster),percentage=100*len(cluster)/len(group),
                    distributions={key:distribution([r[key] for r in cluster]) for key in
                    ('group_ready_seconds','group_first_sql_seconds','ready_cpu_seconds')} if cluster else {})
    finally: save()


if __name__ == '__main__':main()
