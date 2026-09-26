#!/usr/bin/env python3
"""Summarize measured initialization intervals; never infer CPU from wall time."""
import json
from pathlib import Path
import statistics
import sys

from isolation_baseline import percentile

# Nested engine buckets overlap their enclosing embedded/plugin buckets.
INTERVALS = {
    'embedded options': ('embedded_begin', 'embedded_options_complete'),
    'global components before plugins': ('components_begin', 'plugins_begin'),
    'all plugins': ('plugins_begin', 'plugins_complete'),
    'InnoDB options': ('innodb_plugin_begin', 'innodb_parameters_complete'),
    'InnoDB runtime before buffer pool': ('innodb_runtime_begin', 'buffer_pool_begin'),
    'buffer pool creation': ('buffer_pool_begin', 'buffer_pool_complete'),
    'log/lock/page-cleaner setup': ('buffer_pool_complete', 'innodb_memory_background_complete'),
    'tablespaces/log/recovery/dictionary': ('innodb_memory_background_complete', 'innodb_open_recovery_complete'),
    'doublewrite/undo/transaction setup': ('innodb_open_recovery_complete', 'innodb_transactions_complete'),
    'metadata/temp tablespace/background setup': ('innodb_transactions_complete', 'innodb_background_complete'),
    'remaining InnoDB startup': ('innodb_background_complete', 'innodb_start_complete'),
    'post-plugin components/DDL': ('plugins_complete', 'ddl_recovery_complete'),
    'remaining embedded setup': ('ddl_recovery_complete', 'embedded_complete'),
    'complete embedded initialization': ('embedded_begin', 'embedded_complete'),
}
COUNTERS = ('process_cpu_ns', 'thread_cpu_ns', 'read_bytes', 'write_bytes', 'io_call_ns',
            'wrapped_alloc_balance_bytes', 'wrapped_mmap_balance_bytes', 'wrapped_alloc_requested_bytes', 'pthread_creates')


def validate(record):
    if not isinstance(record, dict) or record.get('version') != 1 or record.get('clock') != 'guest_monotonic':
        raise ValueError('missing/invalid initialization diagnostics; rebuild instrumented guest')
    events = record.get('events', [])
    names = [e['name'] for e in events]
    required = {'guest_main', 'restore_complete', 'ready_prepared'} | {name for pair in INTERVALS.values() for name in pair}
    if len(names) != len(set(names)) or not required <= set(names):
        raise ValueError('initialization boundaries missing or duplicated')
    offsets = [e['offset_ns'] for e in events]
    if any(not isinstance(v, int) or v < 0 for v in offsets) or offsets != sorted(offsets):
        raise ValueError('non-monotonic initialization events')
    if record.get('dropped_records') != 0:
        raise ValueError('bounded initialization collector dropped records; results incomplete')
    return {e['name']: e for e in events}


def records(report):
    for sample in report['samples']:
        if sample['phase'] != 'measurement' or sample['case'] == 'snapshot':
            continue
        for db in sample.get('per_db', []) or [sample]:
            record = db.get('stage_timings', {}).get('host', {}).get('guest', {}).get('initialization')
            if record:
                yield sample, db, record


def summarize(report):
    groups = {}
    for sample, _, record in records(report):
        events = validate(record)
        for label, (a, b) in INTERVALS.items():
            start, end = events[a], events[b]
            row = {'wall_ns': end['offset_ns'] - start['offset_ns']}
            if row['wall_ns'] < 0:
                raise ValueError(f'initialization order changed: {label}')
            for key in COUNTERS:
                x, y = start.get(key), end.get(key)
                row[key] = y-x if isinstance(x, int) and isinstance(y, int) else None
                # OS thread identity may change in WASIX. Zero/negative clocks
                # must not be sold as evidence that a stage used no CPU.
                if key.endswith('cpu_ns') and (not x or not y or row[key] < 0):
                    row[key] = None
            groups.setdefault((sample['case'], sample['workers'], label), []).append(row)
    result = []
    for (case, workers, label), rows in sorted(groups.items()):
        summary = {'case': case, 'workers': workers, 'stage': label, 'count': len(rows)}
        for key in ('wall_ns', *COUNTERS):
            values = [row[key] for row in rows if row[key] is not None]
            summary[key] = {'count': len(values), 'p50': statistics.median(values), 'p95': percentile(values, .95)} if values else None
        result.append(summary)
    return result


def render(report):
    rows = report.get('initialization_summary') or summarize(report)
    lines = ['# MariaDB initialization diagnostics', '',
             f"Source: `{report['environment'].get('commit', 'unknown')}`; fixture rows: {report.get('settings', {}).get('rows', 'unknown')}.", '',
             'Nested buckets overlap. Percentiles are not additive. CPU clocks cover the runtime process / current OS thread, not exclusive engine CPU.', '',
             '| Case | DBs | Stage | n | Wall p50 / p95 ms | Process CPU p50 / p95 ms | Read / write p50 MiB | Alloc balance delta p50 MiB |',
             '| --- | ---: | --- | ---: | ---: | ---: | ---: | ---: |']
    def pair(v):
        return f"{v['p50']/1e6:.2f} / {v['p95']/1e6:.2f}" if v else 'unavailable'
    for row in rows:
        read, write = row['read_bytes'], row['write_bytes']
        allocation = row['wrapped_alloc_balance_bytes']
        io = f"{read['p50']/1024**2:.2f} / {write['p50']/1024**2:.2f}" if read and write else 'unavailable'
        lines.append(f"| {row['case']} | {row['workers']} | {row['stage']} | {row['count']} | {pair(row['wall_ns'])} | {pair(row['process_cpu_ns'])} | {io} | {allocation['p50']/1024**2:.2f} |")
    files = {}
    for sample, _, record in records(report):
        for file in record.get('files', []):
            files.setdefault((sample['case'], sample['workers'], file['path']), []).append(file)
    lines += ['', '## Observed logical database file activity (through ready preparation)', '',
              '| Case | DBs | File | Read p50 MiB | Write p50 MiB | I/O call time p50 ms |',
              '| --- | ---: | --- | ---: | ---: | ---: |']
    for (case, workers, path), observations in sorted(files.items()):
        values = [statistics.median([o[key] for o in observations]) for key in ('read_bytes', 'write_bytes', 'io_call_ns')]
        lines.append(f'| {case} | {workers} | `{path}` | {values[0]/1024**2:.2f} | {values[1]/1024**2:.2f} | {values[2]/1e6:.2f} |')
    lines += ['', 'Raw samples retain linear-memory capacity, wrapped allocator balance/request totals, successful pthread-create count and post-ready OS mappings/thread inventory.',
              'POSIX wrappers miss libc-internal buffered I/O and mmap. Logical I/O uses the WASIX filesystem; it is not host disk traffic.',
              'Summed I/O call durations may overlap threads and do not prove filesystem waiting. Process CPU includes other runtime threads.',
              'Allocator balance is not total heap/RSS: unwrapped allocations, pre-enable frees, allocator metadata/fragmentation and Rust VFS/runtime allocations are excluded.',
              'OS diagnostics are captured once per case after readiness and sampling; unavailable mechanisms are recorded explicitly. RSS is not unique physical memory.', '']
    return '\n'.join(lines)


if __name__ == '__main__':
    print(render(json.loads(Path(sys.argv[1]).read_text())), end='')
