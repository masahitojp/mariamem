"""Read-only replay with --check; derived summaries never overwrite observations."""
from pathlib import Path
from compact import read
import json,statistics,math,sys,csv,io

def stats(v):
 s=sorted(v);assert s
 return {'p50':statistics.median(s),'p95':s[math.ceil(.95*len(s))-1],'mean':statistics.mean(s),'max':max(s),'over_100ms':sum(x>100 for x in s),'n':len(s)}

def events(es):
 names=[x['name'] for x in es];assert len(names)==len(set(names)),names
 offsets=[x['offset_ns'] for x in es];assert all(a<=b for a,b in zip(offsets,offsets[1:])),names
 return {x['name']:x['offset_ns']/1e6 for x in es}

def decompose(trace):
 g=trace['startup']['guest'];gmap=events(g['events']);init=g['initialization'];assert init['dropped_records']==0
 offsets=[x['offset_ns'] for x in init['events']];assert all(a<=b for a,b in zip(offsets,offsets[1:]))
 imap=events([x for x in init['events'] if not x['name'].startswith('plugin.')]);out={}
 # Different plugin types can share a name (uuid); pair every invocation in
 # original event order and sum repeated names, never overwrite/drop them.
 pending=None;plugin_total={}
 for x in init['events']:
  name=x['name']
  if not name.startswith('plugin.'):continue
  stem,phase=name.rsplit('.',1)
  if phase=='begin':assert pending is None;pending=(stem,x['offset_ns'])
  else:
   assert phase=='end' and pending is not None and pending[0]==stem
   plugin_total[stem]=plugin_total.get(stem,0)+(x['offset_ns']-pending[1])/1e6;pending=None
 assert pending is None
 out.update(plugin_total)
 def add(name,a,b,es=imap):
  d=es[b]-es[a];assert d>=0,(name,d);out[name]=d
 add('server_init','server_init_begin','server_init_complete',gmap)
 add('common','embedded_begin','embedded_options_complete')
 add('components_before_plugins','embedded_options_complete','plugins_begin')
 add('myisam_key_cache','myisam_key_cache_begin','myisam_key_cache_complete')
 add('aria_cache','aria_cache_begin','aria_cache_complete')
 add('aria_log_cache','aria_cache_complete','aria_log_cache_complete')
 add('aria_log_init','aria_log_cache_complete','aria_log_init_complete')
 add('aria_recovery','aria_log_init_complete','aria_recovery_complete')
 add('aria_checkpoint','aria_recovery_complete','aria_checkpoint_complete')
 add('plugins','plugins_begin','plugins_complete')
 add('components_after_plugins','plugins_complete','embedded_complete')
 add('embedded','embedded_begin','embedded_complete')
 out['server_other']=out['server_init']-out['embedded'];assert out['server_other']>=-.05
 assert 'plugin.InnoDB' in out
 out['plugins_other']=out['plugins']-sum(v for k,v in out.items() if k.startswith('plugin.'));assert out['plugins_other']>=-.05
 for name,a,b in [
 ('innodb_parameters','innodb_plugin_begin','innodb_parameters_complete'),
 ('innodb_before_pool','innodb_parameters_complete','buffer_pool_begin'),
 ('buffer_pool','buffer_pool_begin','buffer_pool_complete'),
 ('innodb_memory_background','buffer_pool_complete','innodb_memory_background_complete'),
 ('innodb_open_recovery','innodb_memory_background_complete','innodb_open_recovery_complete'),
 ('innodb_transactions','innodb_open_recovery_complete','innodb_transactions_complete'),
 ('innodb_background','innodb_transactions_complete','innodb_background_complete'),
 ('innodb_finish','innodb_background_complete','innodb_start_complete')]:add(name,a,b)
 out['innodb_remaining']=out['plugin.InnoDB']-sum(v for k,v in out.items() if k.startswith('innodb_'))-out['buffer_pool'];assert out['innodb_remaining']>=-.05
 for k in ['process_cpu_ns','thread_cpu_ns']:
  assert all(x[k] is None for x in init['events']),'stage CPU availability changed'
 return out

def reduce(records):
 assert len(records)==18
 rows=[];cells={};ordinary=[]
 expected={(p,m,r) for p in [1,4] for m in ['off','on'] for r in range(3)};seen=set()
 for rec in records:
  r=rec['report'];neg=rec['negative'];assert r['cleanup']
  assert r['resolved_max_forks']==rec['parallel'] and r['max_active']<=rec['parallel']
  assert all(r['cleanup_stats'][k]==0 for k in ['active_mappings','active_rw_bytes','active_reserved_bytes','release_failures','grow_failures'])
  if neg:assert rec['exit_code']==1 and not r['success'] and 'pristine oracle' in r['error']
  else:assert rec['exit_code']==0 and r['success'] and len(r['samples'])==rec['count'] and all(x['oracle'] and x['cleanup'] for x in r['samples'])
  if rec['mode']=='on':
   assert set(rec['traces'])=={str(i) for i in range(rec['count'])}
   decoded={i:decompose(t) for i,t in rec['traces'].items()}
  if rec['kind']!='primary':continue
  key=(rec['parallel'],rec['mode'],rec['rep']);assert key in expected and key not in seen;seen.add(key)
  forks=[]
  for sample in r['samples']:
   spans={x['name']:x['end_ms']-x['begin_ms'] for x in sample['spans']};forks.append(spans['start_or_fork'])
   row={'parallel':rec['parallel'],'mode':rec['mode'],'rep':rec['rep'],'child':sample['index'],'fork':spans['start_or_fork'],'count_sum':spans['count_sum'],'update':spans['update']}
   if rec['mode']=='on':row.update(decoded[str(sample['index'])])
   rows.append(row)
  ordinary.append({'parallel':rec['parallel'],'mode':rec['mode'],'rep':rec['rep'],'suite_ms':r['suite_ms'],'suite_cpu_ms':r['suite_cpu_ms'],'batch_ms':r['batch_ms'],'process_cpu_ms':rec['process_cpu_ms'],'fork':stats(forks)})
 assert seen==expected
 for p in [1,4]:
  for mode in ['off','on']:
   rr=[r for r in rows if r['parallel']==p and r['mode']==mode];metric=sorted(set(rr[0])-{'parallel','mode','rep','child'})
   cells[f'{mode}-p{p}']={k:stats([r[k] for r in rr]) for k in metric}
 return {'cells':cells,'processes':ordinary,'stage_cpu':'N/A','primary_children':len(rows),'diagnostic_is_performance_claim':False},rows

def outputs(records):
 result,rows=reduce(records);fields=sorted(set().union(*(set(r) for r in rows)));s=io.StringIO();writer=csv.DictWriter(s,fields,lineterminator='\n');writer.writeheader();writer.writerows(rows)
 return {'summary.json':json.dumps(result,indent=2)+'\n','children.csv':s.getvalue()}
if __name__=='__main__':
 here=Path(__file__).resolve().parent
 for name,data in outputs(read(here)).items():
  if '--check' in sys.argv:assert (here/name).read_text()==data,name
  else:(here/name).write_text(data)
 print('REPLAY PASS' if '--check' in sys.argv else 'REDUCED')
