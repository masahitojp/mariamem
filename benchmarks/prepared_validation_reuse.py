#!/usr/bin/env python3
"""Paired prepared-key control versus the existing disposable validation probe."""
import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import shutil
import statistics
import subprocess
import tarfile
import tempfile

from _common import ROOT
from init_report import summarize as init_summary
from isolation_baseline import percentile, summarize, summarize_stages
from prepared_auth_keys import verify_branches
from validation_reuse import hashes, patch


def metrics(report):
    """Aggregate each interval per trial before computing paired differences."""
    groups = {}
    for row in report['samples']:
        if row['case'] != 'fork_first_sql' or row['phase'] != 'measurement':
            continue
        workers = row['workers']
        groups.setdefault((workers, 'batch Fork to SQL'), []).append(row['latency_seconds'])
        for db in row['per_db']:
            trace = db['stage_timings']
            c = {e['name']: e['offset_ns'] for e in trace['caller']}
            h = {e['name']: e['offset_ns'] for e in trace['host']['events']}
            g = {e['name']: e['offset_ns'] for e in trace['host']['guest']['events']}
            public = c['database_returned'] - c['begin'] - h['end']
            host = h['metadata_snapshot_validated'] - h['begin']
            values = {
                'per-DB Fork to SQL': db['latency_seconds'],
                'public outside host': public / 1e9,
                'host validation': host / 1e9,
                'combined preparation': (public + host) / 1e9,
                'restore': (g['restore_complete'] - g['restore_begin']) / 1e9,
                'embedded init': (g['server_init_complete'] - g['server_init_begin']) / 1e9,
                'launch envelope residual': (h['guest_ready'] - h['spawn_begin'] - g['ready_prepared']) / 1e9,
            }
            for name, value in values.items():
                groups.setdefault((workers, name), []).append(value)
    return groups


def aggregate(reports):
    result = {}
    for condition in ('control', 'reuse'):
        samples = [sample for pair in reports for sample in pair[condition]['samples']]
        report = {'samples': samples}
        result[condition] = {
            'latency': summarize(samples), 'stage_summary': summarize_stages(samples),
            'initialization_summary': init_summary(report),
            'waterfall': [{'workers': workers, 'stage': name, 'count': len(values),
                          'raw_seconds': values, 'p50_seconds': statistics.median(values),
                          'p95_seconds': percentile(values, .95)}
                         for (workers, name), values in sorted(metrics(report).items())]}
    differences = {}
    for pair in reports:
        a, b = metrics(pair['control']), metrics(pair['reuse'])
        if a.keys() != b.keys():
            raise ValueError('paired cases differ')
        for key in a:
            # Parallel per-DB observations are correlated; one median per pair.
            differences.setdefault(key, []).append(statistics.median(a[key])-statistics.median(b[key]))
    result['paired_control_minus_reuse'] = [
        {'workers': workers, 'stage': name, 'raw_seconds': values,
         'p50_seconds': statistics.median(values), 'p95_seconds': percentile(values, .95)}
        for (workers, name), values in sorted(differences.items())]
    return result


def run(native, output, pairs=20, warmup=2, restore_attribution=False, source_boundary=False):
    if subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True).strip():
        raise ValueError('commit the experiment before measuring')
    source = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    output.mkdir(parents=True, exist_ok=False)
    if any(p.is_symlink() for p in native.rglob('*')):
        raise ValueError('native bundle must contain regular files')
    runs, reports = [], []
    with tempfile.TemporaryDirectory(prefix='mariamem-prepared-validation-') as temporary:
        temporary = Path(temporary)
        bundle = temporary/'native'
        shutil.copytree(native, bundle)
        before = hashes(bundle)
        for p in bundle.rglob('*'):
            if p.is_file():
                p.chmod(0o555 if p.stat().st_mode & 0o111 else 0o444)
        archive = subprocess.check_output(['git', 'archive', source], cwd=ROOT)
        binaries, changed = {}, {}
        for condition in ('control', 'reuse'):
            root = temporary/condition
            root.mkdir()
            with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
                tar.extractall(root, filter='data')
            if condition == 'reuse' or restore_attribution or source_boundary:
                changed = patch(root)  # Existing two-digest within-call probe only.
            subprocess.run(['go', 'test', './internal/artifacts', './internal/snapshot', './internal/host'], cwd=root, check=True)
            binary = temporary/(condition+'-go')
            subprocess.run(['go', 'build', '-trimpath', '-o', str(binary), './benchmarks/goisolation'], cwd=root, check=True)
            binaries[condition] = binary
        keys = temporary/'keys'
        keys.mkdir()
        subprocess.run(['openssl', 'genpkey', '-algorithm', 'RSA', '-pkeyopt', 'rsa_keygen_bits:2048', '-out', str(keys/'private.pem')], check=True)
        subprocess.run(['openssl', 'pkey', '-in', str(keys/'private.pem'), '-check', '-noout'], check=True)
        subprocess.run(['openssl', 'pkey', '-in', str(keys/'private.pem'), '-pubout', '-out', str(keys/'public.pem')], check=True)
        key_hashes = hashes(keys)
        env = dict(os.environ, MARIAMEM_EXPERIMENT_AUTH_KEYS_DIR=str(keys), MARIAMEM_AUTH_EXPERIMENT_CHECK='1')
        for key in ('MARIAMEM_RESTORE_DIAGNOSTICS', 'MARIAMEM_SOURCE_BOUNDARY_PROBE', 'MARIAMEM_GUEST_RESTORE_SOURCE', 'MARIAMEM_SOURCE_BOUNDARY_PAIR', 'MARIAMEM_SOURCE_BOUNDARY_ORDER'):
            env.pop(key, None)
        if source_boundary:
            env.update(MARIAMEM_RESTORE_DIAGNOSTICS='1', MARIAMEM_SOURCE_BOUNDARY_PROBE='1', MARIAMEM_SOURCE_BOUNDARY_PAIR='1')
        for pair in range(-warmup, pairs):
            current = {}
            order = ('control', 'reuse') if pair % 2 == 0 else ('reuse', 'control')
            if source_boundary:
                env['MARIAMEM_SOURCE_BOUNDARY_ORDER'] = 'host-first' if pair % 2 == 0 else 'guest-first'
                order = ('control',)
            for condition in order:
                path = output/f'pair-{pair}-{condition}.json'
                subprocess.run([str(binaries[condition]), '--native-dir', str(bundle), '--json', str(path),
                                '--runs', '1', '--warmup', '0', '--workers', '1,4,8',
                                '--rows', '1000', '--queries', '100', '--init-diagnostics'],
                               cwd=temporary/condition, env=dict(env, **({'MARIAMEM_GUEST_RESTORE_SOURCE': '1'} if source_boundary and condition == 'reuse' else ({'MARIAMEM_RESTORE_DIAGNOSTICS': '1'} if restore_attribution and condition == 'reuse' else {}))), check=True)
                raw = json.loads(path.read_text())
                if not raw['completed'] or verify_branches(raw, 'existing-keys') != (27 if source_boundary else 14):
                    raise ValueError('missing prepared-key startup evidence')
                if source_boundary:
                    for name in ('control', 'reuse'):
                        current[name] = dict(raw, samples=[s for s in raw['samples'] if s.get('source_condition', name) == name])
                else:
                    current[condition] = raw
                runs.append({'pair': pair, 'condition': condition, 'raw': path.name})
            if pair >= 0:
                reports.append(current)
        if before != hashes(bundle) or key_hashes != hashes(keys):
            raise ValueError('immutable native/key inputs changed')
        identity = {'source_commit': source, 'patched_source_sha256': changed,
                    'binary_sha256': {k: hashlib.sha256(v.read_bytes()).hexdigest() for k, v in binaries.items()},
                    'native_sha256': before, 'test_key_sha256': key_hashes}
    if restore_attribution:
        from restore_report import summarize as restore_summary
        restore = restore_summary([pair['reuse'] for pair in reports])
    result = {'experiment': 'prepared-key-within-call-validation-reuse', **identity,
              'platform': platform.platform(), 'architecture': platform.machine(),
              'pairs': pairs, 'warmup_pairs': warmup, 'runs': runs, 'summary': aggregate(reports),
              'native_provenance': json.loads((native/'provenance.json').read_text()),
              'notes': ['Same read-only native path and test RSA pair in both conditions.',
                        'Only existing disposable two-redundant-AOT-digest patch differs.',
                        'No memory diagnostics; raw sampled CPU/RSS retained.',
                        'Public-outside-host includes public preparation and host trace return tail.',
                        'Envelope residual is not pure Wasmer time; scopes overlap.',
                        'Positive paired differences mean control was slower.']}
    if restore_attribution:
        result['experiment'] = 'prepared-keys-validation-reuse-restore-attribution'
        result['restore_copy'] = restore
        result['notes'] = ['Both conditions use prepared keys and the same validation-reuse patch.', 'Control: restore counters off; reuse: restore counters on; paired difference measures instrumentation perturbation.', 'No memory diagnostics; no storage or validation optimization.']
    if source_boundary:
        from source_boundary_report import summarize as source_summary
        result['experiment'] = 'host-vs-guest-source-restore'
        result['source_boundary'] = source_summary(reports)
        result['notes'] = ['Both conditions: prepared keys, validation reuse, identical copy code and restore instrumentation.', 'Control=host source; reuse=guest-memory source.', 'Guest-source pre-stage and exact byte verification are separately timed; Fork and restore event envelope include these costs.', 'Guest-source retains an extra ~138MiB source; no expensive memory diagnostics.']
    (output/'summary.json').write_text(json.dumps(result, indent=2)+'\n')
    lines = ['# Prepared keys: within-call validation reuse', '', f'Candidate: `{source}`', '',
             '| Condition | Workers | Stage | p50 ms | p95 ms |', '|---|---:|---|---:|---:|']
    for condition in ('control', 'reuse'):
        for row in result['summary'][condition]['waterfall']:
            lines.append(f'| {condition} | {row["workers"]} | {row["stage"]} | {row["p50_seconds"]*1000:.2f} | {row["p95_seconds"]*1000:.2f} |')
    lines += ['', '## Paired control-minus-reuse differences', '',
              '| Workers | Stage | Median ms | p95 ms |', '|---:|---|---:|---:|']
    for row in result['summary']['paired_control_minus_reuse']:
        lines.append(f'| {row["workers"]} | {row["stage"]} | {row["p50_seconds"]*1000:.2f} | {row["p95_seconds"]*1000:.2f} |')
    if restore_attribution:
        lines += ['', '## Restore operation attribution (probe enabled)', '', '| Workers | Component | p50 ms | p95 ms |', '|---:|---|---:|---:|']
        for row in restore:
            if row['metric'] == 'wall_ns' and not row['component'].startswith('file:'):
                lines.append(f"| {row['workers']} | {row['component']} | {row['p50']/1e6:.2f} | {row['p95']/1e6:.2f} |")
        lines += ['', 'Control/probe both use validation reuse; paired differences measure diagnostic perturbation. File/CPU/byte distributions are in summary.json.']
    if source_boundary:
        lines += ['', '## Copy-only source comparison (pre-stage and verification are separate)', '', '| Condition | Workers | Component | p50 ms | p95 ms |', '|---|---:|---|---:|---:|']
        for condition, rows in result['source_boundary'].items():
            for row in rows:
                if row['metric'] == 'wall_ns' and not row['component'].startswith('file:'):
                    lines.append(f"| {condition} | {row['workers']} | {row['component']} | {row['p50']/1e6:.2f} | {row['p95']/1e6:.2f} |")
    (output/'summary.md').write_text('\n'.join(lines)+'\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native-dir', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--pairs', type=int, default=20)
    parser.add_argument('--warmup', type=int, default=2)
    parser.add_argument('--restore-attribution', action='store_true')
    parser.add_argument('--source-boundary', action='store_true')
    args = parser.parse_args()
    if args.restore_attribution and args.source_boundary:
        parser.error('choose exactly one restore probe')
    if args.pairs < 1 or args.warmup < 0:
        parser.error('positive pairs and nonnegative warmup required')
    run(args.native_dir.resolve(), args.output.resolve(), args.pairs, args.warmup, args.restore_attribution, args.source_boundary)
