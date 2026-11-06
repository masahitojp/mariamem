"""Read-only retained-data replay of the fixed P4 schedule."""
from pathlib import Path
import gzip,json,statistics,sys,math
from stage_core import child

def stats(xs):
 s=sorted(xs);return dict(p50=statistics.median(s),p95=s[math.ceil(.95*len(s))-1],mean=statistics.mean(s),max=max(s),n=len(s),over100=sum(v>100 for v in s))
def reduce(p):
 records=json.loads((p/'records.json').read_text());obs=json.loads(gzip.decompress((p/'observations.json.gz').read_bytes()));owners=json.loads((p/'owner-summary.json').read_text());timings=json.loads(gzip.decompress((p/'timings.json.gz').read_bytes()))
 assert len(records)==18 and len({r['name'] for r in records})==18
 kinds={'pilot':2,'negative':2,'warmup':2,'primary':10,'diagnostic':2};assert {k:sum(r['kind']==k for r in records) for k in kinds}==kinds
 rows=[];tails=[];diagnostic=[];child_count=0
 for rec in records:
  r=obs[rec['report']];negative=rec['kind']=='negative';assert r['fixed_waves'] and r['parallel']==4 and r['resolved_max_forks']==4
  assert r['cleanup'] and all(r['cleanup_stats'][k]==0 for k in ['active_mappings','active_rw_bytes','active_reserved_bytes','release_failures'])
  assert r['image_after_close']['closed'] and r['image_after_close']['owned_fds']==0
  candidate=rec['arm']=='pages';assert r['image_before_close']['page_only']==candidate and r['image_before_close']['enabled']==candidate
  assert r['image_before_close']['builds']==int(candidate)
  if candidate:
   assert r['image_before_close']['initialized_page_bytes']==8863744 and len(r['image_before_close']['image_ranges'])==22
   assert r['image_before_close']['acquires']==len(r['samples'])+1
  if negative:assert rec['exit_code']==1 and not r['success'] and 'pristine oracle' in r['error']
  else:
   assert rec['exit_code']==0 and r['success'] and len(r['samples'])==rec['count']
   assert all(s['oracle'] and s['cleanup'] and not s.get('error') for s in r['samples'])
  child_count+=len(r['samples']);assert sorted(s['index'] for s in r['samples'])==list(range(len(r['samples'])))
  assert len(r['samples'])==4*len(r['waves']);end=0;forks=[];wave_ready=[];wave_cpu=[];skews=[];window=[]
  for w in r['waves']:
   ss=[s for s in r['samples'] if s['index']//4==w['index']];assert len(ss)==4
   assert end<=w['begin_ms']<=w['forks_begin_ms']<=w['all_ready_ms']<=w['end_ms'];end=w['end_ms']
   starts=[];ends=[]
   for s in ss:
    z={x['name']:x for x in s['spans']};assert len(z)==len(s['spans'])
    assert w['forks_begin_ms']<=z['start_or_fork']['begin_ms']<=z['start_or_fork']['end_ms']<=w['all_ready_ms']
    assert z['wave_start_wait']['end_ms']<=z['start_or_fork']['begin_ms']
    assert z['wave_ready_wait']['begin_ms']>=z['start_or_fork']['end_ms'] and z['wave_ready_wait']['end_ms']>=w['all_ready_ms']
    assert z['connect']['begin_ms']>=w['all_ready_ms'] and s['end_ms']<=w['end_ms']
    assert s['cleanup'] and z['close']['end_ms']<=w['end_ms']
    starts.append(z['start_or_fork']['begin_ms']);ends.append(z['start_or_fork']['end_ms']);forks.append(ends[-1]-starts[-1])
    for name,span in z.items():
     ms=span['end_ms']-span['begin_ms']
     if ms>100:tails.append(dict(run=rec['name'],child=s['index'],stage=name,ms=ms))
   wave_ready.append(w['all_ready_ms']-w['forks_begin_ms']);wave_cpu.append(w['fork_cpu_ms']);skews.append(max(starts)-min(starts));window.append(max(ends)-min(starts))
  rows.append(dict(name=rec['name'],arm=rec['arm'],rep=rec['rep'],kind=rec['kind'],fork=stats(forks),wave_ready=stats(wave_ready),wave_cpu=stats(wave_cpu),start_skew=stats(skews),fork_window=stats(window),batch_ms=r['batch_ms'],suite_ms=r['suite_ms'],suite_cpu_ms=r['suite_cpu_ms']))
  if rec['kind']=='diagnostic':
   o=next(x for x in owners if x['name']==rec['name']);assert o['child_indices']==list(range(48)) and o['truncated']==0
   assert all(s['traces']['startup'] in timings[rec['name']].values() for s in r['samples'])
   ds=[child(s,'image' if candidate else 'anonymous') for s in r['samples']]
   diagnostic.append(dict(name=rec['name'],arm=rec['arm'],metrics={k:stats([d[k] for d in ds]) for k in ds[0]},children=ds))
 sql_tail_overlaps=[]
 for rec in records:
  r=obs[rec['report']];forks=[next(z for z in s['spans'] if z['name']=='start_or_fork') for s in r['samples']]
  for s in r['samples']:
   for z in s['spans']:
    if z['name'] in ['count_sum','update'] and z['end_ms']-z['begin_ms']>100:
     n=sum(max(z['begin_ms'],f['begin_ms'])<min(z['end_ms'],f['end_ms']) for f in forks)
     assert n==0,'SQL tail overlaps Fork'
     sql_tail_overlaps.append(dict(run=rec['name'],child=s['index'],stage=z['name'],overlapping_forks=n))
 assert child_count==688
 primary=[x for x in rows if x['kind']=='primary'];pairs=[]
 for rep in range(5):
  a=next(r for r in primary if r['arm']=='anonymous' and r['rep']==rep);b=next(r for r in primary if r['arm']=='pages' and r['rep']==rep)
  d={}
  for metric in ['fork','wave_ready','wave_cpu','start_skew','fork_window']:
   for stat in ['p50','p95','mean']:
    aa=a[metric][stat];bb=b[metric][stat];d[metric+'_'+stat]=dict(anonymous=aa,pages=bb,delta_ms=bb-aa,pct=100*(bb/aa-1))
  pairs.append(dict(rep=rep,metrics=d))
 summary={}
 for k in pairs[0]['metrics']:
  vals=[x['metrics'][k] for x in pairs]
  summary[k]=dict(anonymous=statistics.median(x['anonymous'] for x in vals),pages=statistics.median(x['pages'] for x in vals),paired_pct=[x['pct'] for x in vals],paired_median_pct=statistics.median(x['pct'] for x in vals),pairs_improve=sum(x['pages']<x['anonymous'] for x in vals))
 gates={k:summary[k]['paired_median_pct']<=-3 and summary[k]['pairs_improve']>=4 for k in ['fork_p50','wave_ready_p50']}
 cpu=summary['wave_cpu_p50'];gates['cpu_guard']=cpu['paired_median_pct']<=5 and sum(x>5 for x in cpu['paired_pct'])<4
 return dict(source_commit=json.loads((p/'inputs.json').read_text())['source_commit'],processes=rows,pairs=pairs,summary=summary,gates=gates,isolated_screen_pass=all(gates.values()),diagnostic=diagnostic,tails=tails,children=child_count,sql_tail_overlaps=sql_tail_overlaps,scope='P4 fixed-wave mechanism isolation; prior mixed full-suite screen remains unchanged')
if __name__=='__main__':
 p=Path(sys.argv[1]);out=reduce(p)
 if '--check' in sys.argv:assert out==json.loads((p/'summary.json').read_text());print('PASS: 18 processes, 688 children, wave contract, SQL/cleanup and 96 diagnostic partitions')
 else:(p/'summary.json').write_text(json.dumps(out,indent=2)+'\n')
