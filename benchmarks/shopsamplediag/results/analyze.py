"""Offline replay. Missing server counters remain missing, never numeric zero."""
from pathlib import Path
import hashlib,json,math,statistics as st,sys
P=Path(__file__).resolve().parent
runs=json.loads((P/'observations.json').read_text())
expected={'begin':1,'prepare_order':1,'prepare_item':1,'prepare_stock':1,'order_insert':40,'item_insert':100,'stock_update':100,'commit':1,'statement_close':3}
def stats(v):
 return dict(n=len(v),p50=st.median(v),p95=sorted(v)[math.ceil(len(v)*.95)-1],min=min(v),max=max(v),sum=sum(v))
summary={'runs':{},'interpretation':'One current-only P8 primary suite per mode; warmups separate. Status probes warm the connection and may perturb scheduling/caches. No speedup or causal setting benefit claim.'}
assert len(runs)==4 and [r['name'] for r in runs]==['control-warmup','diagnostic-warmup','control','diagnostic']
for r in runs:
 assert r['accepted'] and r['exit_code']==0 and r['scratch_empty']
 t=r['trace'];m=t['meta'];ss=t['spans'];assert m['parallel']=='8' and m['fork_cap']=='9' and m['test_exit']=='0' and m['active_mappings_after']=='0'
 assert m['read_cases']=='50' and m['write_cases']=='20'
 for k,n in [('read',50),('write',20),('fork',21),('sample',21)]:assert sum(x['kind']==k for x in ss)==n
 assert all(0<=x['start_ms']<=x['end_ms']<=t['elapsed_ms'] for x in ss)
 samples={x['lane']:x for x in ss if x['kind']=='sample'};assert len(samples)==21
 ds=r['diagnostics']['records'] or [];active=r['name'].startswith('diagnostic');assert len(ds)==(21 if active else 0)
 entry=dict(suite_ms=t['elapsed_ms'],cpu_ms=float(m['cpu_ms']),sample_outer_ms=stats([x['end_ms']-x['start_ms'] for x in samples.values()]),fork_ms=stats([x['end_ms']-x['start_ms'] for x in ss if x['kind']=='fork']))
 if active:
  assert len({x['lane'] for x in ds})==21
  children=[]
  for d in ds:
   assert not d.get('error') and d['lane'] in samples
   assert set(d['ops_ms'])==set(expected)
   for k,n in expected.items():assert len(d['ops_ms'][k])==n and all(v>=0 for v in d['ops_ms'][k])
   totals={k:sum(v) for k,v in d['ops_ms'].items()};residual=d['body_ms']-sum(totals.values());assert residual>=-0.01
   outer=samples[d['lane']]['end_ms']-samples[d['lane']]['start_ms'];assert d['body_ms']+d['probe_before_ms']+d['probe_after_ms']<=outer+.01
   settings={k.lower():v for k,v in d['settings'].items()}
   for k,v in {'innodb_buffer_pool_size':'16777216','innodb_log_buffer_size':'2097152','table_open_cache':'32','foreign_key_checks':'ON','unique_checks':'ON','check_constraint_checks':'ON'}.items():assert settings[k]==v,(k,settings.get(k))
   before={k.lower():int(v) for k,v in d['status_before'].items()};after={k.lower():int(v) for k,v in d['status_after'].items()}
   delta={k:after[k]-before[k] for k in sorted(before.keys()&after.keys())}
   children.append(dict(lane=d['lane'],body_ms=d['body_ms'],operation_total_ms=totals,residual_ms=residual,status_delta=delta,missing_status=[k for k in r['diagnostics']['requested_status'] if k.lower() not in delta]))
  entry['children']=children
  entry['body_ms']=stats([d['body_ms'] for d in ds]);entry['probe_before_ms']=stats([d['probe_before_ms'] for d in ds]);entry['probe_after_ms']=stats([d['probe_after_ms'] for d in ds])
  entry['per_child_operation_total_ms']={k:stats([c['operation_total_ms'][k] for c in children]) for k in expected}
  entry['per_call_operation_ms']={k:stats([v for d in ds for v in d['ops_ms'][k]]) for k in expected}
  entry['operation_share_of_total_body_percent']={k:100*sum(c['operation_total_ms'][k] for c in children)/sum(d['body_ms'] for d in ds) for k in expected}
  keys=set.intersection(*(set(c['status_delta']) for c in children));entry['status_delta']={k:stats([c['status_delta'][k] for c in children]) for k in sorted(keys)}
  entry['missing_status']=sorted(set(k for c in children for k in c['missing_status']))
  entry['settings_values']={k:sorted({d['settings'].get(k,'MISSING') for d in ds}) for k in sorted(set.union(*(set(d['settings']) for d in ds)))}
  entry['missing_settings']=sorted(set(k for k in r['diagnostics']['requested_settings'] if any(k.lower() not in {n.lower() for n in d['settings']} for d in ds)))
 summary['runs'][r['name']]=entry
text=json.dumps(summary,indent=2)+'\n'
if '--check' in sys.argv:
 assert (P/'summary.json').read_text()==text
 for n,h in json.loads((P/'SHA256SUMS.json').read_text()).items():assert hashlib.sha256((P/n).read_bytes()).hexdigest()==h,n
 print('PASS: four runs,70 cases each,21 diagnostic children each,operation census,settings,counters,checksums')
else:
 (P/'summary.json').write_text(text)
 d=summary['runs']['diagnostic'];print(json.dumps({k:v for k,v in d.items() if k!='children'},indent=2))
