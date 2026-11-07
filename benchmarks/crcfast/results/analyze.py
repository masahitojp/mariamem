from pathlib import Path
import json,gzip,hashlib,statistics,sys
from stage_core import stats

def reduce(p):
 rs=json.loads((p/'records.json').read_text());obs=json.loads(gzip.decompress((p/'observations.json.gz').read_bytes()));owners=json.loads((p/'owner-summary.json').read_text());ti=json.loads(gzip.decompress((p/'timing-index.json.gz').read_bytes()))
 assert len(rs)==26 and len({r['name'] for r in rs})==26
 assert {k:sum(r['kind']==k for r in rs) for k in ['pilot','negative','warmup','primary','diagnostic']}==dict(pilot=4,negative=4,warmup=4,primary=12,diagnostic=2)
 seen=set();children=[];processes=[];tails=[];total=0
 for r in rs:
  report=obs[r['report']];negative=r['kind']=='negative';assert r['arm'] in ['software','fast'] and r['parallel']==1
  key=(r['mode'],r['arm'],r['observer'],r['rep'],r['kind']);assert key not in seen;seen.add(key)
  assert r['observer']==('on' if r['kind']=='diagnostic' else 'off')
  assert report['mode']==r['mode'] and report['prepare_baseline'] and report['fixed_waves'] and report['parallel']==1 and report['gomaxprocs']==8
  assert report['cleanup'] and report['resolved_max_forks']==1 and report['max_active']==1
  assert all(report['cleanup_stats'][k]==0 for k in ['active_mappings','active_rw_bytes','active_reserved_bytes','release_failures','grow_failures'])
  assert report['image_after_close']['closed'] and report['image_after_close']['owned_fds']==0
  assert report['image_before_close']['page_only'] and report['image_before_close']['enabled'] and report['image_before_close']['builds']==1 and report['image_before_close']['acquires']==len(report['samples'])+1
  if negative:assert r['exit_code']==1 and not report['success'] and 'pristine oracle' in report['error']
  else:assert r['exit_code']==0 and report['success'] and all(s['oracle'] and s['cleanup'] and not s.get('error') for s in report['samples'])
  assert len(report['samples'])==r['count'] and sorted(s['index'] for s in report['samples'])==list(range(r['count']))
  o=next(x for x in owners if x['name']==r['name']);assert not o['truncated'] and o['child_indices']==list(range(r['count']))
  total+=r['count'];end=0;metrics=[]
  for sample,w in zip(report['samples'],report['waves']):
   assert w['index']==sample['index'];sp={v['name']:v for v in sample['spans']};assert len(sp)==len(sample['spans'])
   assert end<=w['begin_ms']<=w['forks_begin_ms']<=sp['start_or_fork']['begin_ms']<=sp['start_or_fork']['end_ms']<=w['all_ready_ms']<=sp['connect']['begin_ms']<=sample['end_ms']<=w['end_ms'];end=w['end_ms']
   assert ('seed' in sp)==(r['mode']=='fresh') and sample['cleanup']
   d={k:v['end_ms']-v['begin_ms'] for k,v in sp.items()};assert all(v>=0 for v in d.values())
   assert 'fork_cpu_ms' in sample and sample['fork_cpu_ms']>=0;d['fork_cpu']=sample['fork_cpu_ms']
   for k,v in d.items():
    if k!='fork_cpu' and v>100:tails.append(dict(run=r['name'],child=sample['index'],stage=k,ms=v))
   if not negative:d['same_state']=sp['count_sum']['end_ms']-sp['start_or_fork']['begin_ms']
   if r['observer']=='on':
    tr=sample['traces'];assert set(tr)=={'fork','api_startup','startup'}
    h=hashlib.sha256(json.dumps(tr['startup'],sort_keys=True,separators=(',',':')).encode()).hexdigest();assert h in {v['canonical_sha256'] for v in ti[r['name']].values()}
    ev=tr['startup']['events'];costs=[json.loads(x['name'].split('innodb/rseg_cost/',1)[1]) for x in ev if x['name'].startswith('innodb/rseg_cost/')];assert len(costs)==1;c=costs[0];hp=c['header_path'];v=hp['validation']
    assert c['complete'] and c['registered']==c['scan_calls']==128 and c['slots']==131072 and c['null_slots']+c['undo_calls']==c['slots']
    assert c['scan_inclusive_ns']==c['scan_ns']+c['undo_ns']
    assert hp['calls']==hp['misses']==hp['lookups']==128 and hp['hits']==0 and hp['incomplete']==0
    assert hp['read_nested_calls'][:3]==[128,128,128] and sum(hp['read_nested_ns'])<=hp['phase_ns'][1]
    assert sum(hp['phase_ns'])+hp['other_ns']==hp['total_ns']<=c['page_ns'][2]
    assert v['calls']==v['recovery_flag']==v['crc_calls']==128 and v['counts']==[128,128] and v['crc_bytes']==2096640 and v['incomplete']==0
    assert all(type(n)==int and n>=0 for n in v['ns']+[v['crc_ns']]) and v['crc_ns']<=v['ns'][0] and sum(v['ns'])<=hp['read_nested_ns'][2]
    for k,n in [('crc',v['crc_ns']),('validation_other',v['ns'][0]-v['crc_ns']),('recovery',v['ns'][1]),('completion_other',hp['read_nested_ns'][2]-sum(v['ns'])),('read_complete',hp['read_nested_ns'][2]),('header',c['page_ns'][2])]:d['diag.'+k]=n/1e6
    assert abs(d['diag.read_complete']-sum(d['diag.'+k] for k in ['crc','validation_other','recovery','completion_other']))<1e-6
   else:assert not sample.get('traces')
   metrics.append(d);children.append(dict(run=r['name'],child=sample['index'],ms=d))
  assert len(report['waves'])==r['count']
  processes.append(dict(name=r['name'],mode=r['mode'],arm=r['arm'],kind=r['kind'],rep=r['rep'],metrics={k:stats([x[k] for x in metrics]) for k in sorted(set.intersection(*(set(x) for x in metrics)))},**{k:report[k] for k in ['suite_ms','batch_ms','suite_cpu_ms','batch_cpu_ms','lifetime_max_rss_bytes']}))
 assert total==884
 expected={(m,a,'off',rep,'primary') for m in ['fresh','fork'] for a in ['software','fast'] for rep in range(3)};assert expected=={x for x in seen if x[-1]=='primary'}
 pairs=[]
 for m in ['fresh','fork']:
  for rep in range(3):
   old=next(x for x in processes if x['mode']==m and x['arm']=='software' and x['kind']=='primary' and x['rep']==rep);new=next(x for x in processes if x['mode']==m and x['arm']=='fast' and x['kind']=='primary' and x['rep']==rep)
   pairs.append(dict(mode=m,rep=rep,software=old['name'],fast=new['name'],delta_ms={k:new[k]-old[k] for k in ['suite_ms','batch_ms','suite_cpu_ms','batch_cpu_ms']},delta_child_p50={k:new['metrics'][k]['p50']-old['metrics'][k]['p50'] for k in old['metrics']}))
 improvements=[-x['delta_child_p50']['start_or_fork'] for x in pairs if x['mode']=='fork'];passed=min(improvements)>0 and statistics.median(improvements)>=1
 return dict(source_commit=json.loads((p/'inputs.json').read_text())['source_commit'],processes=processes,children=children,pairs=pairs,tails=tails,total_children=total,criterion='all 3 Fork API p50 pairs improve; median >=1ms; correctness PASS; all cost/regression metrics reported',result='CONTINUE_CANDIDATE' if passed else 'NO_CLEAR_BENEFIT',median_fork_p50_improvement_ms=statistics.median(improvements))
if __name__=='__main__':
 p=Path(sys.argv[1]);out=reduce(p)
 if '--check' in sys.argv:assert out==json.loads((p/'summary.json').read_text());print('PASS retained-only: 26 processes /884 children, state/cleanup/owners/timing and paired comparisons')
 else:(p/'summary.json').write_text(json.dumps(out,indent=2)+'\n');print(out['result'],out['median_fork_p50_improvement_ms'])
