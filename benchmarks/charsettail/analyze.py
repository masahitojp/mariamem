"""Read-only validation/reduction of fixed Issue100 observations."""
import argparse,copy,hashlib,json,statistics
from pathlib import Path
PREFIX='runtime/commoninit/'
MARKS=['common_begin', 'timer_begin', 'timer_end_common_variables_begin', 'status_begin', 'options_begin', 'options_version_uid_end', 'error_messages_begin', 'sql_registration_begin', 'charset_begin', 'collation_parse_begin', 'registry_begin', 'registry_end', 'collation_parse_end', 'default_lookup_begin', 'default_lookup_end', 'charset_log_defaults_end', 'path_parse_begin', 'path_parse_end', 'db_cache_begin', 'case_probe_begin', 'case_probe_end', 'common_variables_end', 'common_end']
INTERVALS={'pre_timer': ('common_begin', 'timer_begin'), 'timer': ('timer_begin', 'timer_end_common_variables_begin'), 'common_variables': ('timer_end_common_variables_begin', 'common_variables_end'), 'charset_tail': ('charset_begin', 'common_variables_end'), 'pre_lookup': ('charset_begin', 'default_lookup_begin'), 'default_lookup': ('default_lookup_begin', 'default_lookup_end'), 'remaining_charset_log_defaults': ('default_lookup_end', 'charset_log_defaults_end'), 'path_prepare': ('charset_log_defaults_end', 'path_parse_begin'), 'path_parse': ('path_parse_begin', 'path_parse_end'), 'path_checks': ('path_parse_end', 'db_cache_begin'), 'db_cache': ('db_cache_begin', 'case_probe_begin'), 'case_probe': ('case_probe_begin', 'case_probe_end'), 'remaining_tail': ('case_probe_end', 'common_variables_end'), 'common_total': ('common_begin', 'common_end'), 'before_collation_parse': ('charset_begin', 'collation_parse_begin'), 'collation_parse': ('collation_parse_begin', 'collation_parse_end'), 'registry_init': ('registry_begin', 'registry_end'), 'parse_before_registry': ('collation_parse_begin', 'registry_begin'), 'parse_after_registry': ('registry_end', 'collation_parse_end'), 'parse_to_default': ('collation_parse_end', 'default_lookup_begin')}
def med(v):return statistics.median(v)
def validate(j,marked,negative=False):
 assert j['exit_code']==(1 if negative else 0)
 assert j['result']==('FAIL' if negative else 'PASS')
 if negative:assert 'seed oracle' in j['error']
 else:assert len(j['children'])==4 and all(c['oracle'] for c in j['children'])
 assert j['scratch_remaining']==[]
 assert all(j['cleanup'][k]==0 for k in ['active_mappings','active_rw_bytes','active_reserved_bytes','release_failures'])
 for c in j['children']:
  ev=c['guest']['initialization'];assert ev['dropped_records']==0
  idx={x['name']:x['offset_ns'] for x in ev['events']}
  assert idx['embedded_options_complete']>idx['embedded_begin']
  obs=[e for e in c['events'] if e['name'].startswith(PREFIX)]
  assert [e['name'][len(PREFIX):] for e in obs]==(MARKS if marked else [])
  assert all(b['offset_ns']>=a['offset_ns'] for a,b in zip(obs,obs[1:]))
  details(c,marked)
def details(c,marked,span=None):
 events=[e for e in c['events'] if e['name'].startswith('runtime/charsetdetail/') and (span is None or span[0]<=e['offset_ns']<=span[1])]
 if not marked:assert not events
 stacks={};durations={}
 for e in events:
  kind,id,slot,bound=e['name'].split('/')[2:];key=kind+'/'+id+'/'+slot
  if bound=='begin':stacks.setdefault(key,[]).append(e['offset_ns'])
  else:
   assert bound=='end' and stacks.get(key),key
   begin=stacks[key].pop();assert e['offset_ns']>=begin
   durations[key]=durations.get(key,0)+e['offset_ns']-begin
 assert not any(stacks.values())
 return durations
def summarize(records):
 out={}
 for mode in ['control','init']:
  rows=[]
  for r in range(3):
   j=records[f'round{r}-{mode}'];validate(j,mode=='init');cols={'fork_wall':[],'fork_cpu':[],'guest_common':[],'guest_server_init':[]}
   if mode=='init':
    cols.update({k:[] for k in INTERVALS})
    cols.update(parse_handler_total=[],parse_remainder=[])
    ids=set().union(*(details(c,True) for c in j['children']))
    cols.update({'handler/'+k:[] for k in sorted(ids)})
   for c in j['children']:
    cols['fork_wall'].append(c['fork_wall_ns']);cols['fork_cpu'].append(c['fork_cpu_ns'])
    g={e['name']:e['offset_ns'] for e in c['guest']['initialization']['events']}
    cols['guest_common'].append(g['embedded_options_complete']-g['embedded_begin'])
    e={e['name']:e['offset_ns'] for e in c['guest']['events']}
    cols['guest_server_init'].append(e['server_init_complete']-e['server_init_begin'])
    if mode=='init':
     e={e['name'][len(PREFIX):]:e['offset_ns'] for e in c['events'] if e['name'].startswith(PREFIX)}
     for k,(a,b) in INTERVALS.items():cols[k].append(e[b]-e[a])
     ds=details(c,True)
     parse_handlers=sum(details(c,True,(e['collation_parse_begin'],e['collation_parse_end'])).values())
     rem=e['collation_parse_end']-e['collation_parse_begin']-(e['registry_end']-e['registry_begin'])-parse_handlers
     assert rem>=0
     cols['parse_handler_total'].append(parse_handlers);cols['parse_remainder'].append(rem)
     for k in ids:cols['handler/'+k].append(ds.get(k,0))
   rows.append({'name':f'round{r}-{mode}','child_ns':cols,'process_median_ms':{k:med(v)/1e6 for k,v in cols.items()}})
  out[mode]={'processes':rows,'median_of_process_medians_ms':{k:med([row['process_median_ms'][k] for row in rows]) for k in rows[0]['process_median_ms']}}
 return out
p=argparse.ArgumentParser();p.add_argument('evidence',type=Path);p.add_argument('--check',type=Path);a=p.parse_args()
if (a.evidence/'compact.json').exists():
 c=json.loads((a.evidence/'compact.json').read_text());r=copy.deepcopy(c['runs'])
 for j in r.values():
  for child in j['children']:
   diag=child['guest']['initialization'];diag['events']=[dict(zip(c['initialization_event_columns'],v)) for v in diag['events']]
else:
 r={f.stem:json.loads(f.read_text()) for f in a.evidence.glob('*.json') if f.stem.startswith(('round','warmup','pilot','negative')) and not f.stem.endswith('assessment')}
for n in ['pilot-init','negative-init','warmup-control','warmup-init']:validate(r[n],n.endswith('-init'),n.startswith('negative'))
s=summarize(r)
# Mechanical oracles must reject missing markers, dropped observations and hidden cleanup failures.
for kind in ['missing_marker','dropped','cleanup','missing_handler_end']:
 j=copy.deepcopy(r['round0-init'])
 if kind=='missing_marker':j['children'][0]['events']=[e for e in j['children'][0]['events'] if e['name']!=PREFIX+'timer_begin']
 if kind=='dropped':j['children'][0]['guest']['initialization']['dropped_records']=1
 if kind=='cleanup':j['cleanup']['active_mappings']=1
 if kind=='missing_handler_end':j['children'][0]['events']=[e for e in j['children'][0]['events'] if e['name']!='runtime/charsetdetail/collation/2304/244/end']
 try:validate(j,True)
 except AssertionError:pass
 else:raise AssertionError('mutation accepted: '+kind)
if (a.evidence/'preliminary.json').exists():
 preliminary=json.loads((a.evidence/'preliminary.json').read_text())
 for name,j in preliminary['runs'].items():
  negative='negative' in name;assert j['exit_code']==(1 if negative else 0) and j['result']==('FAIL' if negative else 'PASS')
  assert len(j['children'])==(1 if negative else 4)
  if negative:assert 'seed oracle' in j['error']
  else:assert all(c['oracle'] for c in j['children'])
  assert not j['scratch_remaining'] and all(j['cleanup'][k]==0 for k in ['active_mappings','active_rw_bytes','active_reserved_bytes','release_failures'])
  expected=[m for m in MARKS if not (name.startswith('coarse-') and m in ['collation_parse_begin','registry_begin','registry_end','collation_parse_end'])]
  for c in j['children']:
   assert c['guest']['initialization']['dropped_records']==0
   assert [e['name'][len(PREFIX):] for e in c['events'] if e['name'].startswith(PREFIX)]==expected
if a.check:
 assert s==json.loads(a.check.read_text())
 for name,sha in json.loads((a.evidence/'SHA256SUMS.json').read_text()).items():assert hashlib.sha256((a.evidence/name).read_bytes()).hexdigest()==sha,name
print(json.dumps(s,indent=2))
