#!/usr/bin/env python3
"""Render existing lifecycle JSON as a compact measured waterfall; no new samples."""
import json
from pathlib import Path
import statistics
import sys


def render(report):
    environment = report.get('environment', {})
    lines = ['# Guest startup stage measurement', '',
             f"Source: `{environment.get('commit', 'unknown')}`; platform: {environment.get('platform', 'unknown')}; API: {report.get('api', 'python')}; toolchain: {environment.get('go', environment.get('python', 'unknown'))}.", '',
             'Nested scopes overlap; do not sum percentile columns. No performance gates.', '',
             '| Case | DBs | Scope / ending boundary | n | p50 ms | p95 ms |',
             '| --- | ---: | --- | ---: | ---: | ---: |']
    for row in report.get('stage_summary', []):
        lines.append(f"| {row['case']} | {row['workers']} | {row['scope']} / {row['stage']} | {row['count']} | {row['p50_seconds']*1000:.3f} | {row['p95_seconds']*1000:.3f} |")
    work = {}
    for sample in report.get('samples', []):
        if sample.get('phase') != 'measurement':
            continue
        for instance in sample.get('per_db', []):
            trace = instance.get('stage_timings') or {}
            for scope in ('native_verification', 'snapshot_verification'):
                events = trace.get(scope, {}).get('events') or []
                if events:
                    key = (sample['case'], sample['workers'], scope)
                    work.setdefault(key, []).append((sum(e.get('bytes_read', 0) for e in events),
                                                    sum(e.get('files_touched', 0) for e in events)))
    if work:
        lines += ['', '## Verification logical work', '',
                  'File visits include repeated metadata/open visits, not unique files. Bytes include the sidecar reread; they are not physical I/O.', '',
                  '| Case | DBs | Scope | Median logical bytes read | Median file visits |',
                  '| --- | ---: | --- | ---: | ---: |']
        for (case, workers, scope), rows in work.items():
            lines.append(f"| {case} | {workers} | {scope} | {statistics.median(r[0] for r in rows):.0f} | {statistics.median(r[1] for r in rows):.0f} |")
    lines += ['', '## End-to-end and correlated process observations', '',
              '| Case | DBs | p50 / p95 ms | Median descendant CPU s | Median sampled descendant RSS MiB |',
              '| --- | ---: | ---: | ---: | ---: |']
    def median(rows, key, scale=1):
        values = [row.get('cost', {}).get(key) for row in rows]
        values = [value / scale for value in values if value is not None]
        return f'{statistics.median(values):.3f}' if values else 'unavailable'
    for row in report.get('summary', []):
        samples = [sample for sample in report['samples'] if sample['phase'] == 'measurement'
                   and (sample['case'], sample['workers']) == (row['case'], row['workers'])]
        lines.append(f"| {row['case']} | {row['workers']} | {row['p50_seconds']*1000:.3f} / {row['p95_seconds']*1000:.3f} | {median(samples, 'sampled_descendant_cpu_seconds')} | {median(samples, 'sampled_peak_rss_bytes', 1024**2)} |")
    lines += ['', 'Raw JSON retains per-trial CPU/RSS samples and incremental RSS per DB.',
              'For Go, descendant columns exclude the in-process host; runner CPU/RSS and tree peak are separate JSON fields.',
              'CPU misses startup/exit edges; RSS sums can double-count shared pages.',
              'The startup envelope residual includes pre-main runtime/CRT initialization,',
              'C/C++ static constructors, diagnostic file writing and ready delivery/scheduling;',
              'it is not pure Wasmer time.',
              ('See initialization_summary for measured InnoDB subdivisions.' if report.get('initialization_summary') else
               'MariaDB server initialization includes InnoDB; those internals are unsplit in this report.'), '']
    return '\n'.join(lines)


if __name__ == '__main__':
    print(render(json.loads(Path(sys.argv[1]).read_text())), end='')
