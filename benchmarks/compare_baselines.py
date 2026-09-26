#!/usr/bin/env python3
"""Compare aligned Go/Python measurements; reject mismatched experimental inputs."""
import json
from pathlib import Path
import sys


def compare(go, python):
    if go.get('api') != 'go' or python.get('api') != 'python':
        raise ValueError('expected Go core and Python consumer reports')
    if not go.get('completed') or not python.get('completed'):
        raise ValueError('both benchmark runs must complete')
    for key in ('commit', 'platform', 'machine'):
        if go['environment'].get(key) != python['environment'].get(key):
            raise ValueError(f'comparison requires matching {key}')
    for key in ('runs', 'warmup', 'workers', 'rows', 'queries', 'clients', 'interval', 'hold', 'stage_timing', 'guest_stage_timing'):
        if go['settings'].get(key) != python['settings'].get(key):
            raise ValueError(f'comparison requires matching setting {key}')
    for name in ('wasmer-headless', 'mariamem.wasmu', 'mariamem.wasmu.json'):
        values = [report['environment']['native_manifest']['sha256'].get(name) for report in (go, python)]
        if not values[0] or values[0] != values[1]:
            raise ValueError(f'comparison requires identical {name} bytes')
    rows = {(row['case'], row['workers']): row for row in python['summary']}
    lines = ['# Paired Go core / Python consumer baseline', '',
             f"Source: `{go['environment']['commit']}`; {go['environment']['platform']}", '',
             '| Case | DBs | Go p50 / p95 ms | Python p50 / p95 ms |',
             '| --- | ---: | ---: | ---: |']
    for row in go['summary']:
        other = rows[(row['case'], row['workers'])]
        if row['count'] != other['count']:
            raise ValueError('comparison requires matching sample counts')
        lines.append(f"| {row['case']} | {row['workers']} | {row['p50_seconds']*1000:.3f} / {row['p95_seconds']*1000:.3f} | {other['p50_seconds']*1000:.3f} / {other['p95_seconds']*1000:.3f} |")
        if row.get('per_db_p50_seconds') is not None:
            lines.append(f"| ↳ per DB | {row['workers']} | {row['per_db_p50_seconds']*1000:.3f} / {row['per_db_p95_seconds']*1000:.3f} | {other['per_db_p50_seconds']*1000:.3f} / {other['per_db_p95_seconds']*1000:.3f} |")
    lines += ['', 'A path comparison, not an attribution to Python language overhead.',
              'Drivers, validation, host process lifecycle, GC/cache state and run order differ.',
              'Inspect nested host/guest stages and raw per-trial CPU/RSS separately.',
              'Go descendant cost excludes its in-process host; runner CPU/RSS are separate.',
              'Sequential runs reduce mutual contention but do not control OS pressure or drift.', '']
    return '\n'.join(lines)


if __name__ == '__main__':
    print(compare(*(json.loads(Path(path).read_text()) for path in sys.argv[1:3])), end='')
