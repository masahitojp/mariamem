from pathlib import Path
import copy,csv,io,json,statistics,sys
E=Path(__file__).resolve().parent
def read(n):return json.loads((E/n).read_text())
def q(v,p):
 v=sorted(v);i=(len(v)-1)*p;a=int(i);return v[a]+(v[min(a+1,len(v)-1)]-v[a])*(i-a)
def stats(v):return {'mean':statistics.mean(v),'p50':statistics.median(v),'p95':q(v,.95),'max':max(v)}
def events(t):
 es=t['events'];names=[v['name'] for v in es];assert len(names)==len(set(names));return {v['name']:v['offset_ns']/1e6 for v in es}
def maria(c,tr):
 ts=tr['traces'];h=events(ts['startup']);g=events(ts['startup']['guest']);a=lambda x,y:h[y]-h[x];b=lambda x,y:g[y]-g[x]
 phases={'fork_host_setup':c['fork_ms']-h['end']+h['runtime/instance_begin'],'fork_filesystem':a('runtime/instance_begin','runtime/prepared_handles_ready'),'fork_memory_prepare':a('runtime/prepared_handles_ready','runtime/guest_execute_begin'),'fork_server_init':b('server_init_begin','server_init_complete'),'fork_bootstrap_connection':b('server_init_complete','routine_schema_begin'),'fork_routine_schema':b('routine_schema_begin','routine_schema_complete'),'fork_guest_other':b('guest_main','ready_prepared')-b('server_init_begin','server_init_complete')-b('server_init_complete','routine_schema_begin')-b('routine_schema_begin','routine_schema_complete'),'fork_execution_residual':a('runtime/guest_execute_begin','ready_response_observed')-b('guest_main','ready_prepared'),'fork_post_ready':a('ready_response_observed','end')}
 assert min(phases.values())>=-0.1,phases
 assert abs(sum(phases.values())-c['fork_ms'])<1e-6
 phases['detail_memory_acquire']=a('runtime/memory_begin','runtime/memory_ready')
 phases['detail_handles']=a('runtime/prepared_handles_begin','runtime/prepared_handles_ready')
 hc=events(ts['host_close']);rt=events(ts['runtime_threads_close']);rm=events(ts['runtime_memory_close']);rf=events(ts['runtime_files_close'])
 total=lambda x:x['end']-x['begin']
 close={'close_connection':c['connection_close_ms'],'close_disconnect_wait':c['disconnect_ms'],'close_api_outside_host':c['database_close_ms']-total(hc),'close_admission_stop':hc['admission_stopped']-hc['begin'],'close_sessions_join':hc['sessions_joined']-hc['admission_stopped'],'close_shutdown_mode':hc['shutdown_mode_end']-hc['sessions_joined'],'close_engine_and_transport':hc['shutdown_returned']-hc['shutdown_mode_end']-total(rt)-total(rm)-total(rf),'close_runtime_threads':total(rt),'close_runtime_memory':total(rm),'close_runtime_files':total(rf),'close_host_disposal':hc['end']-hc['shutdown_returned'],'close_wrapper':c['cleanup_ms']-c['connection_close_ms']-c['disconnect_ms']-c['database_close_ms']}
 assert min(close.values())>=-0.1,close
 assert abs(sum(close.values())-c['cleanup_ms'])<1e-6
 phases.update(close)
 phases['detail_memory_release']=rm['release_end']-rm['release_begin']
 phases['detail_prepared_maps_release']=rf['prepared_maps_closed']-rf['descriptors_closed']
 phases['detail_descriptors_close']=rf['descriptors_closed']-rf['begin']
 phases['detail_host_transfer_dispose']=hc['dispose_end']-hc['dispose_begin']
 return phases
def pgmem(c,tr):
 ops={}
 for e in tr['events']:
  op=ops.setdefault(e['operation'],{});assert e['name'] not in op;op[e['name']]=e['offset_ns']/1e6
 f=ops['pg_fork'];cl=ops['pg_cluster'];close=ops['pg_close'];release=ops['pg_cluster_release']
 phases={'fork_admission_and_wrapper':c['fork_ms']-(f['end']-f['begin'])+f['clone_begin']-f['begin'],'fork_fs_clone':f['clone_end']-f['clone_begin'],'fork_boot_wrapper':cl['begin']-f['clone_end'],'fork_cluster_host_setup':cl['host_ready']-cl['begin'],'fork_engine_and_ready':cl['end']-cl['host_ready'],'fork_listener_and_return':f['end']-cl['end']}
 assert min(phases.values())>=-0.1,phases
 assert abs(sum(phases.values())-c['fork_ms'])<1e-6
 closeph={'close_connection':c['connection_close_ms'],'close_disconnect_wait':c['disconnect_ms'],'close_api_wrapper':c['database_close_ms']-(close['end']-close['begin']),'close_notify_clients':close['clients_notified']-close['begin'],'close_lock_wait':close['kill_begin']-close['clients_notified'],'close_kill_wait':close['kill_end']-close['kill_begin'],'close_release_slot':close['end']-close['kill_end'],'close_wrapper':c['cleanup_ms']-c['connection_close_ms']-c['disconnect_ms']-c['database_close_ms']}
 assert min(closeph.values())>=-0.1,closeph
 assert abs(sum(closeph.values())-c['cleanup_ms'])<1e-6
 phases.update(closeph)
 procs=[v for k,v in ops.items() if k.startswith('pg_process/')];assert procs
 assert all('module_closed' in p and 'instantiate_begin' in p and 'instantiate_end' in p for p in procs)
 phases['async_segment_release_duration']=release['end']-release['begin']
 phases['async_module_release_sum']=sum(p['module_closed']-p.get('module_close_begin',p['exit_published']) for p in procs)
 phases['async_after_close_marker']=max(0,max([release['end']]+[p['module_closed'] for p in procs])-close['end'])
 phases['detail_pg_instances']=len(procs)
 phases['detail_pg_instantiate_sum']=sum(p['instantiate_end']-p['instantiate_begin'] for p in procs)
 return phases
def reduce(data):
 records=data['records'];assert len(records)==56
 assert data['completion']['result']=='PASS'
 normal=[r for r in records if r['mode'] in ['plain','traced'] and r['repetition']>=0 and not r['negative']]
 keys=[(r['variant'],r['parallel'],r['mode'],r['repetition']) for r in normal]
 assert len(keys)==36 and set(keys)=={(v,p,m,r) for v in ['maria','pgmem'] for p in [1,4,8] for m in ['plain','traced'] for r in range(3)}
 rows=[];processrows=[]
 for r in records:
  d=data['reports'][r['report']];assert r['binary_sha256']==data['inputs']['binaries'][r['variant']]['sha256']
  assert d['cleanup_complete'] and d['root_closed_before_forks'] and d['go']=='go1.27.4' and d['route']=='pipe' and d['parallel']==r['parallel'] and d['gomaxprocs']==8
  if r['negative']:assert r['returncode']!=0 and not d['success'] and 'pristine oracle' in d['error'];continue
  assert d['success'] and r['returncode']==0 and len(d['samples'])==r['count'] and {s['index'] for s in d['samples']}==set(range(r['count'])) and all(s['oracle'] and s['cleanup_complete'] for s in d['samples'])
  tr=data['traces'].get(r['traces'])
  if tr:assert set(tr['children'])=={str(s['index']) for s in d['samples']}
  if r not in normal:continue
  processrows.append({k:r[k] for k in ['variant','parallel','mode','repetition']}|{'batch_ms':d['batch_ms'],'cpu_ms':d['cpu_user_ms']+d['cpu_system_ms'],'minor_faults':d['minor_faults'],'post_batch_drain_ms':tr['post_batch_drain_ms'] if tr else None})
  for c in d['samples']:
   row={k:r[k] for k in ['variant','parallel','mode','repetition']}|{'index':c['index']}
   for k in ['fork_ms','connect_ms','select_ms','sql_ms','cleanup_ms','total_ms','connection_close_ms','disconnect_ms','database_close_ms']:row[k]=c[k]
   if tr:row.update((maria if r['variant']=='maria' else pgmem)(c,tr['children'][str(c['index'])]))
   rows.append(row)
 cells=[]
 for v in ['maria','pgmem']:
  for p in [1,4,8]:
   for mode in ['plain','traced']:
    cr=[r for r in rows if (r['variant'],r['parallel'],r['mode'])==(v,p,mode)];pr=[r for r in processrows if (r['variant'],r['parallel'],r['mode'])==(v,p,mode)];assert len(cr)==144 and len(pr)==3
    fields=set(cr[0])-{'variant','parallel','mode','repetition','index'}
    cells.append({'variant':v,'parallel':p,'mode':mode,'child':{k:stats([r[k] for r in cr]) for k in sorted(fields)},'process_values':pr,'batch_median_ms':statistics.median(r['batch_ms'] for r in pr),'cpu_median_ms':statistics.median(r['cpu_ms'] for r in pr),'sql_over100ms':sum(r['sql_ms']>100 for r in cr),'async_after_close_count':sum(r.get('async_after_close_marker',0)>0 for r in cr)})
 return {'cells':cells,'validation':{'ordinary_processes':36,'ordinary_children':1728,'warmups':12,'pilots':4,'profiles':4,'complete_matrix':True,'per_child_additive_fork_and_cleanup':True}},rows,processrows
records=read('records.json');data={'records':records,'inputs':read('inputs.json'),'completion':read('measurement-complete.json'),'reports':{r['report']:read(r['report']) for r in records},'traces':{r['traces']:read(r['traces']) for r in records if r['traces']}}
summary,rows,processrows=reduce(data)
def csv_text(rows):
 b=io.StringIO();w=csv.DictWriter(b,fieldnames=sorted(set().union(*(r.keys() for r in rows))),lineterminator='\n');w.writeheader();w.writerows(rows);return b.getvalue()
if '--check' in sys.argv:
 assert read('summary.json')==summary and (E/'children.csv').read_text()==csv_text(rows) and (E/'processes.csv').read_text()==csv_text(processrows)
 for kind in ['missing_process','duplicate_process','wrong_binary','missing_async_release','missing_maria_memory_release']:
  bad=copy.deepcopy(data);r=next(r for r in bad['records'] if r['variant']==('pgmem' if kind=='missing_async_release' else 'maria') and r['mode']=='traced' and r['repetition']==0)
  if kind=='missing_process':bad['records'].remove(r)
  elif kind=='duplicate_process':r['repetition']=1
  elif kind=='wrong_binary':r['binary_sha256']='0'*64
  else:
   child=bad['traces'][r['traces']]['children']['0']
   if kind=='missing_async_release':child['events']=[e for e in child['events'] if e['operation']!='pg_cluster_release']
   else:del child['traces']['runtime_memory_close']
  try:reduce(bad)
  except (AssertionError,KeyError):pass
  else:raise AssertionError('mutation admitted '+kind)
 print('PASS readonly 56-process validation, additive per-child accounting, five rejection controls')
else:
 (E/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');(E/'children.csv').write_text(csv_text(rows));(E/'processes.csv').write_text(csv_text(processrows))
 for c in summary['cells']:
  print(c['variant'],c['parallel'],c['mode'],'batch',round(c['batch_median_ms'],2),'fork_p50',round(c['child']['fork_ms']['p50'],3),'close_p50',round(c['child']['cleanup_ms']['p50'],3))
  if c['mode']=='traced':print({k:round(v['mean'],4) for k,v in c['child'].items() if k.startswith(('fork_','close_','async_','detail_'))})
