#!/usr/bin/env python3
"""Reusable diagnostics-off v0.4 baseline supervisor; no product changes."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
from types import SimpleNamespace

from _common import ROOT, environment
from final_latency import distribution, runner_metadata
from memory_envelope import summarize
from isolation_baseline import summarize_stages


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--native-dir', type=Path, required=True)
    p.add_argument('--runs', type=int, default=30)
    p.add_argument('--scaling-runs', type=int, default=10)
    p.add_argument('--json', type=Path, required=True)
    a = p.parse_args()
    if a.runs < 30 or a.scaling_runs < 1:
        p.error('30+ startup trials and positive scaling trials required')
    output = a.json.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    native = a.native_dir.resolve()
    binary = ROOT/'build/bench/isolation-go'
    helper = ROOT/'build/bench/process-cost'
    subprocess.run(['go', 'build', '-trimpath', '-o', str(binary), './benchmarks/goisolation'], cwd=ROOT, check=True)
    subprocess.run(['cc', '-O2', str(ROOT/'benchmarks/tools/process_cost.c'), '-o', str(helper)], check=True)
    manifest = json.loads((native/'manifest.json').read_text())
    for name, digest in manifest['sha256'].items():
        if hashlib.sha256((native/name).read_bytes()).hexdigest() != digest:
            raise ValueError('native hash mismatch: '+name)
    report = dict(schema_version=1, benchmark='v04_baseline', completed=False,
                  environment=environment(SimpleNamespace(backend='none')),
                  runner_metadata=runner_metadata(native), native_manifest=manifest,
                  settings=dict(startup_runs=a.runs, scaling_runs=a.scaling_runs, rows=1000,
                                workers=[1,4,8,16], interval_seconds=.05, hold_seconds=.1),
                  binary_sha256=hashlib.sha256(binary.read_bytes()).hexdigest(),
                  helper_sha256=hashlib.sha256(helper.read_bytes()).hexdigest(), trials=[])
    report['harness_sha256'] = {str(f.relative_to(ROOT)): hashlib.sha256(f.read_bytes()).hexdigest()
                               for f in [Path(__file__), *sorted((ROOT/'benchmarks/goisolation').glob('*.go'))]}
    def save():
        output.write_text(json.dumps(report, indent=2)+'\n')
    env = os.environ.copy()
    for k in ('MARIAMEM_TIMING_DIR','MARIAMEM_INIT_DIAGNOSTICS','MARIAMEM_MEMORY_DIAGNOSTICS','MARIAMEM_COST_HELPER'):
        env.pop(k, None)
    def trial(kind, n, phase, i):
        raw = output.with_name(f'{output.stem}-{kind}-{n}-{phase}-{i}.json')
        cmd = [str(binary), '--native-dir', str(native), '--json', str(raw), '--runs','1',
               '--warmup','0','--workers',str(n),'--rows','1000','--queries','10']
        trial_env = env.copy()
        if kind == 'batch':
            cmd += ['--resource-probe','batch']
            trial_env['MARIAMEM_COST_HELPER'] = str(helper)
        if kind == 'attribution':
            cmd += ['--guest-stage-timing']
        with raw.with_suffix('.log').open('w') as log:
            child = subprocess.run(cmd, cwd=ROOT, env=trial_env, stdout=log, stderr=subprocess.STDOUT, timeout=300)
        data = json.loads(raw.read_text()) if raw.exists() else None
        row = dict(kind=kind, workers=n, phase=phase, round=i, exit_code=child.returncode,
                   status='pass' if child.returncode==0 and data and data['completed'] else 'failed', report=data)
        report['trials'].append(row); save()
        print(kind,n,phase,i,row['status'],flush=True)
        if row['status'] != 'pass':
            raise RuntimeError('failed trial: '+str(raw))
    try:
        for phase, count in [('warmup',2),('measurement',a.runs)]:
            for i in range(count): trial('startup',1,phase,i)
        for phase, count in [('warmup',1),('measurement',a.scaling_runs)]:
            for i in range(count):
                for n in (1,4,8,16): trial('batch',n,phase,i)
        for i in range(5): trial('attribution',1,'measurement',i)
        samples = [s for t in report['trials'] if t['kind']=='startup' and t['phase']=='measurement' for s in t['report']['samples']]
        report['startup'] = {case: distribution([s['latency_seconds'] for s in samples if s['case']==case])
                             for case in ('start_first_sql','start_seeded','snapshot','fork_first_sql')}
        report['api_return'] = {case: distribution([s.get('api_return_seconds', s['per_db'][0]['api_return_seconds'] if s.get('per_db') else 0) for s in samples if s['case']==case]) for case in ('start_first_sql','fork_first_sql')}
        report['scaling'] = summarize(report['trials'])
        stages = [s for t in report['trials'] if t['kind']=='attribution' for s in t['report']['samples']]
        report['stage_summary'] = summarize_stages(stages)
        report['completed'] = True
    finally: save()

if __name__ == '__main__': main()
