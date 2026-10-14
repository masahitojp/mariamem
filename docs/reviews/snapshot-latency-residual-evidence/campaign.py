#!/usr/bin/env python3
"""Bounded same-source Snapshot characterization; no runtime edits."""

from pathlib import Path
import hashlib
import json
import os
import shutil
import statistics
import subprocess
import sys
import time

ROOT = Path.cwd()
WORK = Path(os.environ['MARIAMEM_EXPERIMENT_WORK'])
TEMP = WORK / 'temp'
EVIDENCE = WORK / 'evidence'
SOURCE = '2550bbe1ccf58f9cf65cf4cd801224907a7f9469'


def run(command, *, env=None, timeout=180):
    result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True,
                            text=True, timeout=timeout)
    if result.returncode:
        raise RuntimeError(f'failed {command}:\n{result.stdout}\n{result.stderr}')
    return result.stdout


def mark(trace, name):
    return next(item['offset_ns'] for item in trace['events'] if item['name'] == name) / 1e6


def main():
    os.environ['GOTOOLCHAIN'] = 'go1.26.8'
    if run(['git', 'rev-parse', 'HEAD']).strip() != SOURCE or run(['git', 'status', '--porcelain']).strip():
        raise RuntimeError('source checkout changed or is dirty')
    if 'go1.26.8' not in run(['go', 'version']):
        raise RuntimeError('wrong Go toolchain')
    binary = TEMP / 'ownedprepared'
    run(['go', 'build', '-p', '1', '-o', str(binary), './benchmarks/ownedprepared'], timeout=1200)
    sys.path.insert(0, str(ROOT / 'scripts'))
    from git_identity import verify_go_binary
    buildinfo = verify_go_binary(ROOT, binary, SOURCE, go='go')
    inputs = {'source_commit': SOURCE, 'go': run(['go', 'version']).strip(),
              'platform': run(['uname', '-a']).strip(), 'gomaxprocs': 2,
              'binary_sha256': hashlib.sha256(binary.read_bytes()).hexdigest(),
              'binary_buildinfo': buildinfo, 'forks_per_trial': 1,
              'payload_mib': [0, 10, 100], 'untraced_trials_per_payload': 3,
              'traced_trials_per_payload': 1}
    (EVIDENCE / 'inputs.json').write_text(json.dumps(inputs, indent=2) + '\n')
    records = []
    env = os.environ.copy()
    env['GOMAXPROCS'] = '2'
    env.pop('MARIAMEM_TIMING_DIR', None)
    for payload in (0, 10, 100):
        for trial in range(4):
            traced = trial == 3
            name = f'payload-{payload}-trial-{trial}'
            output = EVIDENCE / f'{name}.json'
            current = env.copy()
            if traced:
                directory = TEMP / f'trace-{payload}'
                directory.mkdir()
                current['MARIAMEM_TIMING_DIR'] = str(directory)
            command = [str(binary), '-lifecycle', 'fork', '-payload-mib', str(payload),
                       '-forks', '1', '-workers', '1', '-workload', 'read', '-tables', '1',
                       '-label', SOURCE, '-out', str(output)]
            start = time.monotonic()
            run(command, env=current, timeout=180)
            report = json.loads(output.read_text())
            snapshot = [item['seconds'] for item in report['operations'] if item['name'] == 'snapshot']
            if len(snapshot) != 1 or report['lifecycle'] != 'fork':
                raise RuntimeError(f'incomplete snapshot oracle in {name}')
            item = {'name': name, 'payload_mib': payload, 'traced': traced,
                    'snapshot_seconds': snapshot[0], 'suite_product_seconds': report['suite_product_seconds'],
                    'process_wall_seconds': time.monotonic() - start}
            if traced:
                traces = {}
                for path in directory.glob('*.json'):
                    trace = json.loads(path.read_text())
                    if trace.get('operation') in {'public_snapshot', 'snapshot', 'snapshot_export', 'snapshot_publish'}:
                        traces[trace['operation']] = trace
                if set(traces) != {'public_snapshot', 'snapshot', 'snapshot_export', 'snapshot_publish'}:
                    raise RuntimeError(f'missing nested traces in {name}: {list(traces)}')
                (EVIDENCE / f'{name}-traces.json').write_text(json.dumps(traces, indent=2) + '\n')
                host = traces['snapshot']
                export = traces['snapshot_export']
                publish = traces['snapshot_publish']
                public = traces['public_snapshot']
                host_wait = mark(host, 'guest_stopped') - mark(host, 'sessions_drained')
                export_time = mark(export, 'end') - mark(export, 'begin')
                item['trace_ms'] = {
                    'public_total': mark(public, 'end') - mark(public, 'begin'),
                    'host_wait': host_wait,
                    'post_guest_transfer': export_time,
                    'host_wait_less_transfer': host_wait - export_time,
                    'publish_total': mark(publish, 'end') - mark(publish, 'begin'),
                    'manifest_residual': mark(publish, 'end') - mark(publish, 'target_inventory_hashed'),
                    'source_cleanup': mark(public, 'source_cleanup_done') - mark(public, 'host_snapshot_returned'),
                    'owned_acquisition': mark(public, 'owned_backing_acquired') - mark(public, 'source_cleanup_done'),
                }
            records.append(item)
            (EVIDENCE / 'campaign.json').write_text(json.dumps(records, indent=2) + '\n')
            print(name, 'snapshot_ms', round(snapshot[0] * 1000, 1), 'traced', traced, flush=True)
    summary = {}
    for payload in (0, 10, 100):
        group = [record['snapshot_seconds'] * 1000 for record in records
                 if record['payload_mib'] == payload and not record['traced']]
        summary[str(payload)] = {'snapshot_median_ms': statistics.median(group),
                                 'snapshot_min_ms': min(group), 'snapshot_max_ms': max(group),
                                 'traced': next(record['trace_ms'] for record in records
                                                if record['payload_mib'] == payload and record['traced'])}
    (EVIDENCE / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == '__main__':
    main()
