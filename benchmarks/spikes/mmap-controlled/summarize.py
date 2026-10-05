#!/usr/bin/env python3
"""Keep every completed observation; no tail filtering or baseline substitution."""
import csv
import json
import math
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT/'benchmarks/v042-mmap-controlled-evidence'
rows = [json.loads(line) for line in (OUT/'measurements.jsonl').read_text().splitlines()]
states = ['released', 'controlled_heap', 'controlled_mmap']
metrics = ['start_sql_ms', 'start_fixture_ms', 'crud_ms', 'crud_cpu_s', 'total_cpu_s', 'close_ms']
summary = {'fresh': {}, 'one20': {}, 'excluded_observations': 0}

def stats(values):
    return {'median': statistics.median(values), 'p95': sorted(values)[math.ceil(.95*len(values))-1], 'min': min(values), 'max': max(values)}

for state in states:
    fresh = [r for r in rows if r['phase'].startswith('fresh-') and r['phase'].endswith('-'+state)]
    repeated = [r for r in rows if r['phase'] == 'one20-'+state]
    assert len(fresh) == 12 and len(repeated) == 20
    assert [r['generation'] for r in repeated] == list(range(1, 21))
    summary['fresh'][state] = {m: stats([r[m] for r in fresh]) for m in metrics}
    summary['one20'][state] = {m: stats([r[m] for r in repeated]) for m in metrics}
    v = summary['one20'][state]
    v['blocks_of_five'] = [{m: statistics.median(r[m] for r in repeated[i:i+5]) for m in metrics} for i in range(0,20,5)]
    for m in ['heap_alloc_bytes', 'heap_sys_bytes', 'fd', 'goroutines']:
        v[m] = stats([r[m] for r in repeated])
        v[m]['last'] = repeated[-1][m]
    for m in ['rss_bytes', 'primary_bytes']:
        v[m] = stats([r['os'][m] for r in repeated])
        v[m]['last'] = repeated[-1]['os'][m]
    if state == 'controlled_mmap':
        assert all(r['mapping']['active_mappings'] == 0 and r['mapping']['release_failures'] == 0 and r['mapping']['creates'] == r['mapping']['releases'] for r in repeated)
        v['mapping_last'] = repeated[-1]['mapping']
    v['first_generation'] = {m: repeated[0][m] for m in metrics}
    v['last_generation'] = {m: repeated[-1][m] for m in metrics}
summary['relative_mmap_vs_heap'] = {boundary: {metric: {'absolute_delta': summary[boundary]['controlled_mmap'][metric]['median']-summary[boundary]['controlled_heap'][metric]['median'], 'percent_delta': 100*(summary[boundary]['controlled_mmap'][metric]['median']/summary[boundary]['controlled_heap'][metric]['median']-1)} for metric in metrics} for boundary in ['fresh', 'one20']}
(OUT/'summary.json').write_text(json.dumps(summary, indent=2)+'\n')
fields = ['state','generation','ready_ms','start_sql_ms','start_fixture_ms','crud_ms','total_cpu_s','close_ms','heap_alloc_bytes','heap_sys_bytes','rss_bytes','physical_footprint_bytes','fd','goroutines']
with (OUT/'generations.csv').open('w', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=fields)
    writer.writeheader()
    for state in states:
        for r in rows:
            if r['phase'] == 'one20-'+state:
                writer.writerow(dict(state=state, **{k:r[k] for k in fields if k in r}, rss_bytes=r['os']['rss_bytes'], physical_footprint_bytes=r['os']['primary_bytes']))
print(json.dumps({'fresh_medians': {s:{m:summary['fresh'][s][m]['median'] for m in metrics} for s in states}, 'one20_medians': {s:{m:summary['one20'][s][m]['median'] for m in metrics} for s in states}},indent=2))
