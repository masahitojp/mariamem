#!/usr/bin/env python3
"""Informational production Go resource envelope; independent children retain ×16 failures."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import time

from _common import ROOT, RESULTS, environment, positive
from isolation_baseline import percentile


def dist(values):
    return None if not values else {'count': len(values), 'p50': percentile(values, .5), 'p95': percentile(values, .95)}


def summarize(trials):
    groups = []
    for n in (1, 4, 8, 16):
        rows = [t['report']['samples'][0] for t in trials
                if t['kind'] == 'batch' and t['workers'] == n and t['phase'] == 'measurement'
                and t['status'] == 'pass']
        result = {'workers': n, 'successes': len(rows), 'failures': sum(t['status'] == 'failed' for t in trials if t['kind'] == 'batch' and t['workers'] == n)}
        for key in ('group_ready_seconds', 'host_cpu_seconds', 'runtime_cpu_seconds', 'combined_cpu_seconds',
                    'incremental_primary_bytes', 'average_incremental_bytes', 'group_peak_primary_bytes', 'incremental_peak_primary_bytes'):
            result[key] = dist([r[key] for r in rows])
        result['combined_cpu_seconds_per_db'] = dist([r['combined_cpu_seconds']/n for r in rows])
        for state in ('baseline', 'ready', 'after_close'):
            for key in ('primary_bytes', 'rss_bytes', 'private_bytes'):
                result[state+'_'+key] = dist([r[state][key] for r in rows if r[state].get(key) is not None])
        result['after_close_minus_baseline_bytes'] = dist([r['after_close']['primary_bytes']-r['baseline']['primary_bytes'] for r in rows])
        groups.append(result)
    # Match round indices; separate processes/runs, not simultaneous marginals.
    index = {(t['workers'], t['round']): t['report']['samples'][0] for t in trials if t['kind']=='batch' and t['phase']=='measurement' and t['status']=='pass'}
    marginal = []
    for lo, hi in ((1, 4), (4, 8), (8, 16)):
        rounds = sorted(i for n,i in index if n==lo and (hi,i) in index)
        marginal.append({'from':lo,'to':hi,'bytes_per_added_db':dist([(index[hi,i]['incremental_primary_bytes']-index[lo,i]['incremental_primary_bytes'])/(hi-lo) for i in rounds])})
    return {'groups':groups,'marginal_memory':marginal}


def render(report):
    lines=['# Memory and session envelope', '', f"Source: `{report['environment']['commit']}`; {report['environment']['platform']}", '',
           'Physical footprint (macOS) / PSS (Ubuntu); raw RSS secondary. No performance gate.', '',
           '| DBs | completed trials | Group-ready ms p50/p95 | CPU-sec/DB p50/p95 | Incremental MiB/DB p50/p95 |',
           '|---:|---:|---:|---:|---:|']
    for g in report['groups']:
        def f(k,scale=1):
            v=g[k];return 'unavailable' if v is None else f"{v['p50']*scale:.2f} / {v['p95']*scale:.2f}"
        lines.append(f"| {g['workers']} | {g['successes']} | {f('group_ready_seconds',1000)} | {f('combined_cpu_seconds_per_db')} | {f('average_incremental_bytes',1/2**20)} |")
    lines += ['', '## Failures and separate session probe', '']
    for t in report['trials']:
        if t['status']!='pass' or t['kind']=='sessions':
            lines.append(f"- {t['kind']} ×{t['workers']} round {t['round']}: {t['status']}; {t.get('error','')}")
    lines += ['', 'Raw JSON retains G(0)/G(n), private/RSS, peaks, after-close memory, CPU split, raw timelines,',
              'sampling gaps, session establishment times and 1040 recovery, ready mappings and failure exits.',
              'CPU ends at all-ready collection; latency ends at first SQL. Counter collection is not atomic.',
              'Marginal growth matches independent round indices, not same-process simultaneous groups.', '']
    return '\n'.join(lines)


def run_trial(binary, native, helper, output, kind, n, phase, index, timeout):
    raw=output.with_name(f'{output.stem}-{kind}-{n}-{phase}-{index}.partial.json')
    cmd=[str(binary),'--native-dir',str(native),'--json',str(raw),'--resource-probe',kind,
         '--workers',str(n),'--rows','1000','--stage-timing','--guest-stage-timing']
    env=os.environ.copy();env['MARIAMEM_COST_HELPER']=str(helper)
    before=cgroup_events()
    p=subprocess.Popen(cmd,cwd=ROOT,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True)
    error=None
    try:
        stdout,stderr=p.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(p.pid,signal.SIGKILL);stdout,stderr=p.communicate();error='batch timeout (not assumed OOM)'
    # Reap/kill remaining group members after crash, but never hide a cleanup failure.
    try:
        os.killpg(p.pid,0)
    except ProcessLookupError:
        pass
    else:
        os.killpg(p.pid,signal.SIGKILL);error=error or 'child left live process-group members; supervisor cleanup required'
    report=json.loads(raw.read_text()) if raw.is_file() else None
    if raw.exists():raw.unlink()
    okay=p.returncode==0 and report is not None and report.get('completed') and error is None
    if not okay:error=error or (report or {}).get('error') or f'runner exit {p.returncode}; no completed evidence'
    return {'kind':kind,'workers':n,'phase':phase,'round':index,'status':'pass' if okay else 'failed',
            'exit_code':p.returncode,'error':error,'stderr_tail':stderr[-4000:], 'report':report,
            'cgroup_memory_events_before':before,'cgroup_memory_events_after':cgroup_events()}


def cgroup_events():
    p=Path('/sys/fs/cgroup/memory.events')
    try:
        return p.read_text() if p.is_file() else None
    except OSError as exc:
        return {'unavailable': str(exc)}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--native-dir',type=Path,required=True);ap.add_argument('--runs',type=positive,default=20)
    ap.add_argument('--warmup',type=int,default=1);ap.add_argument('--timeout',type=positive,default=300)
    ap.add_argument('--json',type=Path,required=True);a=ap.parse_args()
    if a.warmup<0:ap.error('warmup must be nonnegative')
    output=a.json.resolve();native=a.native_dir.resolve()
    if output.is_relative_to(ROOT) and not output.is_relative_to(RESULTS):ap.error('local output must be under benchmarks/results')
    output.parent.mkdir(parents=True,exist_ok=True)
    binary=ROOT/'build/bench/isolation-go';helper=ROOT/'build/bench/process-cost';binary.parent.mkdir(parents=True,exist_ok=True)
    subprocess.run(['go','build','-trimpath','-o',str(binary),'./benchmarks/goisolation'],cwd=ROOT,check=True)
    subprocess.run(['cc','-O2',str(ROOT/'benchmarks/tools/process_cost.c'),'-o',str(helper)],cwd=ROOT,check=True)
    a.backend='none';report={'schema_version':1,'benchmark':'memory_session_envelope','environment':environment(a),'trials':[]}
    report['environment']['native_manifest']=json.loads((native/'manifest.json').read_text())
    report['environment']['harness_sha256']={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),ROOT/'benchmarks/tools/process_cost.c',*sorted((ROOT/'benchmarks/goisolation').glob('*.go'))]}
    report['environment']['helper_sha256']=hashlib.sha256(helper.read_bytes()).hexdigest()
    report['environment']['runner_sha256']=hashlib.sha256(binary.read_bytes()).hexdigest()
    report['settings']={'runs':a.runs,'warmup':a.warmup,'fixture_rows':1000,'workers':[1,4,8,16],'timeout_seconds':a.timeout}
    def save():
        report.update(summarize(report['trials']));output.write_text(json.dumps(report,indent=2)+'\n')
    def trial(kind,n,phase,i):
        t=run_trial(binary,native,helper,output,kind,n,phase,i,a.timeout);report['trials'].append(t);save();print(kind,n,i,t['status'],flush=True);return t
    # Sessions run before ×16 to preserve their independent result if pressure kills a job.
    for i in range(10):
        if trial('sessions',1,'measurement',i)['status']!='pass':break
    trial('attribution',1,'diagnostic',0)
    blocked=set()
    for phase,count in [('warmup',a.warmup),('measurement',a.runs)]:
        for i in range(count):
            for n in (1,4,8,16):
                if n in blocked:continue
                if trial('batch',n,phase,i)['status']!='pass':blocked.add(n)
    report['completed']=not any(t['status']=='failed' for t in report['trials']);save()
    # Partial failure is evidence, not a disguised success. Always render retained results.
    output.with_suffix('.md').write_text(render(report));print(render(report))
    if not report['completed']:raise SystemExit(1)


if __name__=='__main__':main()
