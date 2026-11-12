"""Replay compact diagnostic census without deleted raw journals or network."""
from pathlib import Path
import collections,hashlib,json,math,sys
D=Path(__file__).resolve().parent/'results'
def quantile(hist,p):
 total=sum(n for _,n in hist);target=max(1,math.ceil(total*p));c=0
 for v,n in hist:
  c+=n
  if c>=target:return v
 raise AssertionError('empty histogram')
def summarize():
 rows=json.loads((D/'observations.json').read_text());assert len(rows)==9 and rows[0]['control']
 natural=rows[1:];assert [r['name'] for r in natural]==[f'natural-{i}' for i in range(1,9)]
 for r in rows:
  assert r['cases']==70 and r['closed_observers']==22 and r['active_mappings_after']==0 and r['scratch_empty']
  assert r['observed_caps']==[16] and r['phase_counts']['prepare']==63
  assert sum(n for _,n in r['global_us_histogram'])==r['read_requests']*2==r['request_stage_bindings']
  for h in ['global_us_histogram','group_us_histogram']:
   assert all(v>=0 and n>0 for v,n in r[h])
  e=r['event_counts'];assert e['spawn_call']==e['worker_enter']==e['pending_clear']==e['worker_exit']==len(r['spawn_intervals_us'])
  assert e.get('spawn_failure_clear',0)==0 and e.get('add_max',0)==0 and e.get('add_throttle',0)==0
  assert e['wait_begin_applied']==e['wait_end_applied']
  assert all(len(v)==3 and min(v)>=0 for v in r['spawn_intervals_us'])
 h=collections.Counter();spawn=[];actors=collections.Counter()
 for r in natural:
  h.update(dict(r['global_us_histogram']));spawn+=r['spawn_intervals_us'];actors.update(r['spawn_actors'])
 gh=sorted(h.items());eh=sorted(collections.Counter(x[0] for x in spawn).items());ih=sorted(collections.Counter(x[1] for x in spawn).items());ch=sorted(collections.Counter(x[2] for x in spawn).items())
 return {'result':'NOT_REPRODUCED_FOREGROUND_TAIL','valid_processes':9,'sql_cases':630,'natural_batches':8,'natural_prepares':sum(r['phase_counts']['prepare'] for r in natural),'natural_prepare_ge100ms':sum(r['phase_ge100ms']['prepare'] for r in natural),'natural_read_requests':sum(r['read_requests'] for r in natural),'queue_stage_samples':sum(h.values()),'global_us':{'p50':quantile(gh,.5),'p95':quantile(gh,.95),'p99':quantile(gh,.99),'max':gh[-1][0],'ge100ms':sum(n for v,n in gh if v>=100000)},'pending_rejections':sum(r['event_counts'].get('add_pending',0) for r in natural),'outer_rejections':sum(r['outer_reject_count'] for r in natural),'created_workers':len(spawn),'spawn_actors':dict(actors),'spawn_call_to_worker_enter_us':{'p50':quantile(eh,.5),'p95':quantile(eh,.95),'max':eh[-1][0]},'worker_enter_to_init_return_us':{'p50':quantile(ih,.5),'p95':quantile(ih,.95),'max':ih[-1][0]},'spawn_call_to_pending_clear_us':{'p50':quantile(ch,.5),'p95':quantile(ch,.95),'max':ch[-1][0]},'limits':'Diagnostic counts are correlated; no incidence/performance comparison or proof that a missing maintenance cycle caused prior tails. Histograms cannot reconstruct the discarded whole request timeline.'}
if __name__=='__main__':
 rendered=json.dumps(summarize(),indent=2)+'\n'
 if sys.argv[1:]==['--check']:
  assert (D/'summary.json').read_text()==rendered
  for f,h in json.loads((D/'SHA256SUMS.json').read_text()).items():assert hashlib.sha256((D/f).read_bytes()).hexdigest()==h
  print('PASS: compact census/quantiles/checksums; natural foreground tail NOT_REPRODUCED')
 elif not sys.argv[1:]:print(rendered,end='')
 else:raise SystemExit('usage: analyze.py [--check]')
