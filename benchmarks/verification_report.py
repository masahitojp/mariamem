#!/usr/bin/env python3
"""Summarize isolated diagnostic work; never translate savings into a FAST verdict."""
import json
from pathlib import Path
import sys

from isolation_baseline import percentile


def render(report):
    if not report['completed']:
        raise ValueError('incomplete verification experiment')
    lines = ['# Isolated verification attribution', '',
             'Full cases call unchanged production validators. Hash cases compare identical',
             'content work only, with metadata/inventory/identity contracts outside that phase.',
             'They are not parallel full validators or measured end-to-end improvements.', '',
             '| Case | Workers | n | Wall p50/p95 ms | CPU p50/p95 ms | Files | Content MiB | Allocated KiB p50 |',
             '| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
    samples = [s for s in report['samples'] if s['phase'] == 'measurement']
    for case, workers in sorted({(s['case'], s['workers']) for s in samples}):
        rows = [s for s in samples if (s['case'], s['workers']) == (case, workers)]
        def p(key, scale=1):
            values = [r[key]*scale for r in rows if r.get(key) is not None]
            return 'unavailable' if not values else f'{percentile(values,.5):.3f}/{percentile(values,.95):.3f}'
        assert len({(r['files_hashed'], r['content_bytes_hashed']) for r in rows}) == 1
        lines.append(f"| {case} | {workers} | {len(rows)} | {p('latency_seconds',1000)} | {p('cpu_seconds',1000)} | "
                     f"{rows[0]['files_hashed']} | {rows[0]['content_bytes_hashed']/2**20:.3f} | {p('heap_total_allocated_bytes',1/1024).split('/')[0]} |")
    lines += ['', 'Raw JSON includes file hashes, inventory count, CPU/mount environment,',
              'allocation deltas and cumulative process peak RSS (not resettable per operation).',
              'All cases use SHA-256 and warm-cache repetitions; no cache eviction or OS tuning.', '']
    return '\n'.join(lines)


if __name__ == '__main__':
    print(render(json.loads(Path(sys.argv[1]).read_text())), end='')
