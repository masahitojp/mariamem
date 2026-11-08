"""Replay actual-C measurements; --check never overwrites evidence."""
from pathlib import Path
import argparse,csv,io,json,math,statistics,sys
S=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(S/'benchmarks/lexercandidate'))
from codec import read

def stats(v):
 s=sorted(v);assert s
 return dict(n=len(s),p50=statistics.median(s),p95=s[math.ceil(.95*len(s))-1],mean=statistics.mean(s),max=max(s),over_100ms=sum(x>100 for x in s))
def events(es):
 assert len({x['name'] for x in es})==len(es)
 assert all(a['offset_ns']<=b['offset_ns'] for a,b in zip(es,es[1:]))
 return {x['name']:x['offset_ns']/1e6 for x in es}
def stages(rec,sample):
 ts=rec['traces'][str(sample['index'])];h=events(ts['startup']['events']);g=events(ts['startup']['guest']['events'])
 spans={x['name']:x['end_ms']-x['begin_ms'] for x in sample['spans']};fork=spans['start_or_fork'];a=lambda x,y:h[y]-h[x];b=lambda x,y:g[y]-g[x]
 row={'host_outside_startup':fork-h['end']+h['runtime/instance_begin'],'filesystem_handles':a('runtime/instance_begin','runtime/prepared_handles_ready'),'memory_prepare':a('runtime/prepared_handles_ready','runtime/guest_execute_begin'),'server_init':b('server_init_begin','server_init_complete'),'bootstrap_connection':b('server_init_complete','routine_schema_begin'),'routine_schema':b('routine_schema_begin','routine_schema_complete'),'guest_other':b('guest_main','ready_prepared')-b('server_init_begin','server_init_complete')-b('server_init_complete','routine_schema_begin')-b('routine_schema_begin','routine_schema_complete'),'execution_residual':a('runtime/guest_execute_begin','ready_response_observed')-b('guest_main','ready_prepared'),'after_ready':a('ready_response_observed','end')}
 assert min(row.values())>=-.1,row
 assert abs(sum(row.values())-fork)<1e-6
 row.update(memory_reserve=a('runtime/reserve_begin','runtime/reserve_end'),memory_construct=a('runtime/construct_begin','runtime/construct_end'))
 return row

def reduce(records):
 assert len(records)==52
 expected={(mode,p,obs,arm,rep) for mode,p,obs in [('fresh',1,'off'),('fresh',4,'off'),('fork',1,'off'),('fork',4,'off'),('fork',1,'on'),('fork',4,'on')] for arm in ['baseline','candidate'] for rep in range(3)}
 seen=set();rows=[];primary=[]
 assert sum(r['kind']=='warmup' for r in records)==12
 assert sum(r['kind']=='control' for r in records)==2
 assert sum(r['negative'] for r in records)==2
 for rec in records:
  d=rec['report']
  assert d['mode']==rec['mode'] and d['parallel']==rec['parallel'] and d['gomaxprocs']==8 and d['go']=='go1.27.3'
  assert d['count']==(1 if rec['negative'] else 2 if rec['kind']=='control' else 48)
  if rec['mode']=='fork':assert d['resolved_max_forks']==rec['parallel']
  assert d['cleanup'] and all(d['cleanup_stats'][k]==0 for k in ['active_mappings','active_rw_bytes','active_reserved_bytes','release_failures'])
  if rec['negative']:
   assert rec['exit_code']==1 and not d['success'] and 'pristine oracle' in d['error'];continue
  assert rec['exit_code']==0 and d['success'] and all(s['oracle'] and s['cleanup'] for s in d['samples'])
  assert len(d['samples'])==(2 if rec['kind']=='control' else 48)
  if rec['observer']=='on':
   assert set(rec['traces'])=={str(i) for i in range(48)}
   sg={s['index']:stages(rec,s) for s in d['samples']}
  else:assert not rec['traces']
  if rec['kind']!='primary':continue
  key=(rec['mode'],rec['parallel'],rec['observer'],rec['arm'],rec['rep']);assert key in expected and key not in seen;seen.add(key);primary.append(rec)
  for child in d['samples']:
   row=dict(mode=rec['mode'],parallel=rec['parallel'],observer=rec['observer'],arm=rec['arm'],rep=rec['rep'],index=child['index'],lane=child['lane'])
   row.update({x['name']:x['end_ms']-x['begin_ms'] for x in child['spans']})
   if rec['observer']=='on':row.update(sg[child['index']])
   rows.append(row)
 assert seen==expected
 cells={}
 for mode,p,obs,arm in sorted({k[:4] for k in expected}):
  rr=[r for r in rows if (r['mode'],r['parallel'],r['observer'],r['arm'])==(mode,p,obs,arm)];pr=[r['report'] for r in primary if (r['mode'],r['parallel'],r['observer'],r['arm'])==(mode,p,obs,arm)]
  metrics=set.intersection(*(set(r) for r in rr))-{'mode','parallel','observer','arm','rep','index','lane'}
  cell={'children':len(rr),'child':{k:stats([r[k] for r in rr]) for k in sorted(metrics)},'process':{k:stats([r[k] for r in pr]) for k in ['suite_ms','batch_ms','suite_cpu_ms','batch_cpu_ms','lifetime_max_rss_bytes']}}
  if obs=='on':cell['representative_child']=min(rr,key=lambda x:abs(x['start_or_fork']-cell['child']['start_or_fork']['p50']))
  cells[f'{arm}-{mode}-p{p}-{obs}']=cell
 comparisons={}
 for mode,p,obs in sorted({k[:3] for k in expected}):
  pairs=[]
  for rep in range(3):
   br,cr=[next(r for r in primary if (r['mode'],r['parallel'],r['observer'],r['arm'],r['rep'])==(mode,p,obs,arm,rep)) for arm in ['baseline','candidate']]
   get=lambda r:statistics.median(next(s['end_ms']-s['begin_ms'] for s in child['spans'] if s['name']=='start_or_fork') for child in r['report']['samples'])
   pairs.append({'rep':rep,'start_p50_baseline_ms':get(br),'start_p50_candidate_ms':get(cr),'start_p50_change_pct':(get(cr)/get(br)-1)*100,**{k+'_change_pct':(cr['report'][k]/br['report'][k]-1)*100 for k in ['suite_ms','batch_ms','batch_cpu_ms','lifetime_max_rss_bytes']}})
  comparisons[f'{mode}-p{p}-{obs}']=pairs
 overhead={}
 for arm in ['baseline','candidate']:
  for p in [1,4]:
   off=cells[f'{arm}-fork-p{p}-off']['child']['start_or_fork']['p50'];on=cells[f'{arm}-fork-p{p}-on']['child']['start_or_fork']['p50']
   overhead[f'{arm}-p{p}']={'off_ms':off,'on_ms':on,'change_pct':(on/off-1)*100}
 return {'scope':'Actual C guest, desktop Mac; elapsed stages, no within-server attribution or individual-Fork CPU/RSS claim','primary_children':len(rows),'cells':cells,'pairs':comparisons,'observer_effect':overhead,'all_samples_retained':True},rows

def outputs(records):
 summary,rows=reduce(records);o=io.StringIO();w=csv.DictWriter(o,sorted(set().union(*(r.keys() for r in rows))),lineterminator='\n');w.writeheader();w.writerows(rows)
 return {'summary.json':json.dumps(summary,indent=2,sort_keys=True)+'\n','children.csv':o.getvalue()}
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--input',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--check',action='store_true');a=p.parse_args()
 value=json.loads(a.input.read_text());records=read(a.input) if isinstance(value,dict) and value.get('encoding')=='zlib-base64-json' else value
 for name,data in outputs(records).items():
  if a.check:assert (a.output/name).read_text()==data,name
  else:(a.output/name).write_text(data)
 print('REPLAY PASS' if a.check else 'REDUCED')
