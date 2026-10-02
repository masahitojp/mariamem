#!/usr/bin/env python3
"""Summarize independent diagnostic processes; raw profiles stay in ignored work."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

FIELDS = ('HeapAlloc', 'HeapInuse', 'HeapIdle', 'HeapReleased', 'HeapObjects',
          'StackInuse', 'Sys', 'HeapSys', 'TotalAlloc', 'NumGC', 'LastGC',
          'GCCPUFraction', 'NextGC', 'GCSys', 'MSpanInuse', 'MCacheInuse')


def summarize(work):
    runs = []
    for directory in sorted(p for p in work.iterdir() if p.is_dir()):
        environment = json.loads((directory / 'environment.json').read_text())
        rows = []
        hashes = {}
        for path in sorted(directory.iterdir()):
            hashes[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
            if path.suffix != '.json':
                continue
            data = json.loads(path.read_text())
            if 'memstats' not in data:
                continue
            rows.append(dict(name=data['name'], timestamp=data['timestamp'],
                             memstats={k: data['memstats'][k] for k in FIELDS},
                             os=next(iter(data['os'].values())),
                             goroutines=data['goroutines'], fds=data['fds'],
                             fd_error=data['fd_error'], snapshot_bytes=data['snapshot_bytes'],
                             snapshot_files=data['snapshot_files'],
                             snapshot_inventory=data.get('snapshot_inventory')))
        rows.sort(key=lambda x: x['timestamp'])
        runs.append(dict(run=directory.name, environment=environment,
                         checkpoints=rows, raw_sha256=hashes))
    return runs


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('work', type=Path)
    p.add_argument('--source-sha', required=True)
    p.add_argument('--binary', type=Path, required=True)
    p.add_argument('--helper', type=Path)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    result = dict(source_sha=args.source_sha, runtime='direct-linked generated-Go',
                  platform='Apple M1 / 16 GiB / macOS 27.0.1 (26A434) / arm64 / Go 1.26.8',
                  caveat='Diagnostic checkpoints/profile sampling change scheduling and allocator reuse; not canonical benchmarks. Some early runs used earlier revisions of diagnostic tooling only.',
                  final_harness_sha256=hashlib.sha256(Path(__file__).with_name('main.go').read_bytes()).hexdigest(),
                  final_binary_sha256=hashlib.sha256(args.binary.read_bytes()).hexdigest(),
                  runs=summarize(args.work))
    result['process_cost_source_sha256'] = hashlib.sha256(Path(__file__).parents[1].joinpath('tools/process_cost.c').read_bytes()).hexdigest()
    if args.helper:
        result['process_cost_binary_sha256'] = hashlib.sha256(args.helper.read_bytes()).hexdigest()
    profiles = [('fresh5-live', 'live_instance_gc', 'inuse_space'),
                ('snapshot-4-map', 'released_gc', 'alloc_space'),
                ('snapshot-2', 'snapshot_retained_gc', 'inuse_space'),
                ('forks16-4-map', 'live_children_gc', 'inuse_space'),
                ('forks16-2', 'closed_handles_retained_gc', 'inuse_space'),
                ('forks16-2', 'closed_handles_retained_free', 'inuse_space')]
    result['selected_profile_summaries'] = {}
    for run, name, view in profiles:
        path = args.work / run / (name+'.heap')
        if path.exists():
            key = run+'/'+name+'/'+view
            result['selected_profile_summaries'][key] = subprocess.check_output(
                ['go', 'tool', 'pprof', '-top', '-nodecount=10', '-'+view, str(path)], text=True)
    args.output.write_text(json.dumps(result, indent=2)+'\n')


if __name__ == '__main__':
    main()
