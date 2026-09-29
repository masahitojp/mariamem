#!/usr/bin/env python3
"""Independent canonical Go trials: production timing versus opt-in attribution."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
from types import SimpleNamespace

from _common import ROOT, RESULTS, environment, positive, validate_guest_timing
from isolation_baseline import percentile, summarize, summarize_stages
from stage_report import render as render_stages


def distribution(values):
    return {'count': len(values), 'min': min(values), 'p50': percentile(values, .5),
            'p95': percentile(values, .95), 'max': max(values)}


def trial_command(binary, native, output, condition):
    command = [str(binary), '--native-dir', str(native), '--json', str(output),
               '--runs', '1', '--warmup', '0', '--workers', '1', '--rows', '1000',
               '--queries', '10']
    if condition == 'attribution':
        command += ['--guest-stage-timing']
    return command


def summarize_trials(trials):
    result = {}
    for condition in ('production', 'attribution'):
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
    lines += ['', 'No product change in this baseline. No slow trial is discarded.',
              'Production has lifecycle diagnostics off; both conditions retain the existing ps sampler.',
              'Each trial is a fresh Go process and fresh isolated DB. Fixture creation/Snapshot and',
              'two explicitly labelled warmup rounds are outside measured Fork entry → first COUNT.',
              'Runtime CPU sampling may miss startup/exit edges; RSS is secondary, not private/PSS.',
              'Observer perturbation is a paired difference, not a correction subtracted from timings.', '']
    if report.get('error'):
        lines += [f"Run failed: {report['error']}", '']
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native-dir', type=Path, required=True)
    parser.add_argument('--runs', type=positive, default=30)
    parser.add_argument('--json', type=Path, required=True)
    args = parser.parse_args()
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
              'settings': {'runs': args.runs, 'warmup_rounds': 2, 'rows': 1000, 'workers': [1]},
              'trials': [], 'completed': False}
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
                for condition in conditions:
                    stem = output.with_name(f'{output.stem}-{phase}-{index}-{condition}')
                    raw = stem.with_suffix('.json')
                    with stem.with_suffix('.log').open('w') as log:
                        process = subprocess.run(trial_command(binary, native, raw, condition), cwd=ROOT,
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
