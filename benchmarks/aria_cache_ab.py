#!/usr/bin/env python3
"""Bounded 128/16 MiB Aria A/B; no performance gates or production changes."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import subprocess

from _common import ROOT, RESULTS, environment, positive, validate_guest_timing
from isolation_baseline import percentile, summarize_stages


def distribution(values):
    if not values or any(not math.isfinite(v) for v in values):
        raise ValueError('missing/nonfinite metric')
    return {'count': len(values), 'p50': percentile(values, .5), 'p95': percentile(values, .95)}


def summarize(samples, runs):
    rows = [s for s in samples if s['case'] == 'fork' and s['phase'] == 'measurement']
    indexed = {}
    for s in rows:
        key = (s['condition'], s['workers'], s['round'])
        if key in indexed:
            raise ValueError('duplicate condition/worker/round')
        indexed[key] = s
        if len(s['per_db']) != s['workers']:
            raise ValueError('missing per-DB samples')
    summaries, paired, growth, amplification = [], [], [], []
    for n in (1, 4, 8):
        a = {i: s for (mode, workers, i), s in indexed.items() if mode == '128' and workers == n}
        b = {i: s for (mode, workers, i), s in indexed.items() if mode == '16' and workers == n}
        if len(a) != runs or a.keys() != b.keys():
            raise ValueError('missing balanced A/B rounds')
        paired.append({'workers': n, 'control_minus_experiment': {
            'per_group_median_first_sql_seconds': distribution([
                percentile([db['latency_seconds'] for db in a[i]['per_db']], .5)-
                percentile([db['latency_seconds'] for db in b[i]['per_db']], .5) for i in a]),
            **{
            key: distribution([a[i][key]-b[i][key] for i in a]) for key in
            ('group_ready_seconds', 'combined_cpu_seconds', 'average_incremental_bytes')}}})
        for mode, group in (('128', a), ('16', b)):
            entries = list(group.values())
            summary = {'condition': mode, 'workers': n,
                       'first_sql_seconds': distribution([db['latency_seconds'] for s in entries for db in s['per_db']])}
            for key in ('group_ready_seconds', 'host_cpu_seconds', 'runtime_cpu_seconds', 'combined_cpu_seconds',
                        'incremental_primary_bytes', 'average_incremental_bytes', 'group_peak_primary_bytes', 'incremental_peak_primary_bytes'):
                summary[key] = distribution([s[key] for s in entries])
            summary['combined_cpu_seconds_per_db'] = distribution([s['combined_cpu_seconds']/n for s in entries])
            for state in ('baseline', 'ready', 'after_close'):
                for key in ('primary_bytes', 'rss_bytes'):
                    summary[f'{state}_{key}'] = distribution([s[state][key] for s in entries])
                private = [s[state]['private_bytes'] for s in entries]
                summary[f'{state}_private_bytes'] = None if all(v is None for v in private) else distribution(private)
            summary['after_close_minus_baseline_bytes'] = distribution([
                s['after_close']['primary_bytes']-s['baseline']['primary_bytes'] for s in entries])
            summaries.append(summary)
    for mode in ('128', '16'):
        rounds = sorted(i for (m, n, i) in indexed if m == mode and n == 1)
        for lower, upper in ((1, 4), (4, 8)):
            growth.append({'condition': mode, 'from': lower, 'to': upper,
                           'marginal_bytes_per_db': distribution([
                               (indexed[mode, upper, i]['incremental_primary_bytes']-
                                indexed[mode, lower, i]['incremental_primary_bytes'])/(upper-lower) for i in rounds])})
        amplification.append({'condition': mode, 'x8_cpu_amplification': distribution([
            indexed[mode, 8, i]['combined_cpu_seconds']/(8*indexed[mode, 1, i]['combined_cpu_seconds']) for i in rounds])})
    return {'summary': summaries, 'paired_differences': paired, 'marginal_memory': growth,
            'cpu_amplification': amplification}


def render(report):
    lines = ['# Aria page-cache A/B', '', f"Source: `{report['environment']['commit']}`; {report['environment']['platform']}",
             '', 'Physical-footprint accounting on macOS; PSS on Ubuntu. RSS is secondary. Informational; no performance gates.', '',
             '| Cache MiB | DBs | First SQL ms p50/p95 | Group ready ms p50/p95 | Combined CPU s/DB p50/p95 | Incremental MiB/DB p50/p95 |',
             '|---:|---:|---:|---:|---:|---:|']
    for s in report.get('summary', []):
        def fmt(key, scale=1):
            v = s[key]
            return f"{v['p50']*scale:.2f} / {v['p95']*scale:.2f}"
        lines.append(f"| {s['condition']} | {s['workers']} | {fmt('first_sql_seconds', 1000)} | {fmt('group_ready_seconds', 1000)} | {fmt('combined_cpu_seconds_per_db')} | {fmt('average_incremental_bytes', 1/1024**2)} |")
    lines += ['', 'JSON retains G(0), G(n), peak samples, private memory where available, after-close observations,',
              'paired differences, marginal 1→4 / 4→8 memory, CPU amplification, guest/host stages, and over-cache correctness workload.',
              'Group counts run sequentially; marginal/CPU-amplification comparisons match round indices but are not simultaneous measurements.',
              'CPU ends at the all-ready counter collection, including startup bookkeeping/version query and sampler overhead; cleanup excluded.',
              'No acceptance decision yet: require reproducible real memory saving ≈≥64 MiB/DB, correctness/cleanup and no reproducible latency/CPU/tail regression.', '']
    return '\n'.join(lines)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--native-dir', type=Path, required=True)
    p.add_argument('--runs', type=positive, default=20)
    p.add_argument('--warmup', type=int, default=2)
    p.add_argument('--json', type=Path, default=RESULTS/'init-aria-cache.json')
    args = p.parse_args()
    if args.warmup < 0:
        p.error('warmup must be nonnegative')
    if (platform.system(), platform.machine()) not in [('Darwin', 'arm64'), ('Linux', 'x86_64')]:
        p.error('requires supported macOS arm64 or Ubuntu 24.04 x86_64')
    if platform.system() == 'Linux':
        release = Path('/etc/os-release').read_text()
        if 'ID=ubuntu' not in release or 'VERSION_ID="24.04"' not in release:
            p.error('Linux measurements require Ubuntu 24.04')
    output, native = args.json.resolve(), args.native_dir.resolve()
    if output.is_relative_to(ROOT) and not output.is_relative_to(RESULTS):
        p.error('checkout results must remain in ignored benchmarks/results')
    binary, helper = ROOT/'build/bench/aria-go', ROOT/'build/bench/process-cost'
    binary.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(['go', 'build', '-trimpath', '-o', str(binary), './benchmarks/goisolation'], cwd=ROOT, check=True)
    subprocess.run(['cc', '-Wall', '-Wextra', '-Werror', str(ROOT/'benchmarks/tools/process_cost.c'), '-o', str(helper)], check=True)
    args.backend = 'none'
    metadata = environment(args)
    metadata['cpu_clock_ticks_per_second'] = os.sysconf('SC_CLK_TCK') if platform.system() == 'Linux' else None
    for name in ('manifest.json', 'provenance.json'):
        metadata[name] = json.loads((native/name).read_text())
    metadata['measurement_inputs_sha256'] = {str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in [binary, helper, ROOT/'guest/experimental.patch', Path(__file__), ROOT/'benchmarks/tools/process_cost.c']}
    output.parent.mkdir(parents=True, exist_ok=True)
    # Unique raw output; never read stale evidence after executable failure.
    import tempfile
    with tempfile.TemporaryDirectory(prefix='aria-ab-') as directory:
        raw = Path(directory)/'raw.json'
        env = os.environ.copy()
        env['MARIAMEM_COST_HELPER'] = str(helper)
        env.pop('MARIAMEM_EXPERIMENT_ARIA_MIB', None)
        result = subprocess.run([str(binary), '--aria-memory-ab', '--guest-stage-timing', '--native-dir', str(native),
                                 '--rows', '1000', '--runs', str(args.runs), '--warmup', str(args.warmup), '--json', str(raw)],
                                cwd=ROOT, env=env)
        if not raw.is_file():
            raise RuntimeError(f'runner exited before evidence: {result.returncode}')
        report = json.loads(raw.read_text())
    report['environment'].update(metadata)
    report['settings'] = {'runs': args.runs, 'warmup': args.warmup, 'rows': 1000, 'sample_interval_seconds': .05,
                          'order': 'alternate 128/16 then 16/128 each round; counts 1,4,8 sequentially'}
    # Persist incomplete evidence as well; a failed correctness/metric check is never success.
    output.write_text(json.dumps(report, indent=2)+'\n')
    if result.returncode or not report['completed']:
        raise SystemExit(result.returncode or 1)
    forks = [s for s in report['samples'] if s['case'] == 'fork']
    for s in forks:
        for db in s['per_db']:
            validate_guest_timing(db['stage_timings']['host']['guest'])
    report.update(summarize(report['samples'], args.runs))
    report['stage_summary'] = {mode: summarize_stages([s for s in forks if s['condition'] == mode]) for mode in ('128', '16')}
    report['over_cache_summary'] = {mode: {key: distribution([s[key] for s in report['samples']
        if s['case'] == 'aria_over_cache' and s['condition'] == mode])
        for key in ('wall_seconds', 'combined_cpu_seconds')} for mode in ('128', '16')}
    output.write_text(json.dumps(report, indent=2)+'\n')
    output.with_suffix('.md').write_text(render(report))
    print(render(report))


if __name__ == '__main__':
    main()
