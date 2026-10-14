from pathlib import Path
import json,statistics
w=Path(__file__).resolve().parents[1]; e=w/'evidence'
s=json.loads((e/'summary.json').read_text())
for r in s:
 a,b=r['original'],r['direct']
 print(r['payload_mib'],r['forks'],r['workers'],
       'snapshot ms',*[round(x['snapshot_seconds']['median']*1000,1) for x in (a,b)],
       'suite s',*[round(x['suite_product_seconds']['median'],3) for x in (a,b)],
       'saved%',round(r['suite_saved_pct'],1),
       'child s',*[round(x['child_window_seconds']['median'],3) for x in (a,b)])
for p in sorted(e.glob('resources-p*.json')):
 d=json.loads(p.read_text()); m=d['go_resource_observation']
 print(p.stem,'alloc MiB',round(m['cumulative_alloc_bytes']/2**20,1),
       'RSS MiB',round(m['process_peak_rss_bytes']/2**20,1),
       'after mappings',m['after']['linear_memory_virtual'],
       'fds',d['fds_before'],d['fds_after'])
for p in sorted(e.glob('trace-p*-traces.json')):
 d=json.loads(p.read_text())
 for t in d:
  if t['operation'] in ('public_snapshot','snapshot_direct_materialize','snapshot_direct_acquire','snapshot_export','snapshot_publish'):
   print(p.stem,t['operation'],round((t['events'][-1]['offset_ns']-t['events'][0]['offset_ns'])/1e6,1))
