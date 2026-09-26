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
              'MariaDB server initialization includes InnoDB; those internals remain unsplit.', '']
    return '\n'.join(lines)


if __name__ == '__main__':
    print(render(json.loads(Path(sys.argv[1]).read_text())), end='')
