#!/usr/bin/env python3
"""Disposable paired RSA-key experiment; no release artifacts or provisioning."""
import argparse
import hashlib
import json
import os
import platform
from pathlib import Path
import subprocess
import tempfile

from _common import ROOT
from init_report import records, summarize, validate
from isolation_baseline import summarize as summarize_latency
from isolation_baseline import percentile
import statistics


def verify_branches(report, condition):
    count = 0
    for _, _, record in records(report):
        events = validate(record)
        if 'auth_load_complete' not in events or 'auth_load_failed' in events:
            raise ValueError('RSA private/public key load did not succeed')
        generated = 'auth_generate_complete' in events
        if 'auth_generate_failed' in events or generated != (condition == 'control'):
            raise ValueError(f'{condition}: incorrect RSA generation branch')
        if ('auth_generate_begin' in events) != generated:
            raise ValueError('incomplete generation evidence')
        count += 1
    if not count:
        raise ValueError('missing RSA branch evidence')
    return count


def run(native, output, pairs=20, warmup=2):
    output.mkdir(parents=True, exist_ok=False)
    binary = ROOT/'build/bench/auth-keys-go'
    binary.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(['go', 'build', '-o', str(binary), './benchmarks/goisolation'], cwd=ROOT, check=True)
    reports = []
    with tempfile.TemporaryDirectory(prefix='mariamem-public-test-keys-') as directory:
        keys = Path(directory)
        subprocess.run(['openssl', 'genpkey', '-algorithm', 'RSA', '-pkeyopt', 'rsa_keygen_bits:2048', '-out', str(keys/'private.pem')], check=True)
        subprocess.run(['openssl', 'pkey', '-in', str(keys/'private.pem'), '-check', '-noout'], check=True)
        subprocess.run(['openssl', 'pkey', '-in', str(keys/'private.pem'), '-pubout', '-out', str(keys/'public.pem')], check=True)
        key_hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in keys.iterdir()}
        for pair in range(-warmup, pairs):
            # Reverse order every pair; each invocation uses the same canonical
            # fixture/readiness definitions and a fresh disposable source DB.
            order = ['control', 'existing-keys'] if pair % 2 == 0 else ['existing-keys', 'control']
            for condition in order:
                path = output/f'pair-{pair}-{condition}.json'
                env = dict(os.environ)
                env.pop('MARIAMEM_EXPERIMENT_AUTH_KEYS_DIR', None)
                if condition == 'existing-keys':
                    env['MARIAMEM_EXPERIMENT_AUTH_KEYS_DIR'] = str(keys)
                env['MARIAMEM_AUTH_EXPERIMENT_CHECK'] = '1'
                subprocess.run([str(binary), '--native-dir', str(native), '--json', str(path),
                                '--runs', '1', '--warmup', '0', '--workers', '1,4,8',
                                '--rows', '1000', '--queries', '100', '--init-diagnostics',
                                '--memory-diagnostics'], cwd=ROOT, env=env, check=True)
                report = json.loads(path.read_text())
                verified = verify_branches(report, condition)
                reports.append({'pair': pair, 'condition': condition, 'raw': path.name, 'branch_checks': verified})
        if key_hashes != {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in keys.iterdir()}:
            raise ValueError('test key material changed during experiment')
    combined = {}
    for condition in ('control', 'existing-keys'):
        samples = []
        for item in reports:
            if item['pair'] >= 0 and item['condition'] == condition:
                samples.extend(json.loads((output/item['raw']).read_text())['samples'])
        combined[condition] = {'latency': summarize_latency(samples),
                               'initialization': summarize({'samples': samples})}
    result = {'experiment': 'prepared-auth-keys', 'source_commit': subprocess.check_output(
        ['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(), 'pairs': pairs,
        'warmup_pairs': warmup, 'test_key_sha256': key_hashes, 'runs': reports,
        'summary': combined, 'platform': platform.platform(), 'architecture': platform.machine(),
        'native_provenance': json.loads((native/'provenance.json').read_text()),
        'notes': ['Keys generated outside measurement; private material deleted after run.',
                  'Same instrumented guest in both conditions; SQL grant bypass unchanged.',
                  'Plugin ACTIVE/public-key evidence is not a full authentication exchange.',
                  'RSS is sampled, not unique memory; CPU has startup/shutdown blind spots.']}
    # Positive values mean control was slower. Pair-level differences retain
    # alternation rather than subtracting unrelated aggregate percentiles.
    differences = {}
    for pair in range(pairs):
        per_condition = {}
        for condition in combined:
            report = json.loads((output/f'pair-{pair}-{condition}.json').read_text())
            values = {(row['case'], row['workers'], 'end_to_end'): row['p50_seconds']
                      for row in summarize_latency(report['samples'])}
            for row in summarize(report):
                if row['stage'] == 'plugin caching_sha2_password callback':
                    for metric in ('wall_ns', 'process_cpu_ns', 'thread_cpu_ns'):
                        if row[metric]:
                            values[(row['case'], row['workers'], metric)] = row[metric]['p50']/1e9
            per_condition[condition] = values
        a, b = per_condition['control'], per_condition['existing-keys']
        for key in a.keys() & b.keys():
            differences.setdefault(key, []).append(a[key]-b[key])
    result['paired_control_minus_existing_seconds'] = [
        {'case': case, 'workers': workers, 'metric': metric, 'raw': values,
         'p50': statistics.median(values), 'p95': percentile(values, .95)}
        for (case, workers, metric), values in sorted(differences.items())]
    (output/'summary.json').write_text(json.dumps(result, indent=2)+'\n')
    lines = ['# Prepared authentication keys A/B', '', f'Candidate: `{result["source_commit"]}`', '',
             '| Condition | Case | Workers | Stage | p50 ms | p95 ms |', '|---|---|---:|---|---:|---:|']
    for condition, data in combined.items():
        for row in data['initialization']:
            if row['stage'] in ('plugin caching_sha2_password callback', 'post-srv_start plugins', 'complete embedded initialization', 'Aria main page cache'):
                wall = row['wall_ns']
                lines.append(f'| {condition} | {row["case"]} | {row["workers"]} | {row["stage"]} | {wall["p50"]/1e6:.3f} | {wall["p95"]/1e6:.3f} |')
    (output/'summary.md').write_text('\n'.join(lines)+'\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--pairs', type=int, default=20)
    parser.add_argument('--warmup', type=int, default=2)
    args = parser.parse_args()
    if args.pairs < 1 or args.warmup < 0:
        parser.error('positive pairs and nonnegative warmup required')
    run(args.native_dir.resolve(), args.output.resolve(), args.pairs, args.warmup)
