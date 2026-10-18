#!/usr/bin/env python3
"""Offline phase reconciliation. Fails on missing traces/cells; no guest execution."""
import argparse
import collections
import json
from pathlib import Path
import statistics
from campaign import validate_stamps


def events(t):
 e=t['events'];assert e[0]['name']=='begin' and e[-1]['name']=='end'
 assert all(a['offset_ns']<=b['offset_ns'] for a,b in zip(e,e[1:])),t
 assert len({x['name'] for x in e})==len(e),t
 return {x['name']:x['offset_ns'] for x in e}

def stats(xs):return dict(n=len(xs),median_ms=statistics.median(xs)/1e6,min_ms=min(xs)/1e6,max_ms=max(xs)/1e6)

def main():
 p=argparse.ArgumentParser();p.add_argument('evidence',type=Path);a=p.parse_args();root=a.evidence
 receipt=json.loads((root/'receipt.json').read_text());assert receipt['completed']
 validate_stamps(receipt['binaries'])
 assert len(receipt['commands'])==40 and all(c['exit_code']==0 for c in receipt['commands'])
 groups=collections.defaultdict(lambda:collections.defaultdict(list));pair=collections.defaultdict(dict);cells=[]
 for cmd in receipt['commands']:
  name=cmd['name'];data=json.loads((root/(name+'.json')).read_text())
  py=name.startswith('python');profile=name.startswith('profile')
  if py:
   assert data['result']=='PASS' and data['unique_hosts']==1
   values=data['times_ms'];n=data['forks'];assert n==(16 if '100mib' in name else 2)
   fork=[values[f'child{i}/start']*1e6 for i in range(n)];close=[values[f'child{i}/close']*1e6 for i in range(n)];disconnect=[values[f'child{i}/disconnect']*1e6 for i in range(n)]
  else:
   n=data['forks'];ops=data['operations']
   def measured(prefix):return [x['seconds']*1e9 for x in ops if x['name'].startswith(prefix)]
   fork=measured('fork_ready_');close=measured('child_close_');disconnect=measured('disconnect_')
   assert len(fork)==len(close)==len(disconnect)==n,(name,n)
  bucket=name.rsplit('-',2)[0] if not profile else name
  variant=name.rsplit('-',1)[1] if not profile else 'profile'
  for key,x in [('public_fork',fork),('public_close',close),('disconnect',disconnect)]:groups[bucket+'/'+variant][key].extend(x)
  if not profile:pair[name.rsplit('-',1)[0]][variant]={'fork_ms':statistics.median(fork)/1e6,'close_ms':statistics.median(close)/1e6,'disconnect_ms':statistics.median(disconnect)/1e6}
  if not cmd['timing_enabled']:continue
  traces=collections.defaultdict(list)
  for f in (root/(name+'-traces')).glob('*.json'):
   t=json.loads(f.read_text());traces[t['operation']].append(t)
  for ts in traces.values():ts.sort(key=lambda t:(t['pid'],t.get('origin_ns',0)))
  for key in ['fork','startup','api_startup','instance','memory_init','instance_guest']:
   expected=0 if py and key in ['fork','api_startup'] else n+(key!='fork')
   assert len(traces[key])==expected,(name,key,len(traces[key]),expected)
  assert len(traces['platform_check'])==(n+1)*(1 if py else 2),(name,'all platform checks')
  # Successful Snapshot consumes the parent; subsequent idempotent Close traces are excluded.
  api_close=[t for t in traces['api_close'] if any(e['name']=='host_closed' for e in t['events'])]
  assert len(traces['host_close'])==n and (py or len(api_close)==n),(name,'close counts')
  durations=collections.defaultdict(list)
  def add(key,ns):assert ns>=0,(name,key,ns);durations[key].append(ns)
  instances={(t['pid'],t['origin_ns']):t for t in traces['instance']}
  if not py and data.get('workers',1)>1:
   # Concurrent operations overlap: preserve same-scope intervals, do not guess cross-trace parentage.
   first=min(t['origin_ns'] for t in traces['fork'])
   for key in ['startup','memory_init','instance','instance_guest']:
    for t in traces[key]:
     if t['origin_ns']<first:continue
     if key=='instance_guest':
      ge={e['name']:e['offset_ns'] for e in t['guest']['events']}
      add('guest_l4m_open_and_slot_init',ge['ready_prepared']-ge['open_begin']);continue
     e=events(t)
     if key=='startup':
      add('baseline_acquire',e['metadata_snapshot_validated']-e['native_identity_checked'])
      add('linked_execution_until_ready',e['ready_header_received']-e['linked_execution_begin'])
      add('host_startup_total',e['end'])
     elif key=='memory_init':
      add('memory_mapping',e['mapping_reserved']);add('generated_memory_init',e['generated_initialized']-e['mapping_reserved'])
     else:
      add('prepared_handles',e['prepared_handles_installed']);add('guest_final_join',e['guest_workers_joined']-e['guest_root_returned'])
      add('linear_memory_release',e['memory_released']-e['guest_diagnostics_collected'])
      add('descriptor_prepared_release',e['descriptors_prepared_closed']-e['memory_released'])
   for t in traces['host_close']:
    e=events(t);add('host_session_drain',e['workers_drained']-e['accepting_stopped'])
    add('shutdown_including_resource_release',e['shutdown_returned']-e['workers_drained']);add('host_close_total',e['end'])
   for key,xs in durations.items():groups[bucket+'/observed'][key].extend(xs)
   cells.append({'name':name,'children':n,'cross_scope_pairing':False,'durations':{k:stats(v) for k,v in durations.items()}})
   continue
  fork_scopes=traces['startup'][1:] if py else traces['fork']
  for fork_index,ft in enumerate(fork_scopes):
   fe=events(ft);start=ft['origin_ns'];end=start+fe['end'];pid=ft['pid']
   def nested(key):
    found=[t for t in traces[key] if t['pid']==pid and start<=t['origin_ns']<=end];assert len(found)==1,(name,key,len(found));return found[0]
   st=nested('startup');se=events(st);mi=nested('memory_init');me=events(mi);ins=nested('instance');ie=events(ins)
   if py:
    platforms=[t for t in traces['platform_check'] if t['pid']==pid and t['origin_ns']<start][-1:]
    assert platforms and platforms[0]['origin_ns']+events(platforms[0])['end']<=start
   else:platforms=[t for t in traces['platform_check'] if t['pid']==pid and start<=t['origin_ns']<=end]
   assert len(platforms)==(1 if py else 2),(name,'platform count',len(platforms))
   platform_ns=sum(events(t)['target_detected'] for t in platforms)
   add('platform_checks_total',platform_ns)
   if py:add('python_public_remainder',fork[fork_index]-se['end']-platform_ns)
   else:add('api_other_outside_host',fe['end']-se['end']-platform_ns)
   g=[t for t in traces['instance_guest'] if (t['pid'],t['origin_ns'])==(ins['pid'],ins['origin_ns'])];assert len(g)==1
   ge={e['name']:e['offset_ns'] for e in g[0]['guest']['events']};assert {'guest_main','restore_begin','restore_complete','open_begin','ready_prepared'}<=ge.keys()
   add('baseline_acquire',se['metadata_snapshot_validated']-se['native_identity_checked'])
   add('host_transfer_setup',se['linked_execution_begin']-se['metadata_snapshot_validated'])
   add('prepared_handles',ie['prepared_handles_installed'])
   add('memory_mapping',me['mapping_reserved'])
   add('generated_memory_init',me['generated_initialized']-me['mapping_reserved'])
   add('memory_total',me['end'])
   ready=st['origin_ns']+se['ready_header_received'];initend=ins['origin_ns']+ie['memory_initialized']
   add('guest_until_ready',ready-initend)
   add('guest_main_until_ready_prepared',ge['ready_prepared']-ge['guest_main'])
   add('guest_l4m_open_and_slot_init',ge['ready_prepared']-ge['open_begin'])
   add('guest_restore_copy',ge['restore_complete']-ge['restore_begin'])
   # Independent clock intervals: subtract durations only, never align guest absolute timestamps.
   add('guest_before_main_and_ready_delivery_residual',(ready-initend)-(ge['ready_prepared']-ge['guest_main']))
   add('ready_decode_and_listener',se['wire_listener_ready']-se['ready_header_received'])
   add('host_startup_total',se['end'])
   if not py:add('fork_trace_total',fe['end'])
  for ct in traces['host_close']:
   ce=events(ct);origin=ct['origin_ns'];pid=ct['pid'];end=origin+ce['end']
   found=[t for t in traces['instance'] if t['pid']==pid and origin<=t['origin_ns']+events(t)['guest_root_returned']<=end];assert len(found)==1,(name,'closing instance',len(found))
   ins=found[0];ie=events(ins);delta=ins['origin_ns']-origin
   root_at=delta+ie['guest_root_returned'];joined=delta+ie['guest_workers_joined'];collected=delta+ie['guest_diagnostics_collected'];released=delta+ie['memory_released'];descriptors=delta+ie['descriptors_prepared_closed']
   add('host_admission_stop',ce['accepting_stopped']);add('host_session_drain',ce['workers_drained']-ce['accepting_stopped'])
   add('shutdown_write_to_guest_root',root_at-ce['workers_drained'])
   add('guest_final_join',joined-root_at);add('guest_diag_read',collected-joined)
   add('linear_memory_release',released-collected);add('descriptor_prepared_release',descriptors-released)
   add('close_after_resources',ce['end']-descriptors);add('host_close_total',ce['end'])
  for key,xs in durations.items():groups[bucket+'/observed'][key].extend(xs)
  cells.append({'name':name,'children':n,'validated_instance_count':len(instances),'durations':{k:stats(v) for k,v in durations.items()}})
 result={'groups':{k:{phase:stats(xs) for phase,xs in phases.items()} for k,phases in groups.items()},'paired_medians':dict(pair),'cells':cells}
 (root/'analysis.json').write_text(json.dumps(result,indent=2)+'\n')
 print('PASS: 40 executions, child/startup/shutdown traces and functional counts reconciled')
 for group,phases in result['groups'].items():
  print(group, ' '.join(f'{k}={v["median_ms"]:.3f}ms' for k,v in phases.items()))

if __name__=='__main__':main()
