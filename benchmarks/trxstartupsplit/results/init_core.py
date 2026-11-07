"""Read-only replay with --check; derived summaries never overwrite observations."""
from pathlib import Path
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
