"""Replay matched Fresh/Fork observations without build/temp dependencies."""
from pathlib import Path
import json,gzip,statistics,sys,hashlib
from stage_core import child,stats
from init_core import decompose

def reduce(p):
 rs=json.loads((p/'records.json').read_text());obs=json.loads(gzip.decompress((p/'observations.json.gz').read_bytes()));owners=json.loads((p/'owner-summary.json').read_text());timings=json.loads(gzip.decompress((p/'timing-index.json.gz').read_bytes()))
 assert len(rs)==12 and len({r['name'] for r in rs})==12
 assert {k:sum(r['kind']==k for r in rs) for k in ['pilot','negative','warmup','primary']}=={'pilot':2,'negative':2,'warmup':2,'primary':6}
 processes=[];children=[];tails=[];total=0;wavecount=0;owner_count=0
 expected={(P,m,o,rep) for P in [1] for m in ['fresh','fork'] for o in ['on'] for rep in range(3)};seen=set()
 for rec in rs:
  r=obs[rec['report']];negative=rec['kind']=='negative';assert r['mode']==rec['mode'] and r['prepare_baseline'] and r['fixed_waves']
  assert r['cleanup'] and r['resolved_max_forks']==rec['parallel'] and r['max_active']==rec['parallel']
  assert all(r['cleanup_stats'][k]==0 for k in ['active_mappings','active_rw_bytes','active_reserved_bytes','release_failures','grow_failures'])
  assert r['image_after_close']['closed'] and r['image_after_close']['owned_fds']==0
  assert r['image_before_close']['page_only'] and r['image_before_close']['enabled'] and r['image_before_close']['builds']==1 and r['image_before_close']['acquires']==len(r['samples'])+1
  if negative:assert rec['exit_code']==1 and not r['success'] and 'pristine oracle' in r['error']
  else:assert rec['exit_code']==0 and r['success'] and len(r['samples'])==rec['count'] and all(s['oracle'] and s['cleanup'] and not s.get('error') for s in r['samples'])
  assert sorted(s['index'] for s in r['samples'])==list(range(len(r['samples'])))
  total+=len(r['samples']);end=0
  for w in r['waves']:
   ss=[s for s in r['samples'] if s['index']//r['parallel']==w['index']];assert len(ss)==r['parallel']
   assert end<=w['begin_ms']<=w['forks_begin_ms']<=w['all_ready_ms']<=w['end_ms'];end=w['end_ms'];wavecount+=1
   for s in ss:
    z={v['name']:v for v in s['spans']};assert len(z)==len(s['spans']) and s['cleanup']
    assert w['forks_begin_ms']<=z['start_or_fork']['begin_ms']<=z['start_or_fork']['end_ms']<=w['all_ready_ms']<=z['connect']['begin_ms'] and s['end_ms']<=w['end_ms']
    assert ('seed' in z)==(r['mode']=='fresh')
  if rec['observer']=='on':
   o=next(o for o in owners if o['name']==rec['name']);assert o['truncated']==0 and o['child_indices']==list(range(rec['count']));owner_count+=rec['count']
  dd=[]
  for sample in r['samples']:
   sp={v['name']:v for v in sample['spans']};d={'api_startup':sp['start_or_fork']['end_ms']-sp['start_or_fork']['begin_ms']}
   if not negative:
    d['same_state']=sp['count_sum']['end_ms']-sp['start_or_fork']['begin_ms'];d['seed_sql']=sp['seed']['end_ms']-sp['seed']['begin_ms'] if r['mode']=='fresh' else 0
   for name,z in sp.items():
    elapsed=z['end_ms']-z['begin_ms']
    if elapsed>100:tails.append(dict(run=rec['name'],child=sample['index'],stage=name,ms=elapsed))
   if rec['observer']=='on':
    tr=sample['traces'];assert set(tr)==({'startup','api_startup','fork'} if r['mode']=='fork' else {'startup','api_startup'})
    assert hashlib.sha256(json.dumps(tr['startup'],sort_keys=True,separators=(',',':')).encode()).hexdigest() in {v['canonical_sha256'] for v in timings[rec['name']].values()}
    host=child(sample,'image');host['guest_post_server_to_routines_complete']=host.pop('guest_routine_schema');d.update({'host.'+k:v for k,v in host.items()})
    init=decompose(tr);d.update({'init.'+k:v for k,v in init.items()})
    events=tr['startup']['events'];names=[x['name'] for x in events]
    assert names.count('innodb/system_space_open_begin')==names.count('innodb/system_space_open_end')==1
    assert names.count('innodb/system_space_create_new')==int(rec['mode']=='fresh') and names.count('innodb/system_space_existing')==int(rec['mode']=='fork')
    es={x['name']:x['offset_ns']/1e6 for x in events}
    span=es['innodb/system_space_open_end']-es['innodb/system_space_open_begin'];outer=init['innodb_open_recovery']
    assert 0<=span<=outer,'open call escapes guest outer interval'
    d['system_space_open']=span;d['open_recovery_remainder']=outer-span
    assert abs(d['system_space_open']+d['open_recovery_remainder']-outer)<1e-6
    host_outer=es['innodb/outer_end']-es['innodb/outer_begin'];assert host_outer>0
    assert host_outer<=outer+.1,(host_outer,outer)
    components=['undo_tablespaces','dictionary_create','recovery','dictionary_boot','redo_apply','dictionary_load','transaction_lists']
    intervals=[(es['innodb/outer_begin'],es['innodb/system_space_open_begin'],'pre_space'),(es['innodb/system_space_open_begin'],es['innodb/system_space_open_end'],'system_space_open')]
    d['pre_space']=intervals[0][1]-intervals[0][0]
    for key in components:
     present=key in (['undo_tablespaces','dictionary_create'] if rec['mode']=='fresh' else ['undo_tablespaces','recovery','dictionary_boot','redo_apply','dictionary_load','transaction_lists'])
     for suffix in ['_begin','_end']:assert names.count('innodb/'+key+suffix)==int(present),(key,names)
     if present:
      aa,bb=[es['innodb/'+key+v] for v in ['_begin','_end']];assert aa<=bb;intervals.append((aa,bb,key));d[key]=bb-aa
     else:d[key]=0
    intervals.sort()
    for i,(aa,bb,key) in enumerate(intervals):
     assert es['innodb/outer_begin']<=aa<=bb<=es['innodb/outer_end'],(key,intervals)
     if i:assert intervals[i-1][1]<=aa,('overlap',intervals)
    d['host_open_recovery']=host_outer
    d['other_open_recovery']=host_outer-sum(bb-aa for aa,bb,_ in intervals);assert d['other_open_recovery']>=0
    assert abs(host_outer-sum(d[k] for k in ['pre_space','system_space_open']+components+['other_open_recovery']))<1e-6
    txn_start=es.get('innodb/transaction_lists_begin',es['innodb/outer_begin']);txn_end=es.get('innodb/transaction_lists_end',es['innodb/outer_end'])
    txn_intervals=[]
    for k in ['purge_create','rseg_array']:
     for suffix in ['_begin','_end']:assert names.count('innodb/'+k+suffix)==1
     aa,bb=[es['innodb/'+k+suffix] for suffix in ['_begin','_end']];assert txn_start<=aa<=bb<=txn_end;txn_intervals.append((aa,bb));d[k]=bb-aa
    assert txn_intervals[0][1]<=txn_intervals[1][0]
    branches=[n for n in names if n in ['innodb/undo_empty','innodb/undo_nonempty']];assert len(branches)==1
    assert txn_intervals[1][1]<=es[branches[0]]<=txn_end
    d['undo_nonempty_branch']=int(branches==['innodb/undo_nonempty'])
    d['undo_empty_branch']=int(branches==['innodb/undo_empty'])
    d['transaction_lists_other']=0;d['fresh_setup_other']=0
    if rec['mode']=='fork':
     d['transaction_lists_other']=d['transaction_lists']-d['purge_create']-d['rseg_array'];assert d['transaction_lists_other']>=0
    else:
     # These Fresh calls were previously part of unmeasured creation/setup.
     # Verify containment and subtract them from that residual, not from the
     # absent Fork-only enclosing marker pair.
     for aa,bb in txn_intervals:
      assert all(bb<=x or y<=aa for x,y,_ in intervals[1:]),('Fresh split overlaps existing component',aa,bb,intervals)
     d['fresh_setup_other']=d['other_open_recovery']-d['purge_create']-d['rseg_array'];assert d['fresh_setup_other']>=0

    cost_events=[x for x in events if x['name'].startswith('innodb/rseg_cost/')]
    assert len(cost_events)==1,'missing/duplicate rseg cost'
    event=cost_events[0];cost=json.loads(event['name'].split('innodb/rseg_cost/',1)[1])
    assert es['innodb/rseg_array_begin']<=event['offset_ns']/1e6<=es['innodb/rseg_array_end']
    assert cost['complete'] and cost['registered']==cost['scan_calls']
    assert cost['registered']==(1 if rec['mode']=='fresh' else 128),cost
    assert cost['page_size'] in [4096,8192,16384,32768,65536]
    assert cost['slots']==cost['registered']*(cost['page_size']//16)
    assert cost['null_slots']+cost['undo_calls']==cost['slots']
    assert cost['page_calls'][:3]==[128,cost['registered'],cost['registered']]
    assert len(cost['page_ns'])==len(cost['page_calls'])==4
    nums=cost['page_ns']+cost['page_calls']+[cost[k] for k in ['undo_ns','undo_calls','scan_ns','scan_inclusive_ns','scan_calls','slots','null_slots','registered','page_size']]
    assert all(type(v)==int and v>=0 for v in nums)
    assert cost['scan_inclusive_ns']==cost['scan_ns']+cost['undo_ns']
    for i,name in enumerate(['trx_sys','space_header','rseg_header','history_page']):
     d['rseg.page.'+name]=cost['page_ns'][i]/1e6
     d['count.page.'+name]=cost['page_calls'][i]
    d['rseg.page_total']=sum(cost['page_ns'])/1e6
    d['rseg.scan_exclusive']=cost['scan_ns']/1e6
    d['rseg.scan_inclusive']=cost['scan_inclusive_ns']/1e6
    d['rseg.undo_restore']=cost['undo_ns']/1e6
    d['rseg.residual']=d['rseg_array']-d['rseg.page_total']-d['rseg.scan_exclusive']-d['rseg.undo_restore']
    assert d['rseg.residual']>=0
    assert abs(d['rseg_array']-sum(d[k] for k in ['rseg.page_total','rseg.scan_exclusive','rseg.undo_restore','rseg.residual']))<1e-6
    hp=cost['header_path'];assert hp['calls']==cost['registered'] and hp['incomplete']==0
    assert len(hp['phase_ns'])==len(hp['phase_calls'])==len(hp['read_nested_ns'])==len(hp['read_nested_calls'])==4
    numbers=hp['phase_ns']+hp['phase_calls']+hp['read_nested_ns']+hp['read_nested_calls']+[hp[k] for k in ['calls','lookups','hits','misses','total_ns','other_ns','incomplete']]
    assert all(type(v)==int and v>=0 for v in numbers)
    assert hp['lookups']==hp['hits']+hp['misses']==hp['phase_calls'][0]
    assert hp['phase_calls'][1]==hp['misses'] and hp['phase_calls'][2]==hp['misses']
    assert sum(hp['phase_ns'])+hp['other_ns']==hp['total_ns']
    assert hp['total_ns']<=cost['page_ns'][2]
    assert sum(hp['read_nested_ns'])<=hp['phase_ns'][1]
    assert hp['read_nested_calls'][0]==hp['misses']
    assert hp['read_nested_calls'][2]<=hp['read_nested_calls'][1]<=hp['misses']
    for i,k in enumerate(['lookup','sync_read_miss','random_read_ahead','read_wait']):
     d['header.'+k]=hp['phase_ns'][i]/1e6;d['count.header.'+k]=hp['phase_calls'][i]
    d['header.other']=hp['other_ns']/1e6
    d['header.wrapper']=d['rseg.page.rseg_header']-hp['total_ns']/1e6
    for i,k in enumerate(['frame_init','sync_io_request','read_complete','race_read_wait']):
     d['header.read.'+k]=hp['read_nested_ns'][i]/1e6;d['count.header.read.'+k]=hp['read_nested_calls'][i]
    val=hp['validation'];assert val['calls']==hp['read_nested_calls'][2] and val['incomplete']==0
    assert len(val['ns'])==len(val['counts'])==2
    assert all(type(n)==int and n>=0 for n in val['ns']+val['counts']+[val[k] for k in ['calls','recovery_flag','crc_ns','crc_calls','crc_bytes','incomplete']])
    assert val['recovery_flag']<=val['calls'] and val['counts'][1]<=val['recovery_flag']
    assert val['crc_calls']<=val['counts'][0] and val['crc_ns']<=val['ns'][0]
    assert val['crc_bytes']<=val['crc_calls']*cost['page_size']
    assert (val['crc_bytes']==0)==(val['crc_calls']==0)
    assert sum(val['ns'])<=hp['read_nested_ns'][2]
    for i,k in enumerate(['validation','recovery']):
     d['complete.'+k]=val['ns'][i]/1e6;d['count.complete.'+k]=val['counts'][i]
    d['complete.crc']=val['crc_ns']/1e6
    d['complete.validation_other']=(val['ns'][0]-val['crc_ns'])/1e6
    d['complete.other']=(hp['read_nested_ns'][2]-sum(val['ns']))/1e6
    for k in ['calls','recovery_flag','crc_calls','crc_bytes']:d['count.complete.'+k]=val[k]
    d['count.complete.clock_reads']=2*(sum(val['counts'])+val['crc_calls'])
    assert abs(d['header.read.read_complete']-sum(d['complete.'+k] for k in ['crc','validation_other','recovery','other']))<1e-6
    d['header.read.other']=(hp['phase_ns'][1]-sum(hp['read_nested_ns']))/1e6
    assert abs(d['rseg.page.rseg_header']-sum(d['header.'+k] for k in ['lookup','sync_read_miss','random_read_ahead','read_wait','other','wrapper']))<1e-6
    for k in ['calls','lookups','hits','misses']:d['count.header.'+k]=hp[k]
    d['count.header.clock_reads']=2*(hp['calls']+sum(hp['phase_calls'])+sum(hp['read_nested_calls']))
    for k in ['undo_calls','scan_calls','slots','null_slots','registered','page_size']:d['count.'+k]=cost[k]
    d['count.clock_reads']=2*(sum(cost['page_calls'])+cost['scan_calls']+cost['undo_calls'])
    d['ratio.null_slots']=cost['null_slots']/cost['slots']
    assert abs(init['server_init']-sum(init[k] for k in ['common','components_before_plugins','plugins','components_after_plugins','server_other']))<1e-6
    g={x['name']:x['offset_ns']/1e6 for x in tr['startup']['guest']['events']}
    for label,a,b in [('guest_restore','restore_begin','restore_complete'),('internal_bootstrap','server_init_complete','bootstrap_complete'),('routine_schema','routine_schema_begin','routine_schema_complete')]:d[label]=g[b]-g[a]
    children.append(dict(run=rec['name'],child=sample['index'],ms=d))
   else:assert not sample.get('traces')
   dd.append(d)
  if rec['kind']=='primary':
   key=(rec['parallel'],rec['mode'],rec['observer'],rec['rep']);assert key in expected and key not in seen;seen.add(key)
   processes.append(dict(name=rec['name'],parallel=rec['parallel'],mode=rec['mode'],observer=rec['observer'],rep=rec['rep'],metrics={k:stats([x[k] for x in dd]) for k in dd[0]},suite_ms=r['suite_ms'],batch_ms=r['batch_ms'],suite_cpu_ms=r['suite_cpu_ms'],setup_spans=r['root_spans']))
 assert seen==expected and total==394 and owner_count==394
 cells=[];comparisons=[];observer_effect=[]
 for P in [1]:
  for o in ['on']:
   for m in ['fresh','fork']:
    rows=[r for r in processes if r['parallel']==P and r['observer']==o and r['mode']==m];assert len(rows)==3
    cells.append(dict(parallel=P,observer=o,mode=m,metrics={k:dict(mean=statistics.mean(v['metrics'][k]['mean'] for v in rows),median_process_p50=statistics.median(v['metrics'][k]['p50'] for v in rows),median_process_p95=statistics.median(v['metrics'][k]['p95'] for v in rows),over_100ms=sum(v['metrics'][k]['over_100ms'] for v in rows)) for k in rows[0]['metrics']}))
   for rep in range(3):
    a=next(r for r in processes if (r['parallel'],r['observer'],r['mode'],r['rep'])==(P,o,'fresh',rep));b=next(r for r in processes if (r['parallel'],r['observer'],r['mode'],r['rep'])==(P,o,'fork',rep))
    comparisons.append(dict(parallel=P,observer=o,rep=rep,fork_minus_fresh_mean_ms={k:b['metrics'][k]['mean']-a['metrics'][k]['mean'] for k in a['metrics']},fork_minus_fresh_p50_ms={k:b['metrics'][k]['p50']-a['metrics'][k]['p50'] for k in a['metrics']}))

 return dict(source_commit=json.loads((p/'inputs.json').read_text())['source_commit'],processes=processes,cells=cells,comparisons=comparisons,observer_effect=observer_effect,tails=tails,children=children,total_children=total,owner_children=owner_count,waves=wavecount,scope='P1 rseg read completion: validation incl. full_crc32, conditional recovery and residual; diagnostic only')
if __name__=='__main__':
 p=Path(sys.argv[1]);out=reduce(p)
 if '--check' in sys.argv:assert out==json.loads((p/'summary.json').read_text());print('PASS: matched state, 394 children, 394 owners, all phases/waves and cleanup')
 else:(p/'summary.json').write_text(json.dumps(out,indent=2)+'\n')
