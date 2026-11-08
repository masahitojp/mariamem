"""One-cohort Fork attribution. --check is read-only and validates every child."""
from codec import read
from pathlib import Path
import json,statistics,math,sys,csv,io,importlib.util
HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('stages',HERE/'stage_analysis.py');mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
def stats(v):
 assert v;ss=sorted(v);return {'n':len(v),'p50':statistics.median(ss),'p95':ss[math.ceil(.95*len(ss))-1],'mean':statistics.mean(ss),'max':max(ss),'over_100ms':sum(x>100 for x in ss)}
def stage_row(rec,sample):
 ts=rec['traces'][str(sample['index'])];h=mod.events(ts['startup']['events']);g=mod.events(ts['startup']['guest']['events'])
 a=lambda x,y:h[y]-h[x];bb=lambda x,y:g[y]-g[x]
 spans={v['name']:v['end_ms']-v['begin_ms'] for v in sample['spans']};fork=spans['start_or_fork']
 row={'fork':fork,'host_outside_startup':fork-h['end']+h['runtime/instance_begin'],'filesystem_handles':a('runtime/instance_begin','runtime/prepared_handles_ready'),'memory_prepare':a('runtime/prepared_handles_ready','runtime/guest_execute_begin'),'server_init':bb('server_init_begin','server_init_complete'),'bootstrap_connection':bb('server_init_complete','routine_schema_begin'),'routine_schema':bb('routine_schema_begin','routine_schema_complete'),'guest_other':bb('guest_main','ready_prepared')-bb('server_init_begin','server_init_complete')-bb('server_init_complete','routine_schema_begin')-bb('routine_schema_begin','routine_schema_complete'),'execution_residual':a('runtime/guest_execute_begin','ready_response_observed')-bb('guest_main','ready_prepared'),'after_ready':a('ready_response_observed','end')}
 top=['host_outside_startup','filesystem_handles','memory_prepare','server_init','bootstrap_connection','routine_schema','guest_other','execution_residual','after_ready']
 assert min(row.values())>=-.1,row
 assert abs(sum(row[k] for k in top)-fork)<1e-6
 row.update(mod.decompose(ts))
 row['other_server']=row['server_init']-row['common']-row['plugin.InnoDB']-row['plugin.Aria']
 row['memory_reserve']=a('runtime/reserve_begin','runtime/reserve_end');row['memory_construct']=a('runtime/construct_begin','runtime/construct_end')
 assert row['other_server']>=-.1
 row['accounting_residual']=sum(row[k] for k in top)-fork
 return row

def reduce(records):
 assert len(records)==37
 rows=[];cells={};primary=[r for r in records if r['kind']=='primary'];assert len(primary)==24
 expected={(p,a,o,r) for p in [1,4] for a in ['original','prepared'] for o in ['off','on'] for r in range(3)};seen=set()
 for rec in records:
  d=rec['report'];assert d['cleanup'] and d['resolved_max_forks']==rec['parallel'] and d['max_active']<=rec['parallel']
  assert all(d['cleanup_stats'][k]==0 for k in ['active_mappings','active_rw_bytes','active_reserved_bytes','release_failures'])
  c=d['cleanup_stats'];n=rec['count']+1;arm=rec['arm']
  assert c['lp_hits']==(0 if arm=='original' else 638*n)
  assert c['lp_original']==(638*n if arm=='original' else 0)
  assert c['lp_copies']==(0 if arm=='original' else n)
  assert c['lp_verified']==(638*n if arm=='verify' else 0)
  assert c['lp_fallback']==(n if arm=='verify' else 0)
  assert d['gomaxprocs']==8 and d['go']=='go1.27.3'
  if not rec['negative']:assert d['samples'][0]['version'].startswith('12.3.3')
  if rec['negative']:assert rec['exit_code']==1 and not d['success'] and 'pristine oracle' in d['error']
  else:assert rec['exit_code']==0 and d['success'] and len(d['samples'])==rec['count'] and all(s['oracle'] and s['cleanup'] for s in d['samples'])
  if rec['observer']=='on':
   assert set(rec['traces'])=={str(i) for i in range(rec['count'])}
   stages={s['index']:stage_row(rec,s) for s in d['samples']}
   assert len(rec['undo_files'])==rec['count']
  else:assert not rec['traces'] and not rec['undo_files']
  if rec['kind']!='primary':continue
  key=(rec['parallel'],rec['arm'],rec['observer'],rec['rep']);assert key in expected and key not in seen;seen.add(key)
  for sample in d['samples']:
   spans={v['name']:v['end_ms']-v['begin_ms'] for v in sample['spans']}
   row={'parallel':rec['parallel'],'arm':rec['arm'],'observer':rec['observer'],'rep':rec['rep'],'index':sample['index'],'fork':spans['start_or_fork'],'count_sum':spans['count_sum'],'update':spans['update'],'close':spans['close']}
   if rec['observer']=='on':row.update(stages[sample['index']])
   rows.append(row)
 assert seen==expected
 for p in [1,4]:
  for arm in ['original','prepared']:
   for obs in ['off','on']:
    rr=[r for r in rows if (r['parallel'],r['arm'],r['observer'])==(p,arm,obs)];assert len(rr)==144
    metrics=sorted(set(rr[0])-{'parallel','arm','observer','rep','index'})
    process=[r['report'] for r in primary if (r['parallel'],r['arm'],r['observer'])==(p,arm,obs)]
    cell={'children':len(rr),'child':{k:stats([r[k] for r in rr]) for k in metrics},'suite':stats([r['suite_ms'] for r in process]),'suite_cpu':stats([r['suite_cpu_ms'] for r in process])}
    if obs=='on':cell['representative_child']=min(rr,key=lambda r:abs(r['fork']-cell['child']['fork']['p50']))
    cells[f'{arm}-p{p}-{obs}']=cell
 overhead={}
 for p in [1,4]:
  for arm in ['original','prepared']:
   off=cells[f'{arm}-p{p}-off']['child']['fork']['p50'];on=cells[f'{arm}-p{p}-on']['child']['fork']['p50']
   overhead[f'{arm}-p{p}']={'off_ms':off,'on_ms':on,'change_pct':(on/off-1)*100}
 return {'scope':'Go prepared prototype attribution, not C guest candidate performance','primary_children':len(rows),'diagnostic_children':sum(r['observer']=='on' for r in rows),'stage_cpu':'N/A: pinned guest process/thread CPU clocks unavailable','cells':cells,'observer_effect':overhead,'all_samples_retained':True},rows

def outputs(records):
 summary,rows=reduce(records);out=io.StringIO();wr=csv.DictWriter(out,sorted(set().union(*(r.keys() for r in rows))),lineterminator='\n');wr.writeheader();wr.writerows(rows)
 return {'summary.json':json.dumps(summary,indent=2)+'\n','children.csv':out.getvalue()}
if __name__=='__main__':
 records=read(HERE/'observations.json')
 for name,data in outputs(records).items():
  if '--check' in sys.argv:assert (HERE/name).read_text()==data,name
  else:(HERE/name).write_text(data)
 print('REPLAY PASS' if '--check' in sys.argv else 'REDUCED')
