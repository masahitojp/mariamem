#!/usr/bin/env python3
"""Independent canonical Go trials: production timing versus opt-in attribution."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace

from _common import ROOT, RESULTS, environment, positive, validate_guest_timing
from isolation_baseline import percentile, summarize, summarize_stages
from stage_report import render as render_stages


from measurement_summary import distribution


def runner_metadata(native):
    """Untimed observations; unavailable diagnostics remain explicit."""
    result = {'github': {key: os.environ.get(key) for key in
              ('GITHUB_RUN_ID', 'GITHUB_RUN_ATTEMPT', 'GITHUB_JOB', 'RUNNER_NAME',
               'RUNNER_OS', 'RUNNER_ARCH', 'ImageOS', 'ImageVersion',
               'MARIAMEM_BENCH_JOB_INDEX', 'MARIAMEM_BENCH_INPUT_SHA256')}}
    commands = {'cpu': ['lscpu'], 'filesystem': ['df', '-T', str(native), tempfile.gettempdir()],
                          'mounts': ['mount'], 'kernel': ['uname', '-a'],
                          'go_target': ['go', 'env', 'GOAMD64', 'GOARM64', 'GOOS', 'GOARCH']}
    if sys.platform == 'darwin':
        commands.update(cpu=['sysctl', '-a'], os_version=['sw_vers'], filesystem=['df', str(native), tempfile.gettempdir()])
    else:
        commands['os_version'] = ['cat', '/etc/os-release']
    for name, command in commands.items():
        try:
            value = subprocess.run(command, capture_output=True, text=True, timeout=10)
            result[name] = {'exit_code': value.returncode, 'output': value.stdout[:131072],
                            'stderr': value.stderr[:4096]}
        except (OSError, subprocess.TimeoutExpired) as error:
            result[name] = {'error': str(error)}
    return result


def trial_command(binary, native, output, condition):
    command = [str(binary), '--native-dir', str(native), '--json', str(output),
               '--runs', '1', '--warmup', '0', '--workers', '1', '--rows', '1000',
               '--queries', '10']
    if condition == 'attribution':
        command += ['--guest-stage-timing']
    return command


def summarize_trials(trials):
    result = {}
    for condition in ('control', 'production', 'attribution'):
        values = []
        for trial in trials:
            if trial['phase'] != 'measurement' or trial['condition'] != condition:
                continue
            # A failed trial invalidates the run; it cannot disappear from percentiles.
            if trial['exit_code'] or not trial['report']['completed']:
                raise ValueError('failed trial: no success verdict or filtered distribution')
            rows = [s for s in trial['report']['samples'] if s['case'] == 'fork_first_sql']
            if len(rows) != 1 or len(rows[0]['per_db']) != 1:
                raise ValueError('expected exactly one independent single-DB Fork')
            values.append(rows[0]['per_db'][0]['latency_seconds'])
        if values:
            result[condition] = distribution(values)
    return result


def render(report):
    lines = ['# Final v0.2 latency baseline', '',
             f"Source: `{report['environment']['commit']}`; {report['environment']['platform']}", '',
             '| Condition | n | min ms | p50 ms | p95 ms | max ms |',
             '| --- | ---: | ---: | ---: | ---: | ---: |']
    for condition, values in report.get('distribution', {}).items():
        lines.append(f"| {condition} | {values['count']} | " +
                     ' | '.join(f"{values[key]*1000:.3f}" for key in ('min', 'p50', 'p95', 'max')) + ' |')
    for condition in report.get('distribution', {}):
        samples = [sample for trial in report.get('trials', [])
                   if trial['phase'] == 'measurement' and trial['condition'] == condition and trial.get('report')
                   for sample in trial['report']['samples'] if sample['case'] == 'fork_first_sql']
        for label, getter, scale in (
            ('Go runner CPU-sec', lambda s: s.get('runner_cpu_seconds'), 1),
            ('Sampled runtime CPU-sec', lambda s: s.get('cost', {}).get('sampled_descendant_cpu_seconds'), 1),
            ('Incremental ready RSS MiB', lambda s: s.get('incremental_ready_rss_bytes'), 1/2**20),
            ('Process-tree peak RSS MiB', lambda s: s.get('cost', {}).get('sampled_process_tree_peak_rss_bytes'), 1/2**20),
        ):
            values = [getter(s)*scale for s in samples if getter(s) is not None]
            if values:
                lines.append(f'{condition} {label} p50/p95: {percentile(values,.5):.3f}/{percentile(values,.95):.3f}')
    lines += ['', 'CPU covers broader batches/sampled runtime edges, not exact first-SQL CPU.']
    metadata = report.get('runner_metadata', {})
    for line in metadata.get('cpu', {}).get('output', '').splitlines():
        if line.startswith(('Model name:', 'CPU(s):', 'Thread(s) per core:')):
            lines.append(line)
    lines += ['', 'No slow trial is discarded.',
              'Production has lifecycle diagnostics off; all conditions retain the existing ps sampler.',
              'Each trial is a fresh Go process and fresh isolated DB. Fixture creation/Snapshot and',
              'two explicitly labelled warmup rounds are outside measured Fork entry → first COUNT.',
              'Runtime CPU sampling may miss startup/exit edges; RSS is secondary, not private/PSS.',
              'Paired differences are measurements, not corrections subtracted from acceptance timings.', '']
    if report.get('error'):
        lines += [f"Run failed: {report['error']}", '']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native-dir', type=Path, required=True)
    parser.add_argument('--runs', type=positive, default=30)
    parser.add_argument('--json', type=Path, required=True)
    parser.add_argument('--production-only', action='store_true', help='fresh-runner primary distribution, diagnostics off')
    parser.add_argument('--comparison-runner', type=Path, help='already-built serial control runner; production-only paired A/B')
    args = parser.parse_args()
    if args.comparison_runner and not args.production_only:
        parser.error('--comparison-runner requires --production-only')
    if args.runs < 20:
        parser.error('at least 20 measured trials per condition are required')
    output = args.json.resolve()
    if output.is_relative_to(ROOT) and not output.is_relative_to(RESULTS):
        parser.error('repository output must be under benchmarks/results/')
    output.parent.mkdir(parents=True, exist_ok=True)
    native = args.native_dir.resolve()
    binary = ROOT/'build/bench/isolation-go'
    binary.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(['go', 'build', '-trimpath', '-o', str(binary), './benchmarks/goisolation'], cwd=ROOT, check=True)
    report = {'benchmark': 'final_v02_latency', 'schema_version': 1,
              'environment': environment(SimpleNamespace(backend='none')),
              'native_manifest': json.loads((native/'manifest.json').read_text()),
              'runner_sha256': hashlib.sha256(binary.read_bytes()).hexdigest(),
              'settings': {'runs': args.runs, 'warmup_rounds': 2, 'rows': 1000, 'workers': [1],
                           'production_only': args.production_only},
              'trials': [], 'completed': False}
    report['runner_metadata'] = runner_metadata(native)
    control = args.comparison_runner.resolve() if args.comparison_runner else None
    if control:
        report['comparison_runner_sha256'] = hashlib.sha256(control.read_bytes()).hexdigest()
    report['harness_sha256'] = {
        str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in [Path(__file__), ROOT/'benchmarks/isolation_baseline.py',
                     ROOT/'benchmarks/stage_report.py', ROOT/'benchmarks/_common.py',
                     *sorted((ROOT/'benchmarks/goisolation').glob('*.go'))]}
    env = os.environ.copy()
    for key in ('MARIAMEM_TIMING_DIR', 'MARIAMEM_INIT_DIAGNOSTICS', 'MARIAMEM_COST_HELPER'):
        env.pop(key, None)
    try:
        for phase, rounds in (('warmup', 2), ('measurement', args.runs)):
            for index in range(rounds):
                conditions = ('production', 'attribution') if index % 2 == 0 else ('attribution', 'production')
                if args.production_only:
                    conditions = (('control', 'production') if index % 2 == 0 else ('production', 'control')) if control else ('production',)
                for condition in conditions:
                    stem = output.with_name(f'{output.stem}-{phase}-{index}-{condition}')
                    raw = stem.with_suffix('.json')
                    with stem.with_suffix('.log').open('w') as log:
                        process = subprocess.run(trial_command(control if condition == 'control' else binary, native, raw, 'production' if condition == 'control' else condition), cwd=ROOT,
                                                 env=env, stdout=log, stderr=subprocess.STDOUT)
                    trial = {'phase': phase, 'round': index, 'condition': condition, 'exit_code': process.returncode,
                             'report': json.loads(raw.read_text()) if raw.is_file() else None}
                    report['trials'].append(trial)
                    output.write_text(json.dumps(report, indent=2)+'\n')
                    if process.returncode or not trial['report'] or not trial['report']['completed']:
                        raise RuntimeError(f'{phase} round {index} {condition} failed; see {stem}.log')
                    if condition == 'attribution':
                        for sample in trial['report']['samples']:
                            for instance in sample.get('per_db', []):
                                validate_guest_timing(instance['stage_timings']['host']['guest'])
        report['distribution'] = summarize_trials(report['trials'])
        report['completed'] = True
    except Exception as error:
        report['error'] = str(error)
        raise
    finally:
        output.write_text(json.dumps(report, indent=2)+'\n')
        output.with_suffix('.md').write_text(render(report))
        samples = [s for t in report['trials'] if t['phase'] == 'measurement' and t['condition'] == 'attribution'
                   and t['report'] for s in t['report']['samples']]
        stages = {'api': 'go', 'environment': report['environment'], 'samples': samples,
                  'summary': summarize(samples), 'stage_summary': summarize_stages(samples)}
        output.with_name(output.stem+'-stages.md').write_text(render_stages(stages))


if __name__ == '__main__':
    main()
