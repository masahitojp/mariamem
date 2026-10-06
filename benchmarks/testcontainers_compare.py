#!/usr/bin/env python3
"""Run balanced practical isolation comparison. Docker is ONLY the competitor."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]

def percentile(values, p):
    values = sorted(values)
    position = (len(values)-1)*p
    lo = int(position)
    hi = min(lo+1, len(values)-1)
    return values[lo] + (values[hi]-values[lo])*(position-lo)

def summary(report):
    result = []
    samples = [s for s in report['samples'] if s['phase']=='measurement']
    for scenario in ('empty', 'fixture'):
        for workers in (1,4,8):
            for backend in ('mariamem','testcontainers'):
                batches = [s for s in samples if (s['scenario'],s['workers'],s['backend'])==(scenario,workers,backend)]
                expected_rounds=set(range(report.get('warmup',0),report.get('warmup',0)+report['runs']))
                if len(batches)!=report['runs'] or {b['round'] for b in batches}!=expected_rounds:
                    raise ValueError('missing measured batch')
                rows = [r for b in batches for r in b['per_db']]
                entry = {'scenario':scenario,'workers':workers,'backend':backend,'instances':len(rows)}
                if len(rows)!=report['runs']*workers:
                    raise ValueError('missing instance')
                for key in ('latency_seconds','startup_seconds','fixture_seconds'):
                    entry[key] = {f'p{p}':percentile([r[key] for r in rows],p/100) for p in (50,95)}
                for key in ('group_ready_seconds','runner_cpu_seconds'):
                    entry[key] = {f'p{p}':percentile([b[key] for b in batches],p/100) for p in (50,95)}
                costs=[r['ready_cost'] for r in rows]
                for key in ('cpu_seconds','rss_bytes','memory_usage_bytes'):
                    available=[c[key] for c in costs if key in c]
                    entry['ready_'+key] = {'samples':len(available),**({f'p{p}':percentile(available,p/100) for p in (50,95)} if available else {})}
                entry['server_versions']=sorted({r['server_version'] for r in rows})
                result.append(entry)
    return result

def render(report):
    lines=['# mariamem / Testcontainers practical baseline', '',
           f"Source: `{report['source_commit']}`; image: `{report['image']}`", '',
           'Milliseconds, p50 / p95. CPU and memory scopes differ; see report methodology.', '',
           '| Scenario | DBs | Backend | First SQL | Group ready | Startup + connect | Fixture load |',
           '|---|---:|---|---|---|---|---|']
    for s in report['summary']:
        def fmt(key):
            return f"{s[key]['p50']*1000:.1f} / {s[key]['p95']*1000:.1f}"
        lines.append(f"| {s['scenario']} | {s['workers']} | {s['backend']} | {fmt('latency_seconds')} | {fmt('group_ready_seconds')} | {fmt('startup_seconds')} | {fmt('fixture_seconds')} |")
    lines += ['', 'Informational measurements; no thresholds. Nothing published.']
    return '\n'.join(lines)+'\n'

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--native-dir',type=Path,help='retired legacy-only input; omit for generated-Go')
    p.add_argument('--runs',type=int,default=20)
    p.add_argument('--warmup',type=int,default=2)
    p.add_argument('--json',type=Path,default=ROOT/'benchmarks/results/testcontainers-comparison.json')
    args=p.parse_args()
    if args.native_dir is not None: p.error('NativeDir is retired; omit it for generated-Go')
    if platform.system()!='Linux' or platform.machine()!='x86_64':
        p.error('run on Ubuntu 24.04 x86_64 with Docker')
    release=Path('/etc/os-release').read_text()
    if 'ID=ubuntu' not in release or 'VERSION_ID="24.04"' not in release:
        p.error('requires Ubuntu 24.04')
    if args.runs<1 or args.warmup<0:
        p.error('runs positive and warmup nonnegative')
    output=args.json.resolve()
    if output.is_relative_to(ROOT) and not output.is_relative_to(ROOT/'benchmarks/results'):
        p.error('checkout outputs must remain under ignored benchmarks/results')
    inputs=json.loads((ROOT/'benchmarks/testcontainers-inputs.json').read_text())
    guest=json.loads((ROOT/'release/generated-go-inputs.json').read_text())
    # All builds/downloads/image resolution are outside timed work.
    begun=time.monotonic()
    subprocess.run(['docker','pull','--platform','linux/amd64',inputs['image']],check=True)
    image=json.loads(subprocess.check_output(['docker','image','inspect',inputs['image']],text=True))[0]
    expected=inputs['image'].split('@')[1]
    if image['Architecture']!='amd64' or not any(d.endswith('@'+expected) for d in image['RepoDigests']):
        raise ValueError('pre-pulled image identity mismatch')
    docker=json.loads(subprocess.check_output(['docker','info','--format','{{json .}}'],text=True))
    pre_pull=time.monotonic()-begun
    binary=ROOT/'build/bench/competitive'
    binary.parent.mkdir(parents=True,exist_ok=True)
    subprocess.run(['go','build','-p','1','-mod=readonly','-trimpath','-o',str(binary),'.'],cwd=ROOT/'benchmarks/competitive',check=True)
    output.parent.mkdir(parents=True,exist_ok=True)
    raw=output.with_suffix('.partial.json')
    if raw.exists():
        raw.unlink()  # Never mistake an older invocation for this run's evidence.
    env=os.environ.copy()
    for name in ('MARIAMEM_NATIVE_DIR','MARIAMEM_EXPERIMENT_RESTORE','MARIAMEM_INIT_DIAGNOSTICS','MARIAMEM_MEMORY_DIAGNOSTICS','MARIAMEM_VALIDATION_REUSE'):
        env.pop(name,None)
    process=subprocess.run([str(binary),'--image',inputs['image'],'--runs',str(args.runs),'--warmup',str(args.warmup),'--json',str(raw)],cwd=ROOT,env=env)
    if not raw.is_file():
        raise RuntimeError('runner failed before producing evidence')
    report=json.loads(raw.read_text())
    report['collected_at_utc']=time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())
    report['benchmark_modules']=subprocess.check_output(['go','list','-m','-json','all'],cwd=ROOT/'benchmarks/competitive',text=True)
    report.update({'inputs':inputs,'image_inspect':image,'docker_info':docker,'pre_pull_seconds':pre_pull,'os_release':release,'platform':platform.platform(),'runtime_kind':'generated-go','guest_sha256':guest['guest_sha256'],'runner_sha256':hashlib.sha256(binary.read_bytes()).hexdigest()})
    if process.returncode==0 and report['completed']:
        report['summary']=summary(report)
        # Reuse the maintained stage summarizer without timing another benchmark.
        from isolation_baseline import summarize_stages
        adapted=[]
        for b in report['samples']:
            if b['backend']!='mariamem':continue
            adapted.append({'case':'start_first_sql' if b['scenario']=='empty' else 'fork_first_sql','phase':b['phase'],'workers':b['workers'],'per_db':[{'stage_timings':{'host':r['host_trace'],'caller':r['caller_events']},'latency_seconds':r['latency_seconds']} for r in b['per_db']]})
        report['stage_summary']=summarize_stages(adapted)
        report['runner_environment']={key:os.environ.get(key) for key in ('ImageOS','ImageVersion','RUNNER_ARCH','RUNNER_OS')}
        report['environment']={'commit':report['source_commit'],'platform':report['platform'],'go':report['go']}
        from stage_report import render as waterfall
        output.with_name(output.stem+'-stages.md').write_text(waterfall({'environment':report['environment'],'api':'go','stage_summary':report['stage_summary'],'summary':[],'samples':[]}))
        output.with_suffix('.md').write_text(render(report))
        print(render(report))
    output.write_text(json.dumps(report,indent=2)+'\n')
    if process.returncode or not report['completed']:
        raise SystemExit(process.returncode or 1)

if __name__=='__main__':main()
