from pathlib import Path
import json,statistics,csv,io,sys,copy
E=Path(__file__).resolve().parent
read=lambda n:json.loads((E/n).read_text())
def q(v,p):
 v=sorted(v);i=(len(v)-1)*p;a=int(i);return v[a]+(v[min(a+1,len(v)-1)]-v[a])*(i-a)
def stats(v):return {'mean':statistics.mean(v),'p50':statistics.median(v),'p95':q(v,.95),'max':max(v)}
def reduce(records):
 ordinary=[r for r in records if r['repetition']>=0 and r['mode'] in ['plain','traced'] and not r['negative']];assert len(ordinary)==18
 rows=[];cells=[]
 for p in [1,4,8]:
  for mode in ['plain','traced']:
   rr=[r for r in ordinary if r['parallel']==p and r['mode']==mode];assert len(rr)==3 and {r['repetition'] for r in rr}=={0,1,2};ds=[]
   for r in rr:
    d=read(r['report']);assert d['success'] and d['cleanup_complete'] and d['root_closed_before_forks'] and d['route']=='pipe' and d['parallel']==p and len(d['samples'])==48
    ds.append(d)
    for c in d['samples']:
     assert c['oracle'] and c['cleanup_complete'];row={'parallel':p,'mode':mode,'round':r['repetition'],'index':c['index'],'fork_ms':c['fork_ms'],'connect_ms':c['connect_ms'],'sql_ms':c['sql_ms'],'cleanup_ms':c['cleanup_ms'],'total_ms':c['total_ms']}
     if mode=='traced':
      ts=d['child_traces'][str(c['index'])];h={x['name']:x['offset_ns']/1e6 for x in ts['startup']['events']};g={x['name']:x['offset_ns']/1e6 for x in ts['startup']['guest']['events']};a=lambda x,y:h[y]-h[x];b=lambda x,y:g[y]-g[x]
      phases={'host_before_instance':c['fork_ms']-h['end']+h['runtime/instance_begin'],'filesystem_and_handles':a('runtime/instance_begin','runtime/prepared_handles_ready'),'memory_reserve_construct':a('runtime/prepared_handles_ready','runtime/guest_execute_begin'),'server_init':b('server_init_begin','server_init_complete'),'bootstrap_connection':b('server_init_complete','routine_schema_begin'),'routine_schema':b('routine_schema_begin','routine_schema_complete'),'guest_other':b('guest_main','ready_prepared')-b('server_init_begin','server_init_complete')-b('server_init_complete','routine_schema_begin')-b('routine_schema_begin','routine_schema_complete'),'execution_residual':a('runtime/guest_execute_begin','ready_response_observed')-b('guest_main','ready_prepared'),'after_ready':a('ready_response_observed','end')}
      assert min(phases.values())>=-0.1,phases;assert abs(sum(phases.values())-c['fork_ms'])<1e-6
      row.update(phases);row['reserve_only']=a('runtime/reserve_begin','runtime/reserve_end');row['construct_only']=a('runtime/construct_begin','runtime/construct_end');row['handles_only']=a('runtime/prepared_handles_begin','runtime/prepared_handles_ready');row['admission_to_handle']={x['name']:x['offset_ns']/1e6 for x in ts['fork']['events']}['snapshot_handle_ready']
     rows.append(row)
   cr=[x for x in rows if x['parallel']==p and x['mode']==mode];keys=[k for k in cr[0] if k not in ['parallel','mode','round','index']];cell={'parallel':p,'mode':mode,'children':144,'batch_ms':[d['batch_ms'] for d in ds],'cpu_ms':[d['cpu_user_ms']+d['cpu_system_ms'] for d in ds],'minor_faults':[d['minor_faults'] for d in ds],'involuntary_switches':[d['involuntary_switches'] for d in ds],'child':{k:stats([x[k] for x in cr]) for k in keys},'sql_over100ms':sum(x['sql_ms']>100 for x in cr)};cell['batch_median_ms']=statistics.median(cell['batch_ms']);cell['cpu_per_child_ms']=statistics.median(cell['cpu_ms'])/48;cells.append(cell)
 return {'cells':cells},rows
assert read('complete.json')['result']=='PASS';records=read('records.json');result,rows=reduce(records)
buf=io.StringIO();fields=sorted(set().union(*(r.keys() for r in rows)));wr=csv.DictWriter(buf,fieldnames=fields,lineterminator='\n');wr.writeheader();wr.writerows(rows)
if '--check' in sys.argv:
 assert result==read('summary.json');assert buf.getvalue()==(E/'children.csv').read_text()
 bad=copy.deepcopy(records);bad=[r for r in bad if not(r['mode']=='traced' and r['parallel']==4 and r['repetition']==0)]
 try:reduce(bad)
 except AssertionError:pass
 else:raise AssertionError('missing trace cell admitted')
 print('PASS readonly reduction; complete matrix and per-child additive accounting; missing-cell rejection')
else:
 (E/'summary.json').write_text(json.dumps(result,indent=2)+'\n');(E/'children.csv').write_text(buf.getvalue())
 for c in result['cells']:
  print(c['parallel'],c['mode'],'batch',round(c['batch_median_ms'],1),'CPU/child',round(c['cpu_per_child_ms'],1),'Fork',round(c['child']['fork_ms']['p50'],2),'p95',round(c['child']['fork_ms']['p95'],2))
  if c['mode']=='traced':print({k:round(v['mean'],2) for k,v in c['child'].items()})
