from pathlib import Path
import json,gzip,hashlib,statistics,sys
from stage_core import stats,child
from init_core import decompose

def reduce(p):
 rs=json.loads((p/'records.json').read_text());obs=json.loads(gzip.decompress((p/'observations.json.gz').read_bytes()));owners=json.loads((p/'owner-summary.json').read_text());ti=json.loads(gzip.decompress((p/'timing-index.json.gz').read_bytes()))
 assert len(rs)==18 and len({r['name'] for r in rs})==18
 assert {k:sum(r['kind']==k for r in rs) for k in ['pilot','negative','warmup','primary','diagnostic','positive']}==dict(pilot=2,negative=2,warmup=2,primary=8,diagnostic=2,positive=2)
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
  crc=report['crc'];keys=['validator_calls','crc_calls','fast_calls','crc_bytes']
  assert set(crc)==set(keys+['fast_enabled']) and all(type(n)==int and n>=0 for n in crc.values())
  assert crc['fast_enabled']==int(r['arm']=='fast') and crc['fast_calls']==crc['crc_calls']*crc['fast_enabled'] and crc['crc_calls']<=crc['validator_calls']
  assert crc['crc_calls']>0 or crc['crc_bytes']==0
  assert [x['child'] for x in o['crc_children']]==list(range(r['count']))
  for cc in o['crc_children']:
   assert all(type(cc[k])==int and cc[k]>=0 for k in keys)
   assert cc['fast_calls']==cc['crc_calls']*crc['fast_enabled'] and cc['crc_calls']<=cc['validator_calls']
   assert cc['crc_calls']>0 or cc['crc_bytes']==0
   if r['kind']=='positive':assert cc['crc_calls']>=128
  unbound={k:crc[k]-sum(cc[k] for cc in o['crc_children']) for k in keys};assert min(unbound.values())>=0
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
    tr=sample['traces'];assert set(tr)=={'api_startup','startup'}
    h=hashlib.sha256(json.dumps(tr['startup'],sort_keys=True,separators=(',',':')).encode()).hexdigest();assert h in {v['canonical_sha256'] for v in ti[r['name']].values()}
    host=child(sample,'image');d.update({'host.'+k:v for k,v in host.items()});init=decompose(tr);d.update({'init.'+k:v for k,v in init.items()})
    ev=tr['startup']['events'];costs=[json.loads(x['name'].split('innodb/rseg_cost/',1)[1]) for x in ev if x['name'].startswith('innodb/rseg_cost/')];assert len(costs)==1;c=costs[0];hp=c['header_path'];val=hp['validation']
    assert c['complete'] and c['registered']==c['scan_calls']==1 and c['slots']==1024 and c['null_slots']+c['undo_calls']==c['slots']
    assert hp['calls']==hp['lookups']==hp['hits']==1 and hp['misses']==0 and hp['incomplete']==0
    assert val['calls']==val['crc_calls']==0 and val['ns']==[0,0] and val['crc_ns']==0 and val['incomplete']==0
    assert abs(init['server_init']-sum(init[k] for k in ['common','components_before_plugins','plugins','components_after_plugins','server_other']))<1e-6
   else:assert not sample.get('traces')
   metrics.append(d);children.append(dict(run=r['name'],child=sample['index'],ms=d))
  assert len(report['waves'])==r['count']
  processes.append(dict(name=r['name'],mode=r['mode'],arm=r['arm'],kind=r['kind'],rep=r['rep'],metrics={k:stats([x[k] for x in metrics]) for k in sorted(set.intersection(*(set(x) for x in metrics)))},crc=crc,unbound_crc=unbound,**{k:report[k] for k in ['suite_ms','batch_ms','suite_cpu_ms','batch_cpu_ms','lifetime_max_rss_bytes']}))
 assert total==594
 plan=json.loads((p/'plan.json').read_text());primary=[x for x in processes if x['kind']=='primary']
 assert len(primary)==8 and [x['arm'] for x in primary]==plan['primary_order'] and [x['rep'] for x in primary]==list(range(8))
 assert all(x['mode']=='fresh' for x in primary)
 pairs=[]
 for i,(oldidx,newidx) in enumerate(plan['primary_pairs']):
  old,new=primary[oldidx],primary[newidx];assert old['arm']=='software' and new['arm']=='fast'
  pairs.append(dict(pair=i,software=old['name'],fast=new['name'],software_first=oldidx<newidx,delta_ms={k:new[k]-old[k] for k in ['suite_ms','batch_ms','suite_cpu_ms','batch_cpu_ms']},delta_child_p50={k:new['metrics'][k]['p50']-old['metrics'][k]['p50'] for k in old['metrics']},delta_child_mean={k:new['metrics'][k]['mean']-old['metrics'][k]['mean'] for k in old['metrics']}))
 deltas=[x['delta_child_p50']['start_or_fork'] for x in pairs];replicated=sum(x>=.25 for x in deltas)>=3 and statistics.median(deltas)>=.25
 fresh=[x for x in processes if x['mode']=='fresh'];unused=all(x['crc']['crc_calls']==0 for x in fresh)
 return dict(source_commit=json.loads((p/'inputs.json').read_text())['source_commit'],processes=processes,children=children,pairs=pairs,tails=tails,total_children=total,criterion=plan['criteria'],fresh_slowdown_replicated=replicated,selected_crc_unused_entire_fresh_process=unused,median_fresh_p50_delta_ms=statistics.median(deltas),result='DIRECT_CRC_COST_EXCLUDED' if unused else 'CRC_EXECUTED_FURTHER_ATTRIBUTION_REQUIRED')
if __name__=='__main__':
 p=Path(sys.argv[1]);out=reduce(p)
 if '--check' in sys.argv:assert out==json.loads((p/'summary.json').read_text());print('PASS retained-only: 18 processes /594 children, state/cleanup/owners/timing and paired comparisons')
 else:(p/'summary.json').write_text(json.dumps(out,indent=2)+'\n');print(out['result'],out['median_fresh_p50_delta_ms'])
