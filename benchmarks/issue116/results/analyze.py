from pathlib import Path
import json,statistics,csv,io,sys,copy
E=Path(__file__).resolve().parent
read=lambda n:json.loads((E/n).read_text())
median=statistics.median

def reduce(records):
 rows=[];stage=[];cells=[];pairs=[]
 for p in [4,8]:
  for mode,count in [('primary',5),('diagnostic',3)]:
   group={}
   for variant in ['baseline','candidate']:
    rr=[r for r in records if r['parallel']==p and r['mode']==mode and r['variant']==variant];assert len(rr)==count and {r['repetition'] for r in rr}==set(range(count))
    vals=[]
    for r in sorted(rr,key=lambda r:r['repetition']):
     d=read(r['report']);assert r['exitcode']==0 and d['success'] and d['cleanup_complete'] and d['root_closed_before_forks'] and d['route']=='pipe' and len(d['samples'])==48 and d['skip_clear']==(variant=='candidate');assert {s['index'] for s in d['samples']}==set(range(48)) and all(s['oracle'] and s['cleanup_complete'] for s in d['samples']);assert r['peak_active']==p
     v={'parallel':p,'mode':mode,'variant':variant,'round':r['repetition'],'batch_ms':d['batch_ms'],'cpu_per_child_ms':(d['cpu_user_ms']+d['cpu_system_ms'])/48,'fork_p50_ms':median(s['fork_ms'] for s in d['samples']),'sql_over100ms':sum(s['sql_ms']>100 for s in d['samples'])}
     if mode=='primary':assert all(v==0 for v in d['read_stats'].values())
     else:
      server=[];memory=[]
      for s in d['samples']:
       t=d['child_traces'][str(s['index'])]['startup'];g={x['name']:x['offset_ns']/1e6 for x in t['guest']['events']};h={x['name']:x['offset_ns']/1e6 for x in t['events']};server.append(g['server_init_complete']-g['server_init_begin']);memory.append(h['runtime/guest_execute_begin']-h['runtime/prepared_handles_ready'])
      v['server_init_mean_ms']=statistics.mean(server);v['memory_mean_ms']=statistics.mean(memory);v['block_prefix_bytes_per_child']=d['read_stats']['block_prefix_bytes']/48;v['mapped_prefix_bytes_per_child']=d['read_stats']['mapped_prefix_bytes']/48
     vals.append(v);rows.append(v)
    group[variant]=vals;cells.append({'parallel':p,'mode':mode,'variant':variant,'processes':count,'process_values':vals,**{key+'_median':median(v[key] for v in vals) for key in vals[0] if key not in ['parallel','mode','variant','round']}})
   ps=[]
   for b,c in zip(group['baseline'],group['candidate']):
    v={'parallel':p,'mode':mode,'round':b['round'],'fork_saved_ms':b['fork_p50_ms']-c['fork_p50_ms'],'fork_saved_percent':100*(1-c['fork_p50_ms']/b['fork_p50_ms']),'cpu_saved_percent':100*(1-c['cpu_per_child_ms']/b['cpu_per_child_ms']),'batch_saved_percent':100*(1-c['batch_ms']/b['batch_ms'])}
    if mode=='diagnostic':v['server_init_saved_ms']=b['server_init_mean_ms']-c['server_init_mean_ms'];v['memory_saved_ms']=b['memory_mean_ms']-c['memory_mean_ms']
    ps.append(v)
   pairs.append({'parallel':p,'mode':mode,'pairs':ps,**{key+'_median':median(v[key] for v in ps) for key in ps[0] if key not in ['parallel','mode','round']},'fork_wins':sum(v['fork_saved_ms']>0 for v in ps),'cpu_wins':sum(v['cpu_saved_percent']>0 for v in ps)})
 p4=next(v for v in pairs if v['parallel']==4 and v['mode']=='primary');p8=next(v for v in pairs if v['parallel']==8 and v['mode']=='primary');diag=next(v for v in pairs if v['parallel']==4 and v['mode']=='diagnostic')
 gates={'correctness':True,'mechanism':read('mechanism.json')['result']=='PASS','p4_fork':p4['fork_saved_ms_median']>=1 and p4['fork_saved_percent_median']>=3 and p4['fork_wins']>=4,'p4_cpu':p4['cpu_saved_percent_median']>=3 and p4['cpu_wins']>=4,'p8_guard':p8['fork_saved_percent_median']>=-5 and p8['cpu_saved_percent_median']>=-5,'batch_guard':p4['batch_saved_percent_median']>=-5 and p8['batch_saved_percent_median']>=-5}
 prediction={'p4_supported':diag['server_init_saved_ms_median']>=.5 and sum(x['server_init_saved_ms']>0 for x in diag['pairs'])>=2,'p4_server_init_saved_ms_median':diag['server_init_saved_ms_median'],'p8_server_init_saved_ms_median':next(v for v in pairs if v['parallel']==8 and v['mode']=='diagnostic')['server_init_saved_ms_median']}
 return {'cells':cells,'paired':pairs,'gates':gates,'prediction':prediction,'recommendation':'CONTINUE_CANDIDATE_REVIEW' if all(gates.values()) else 'STOP_THIS_ROUND_THRESHOLDS_NOT_MET'},rows
assert read('complete.json')['result']=='PASS';records=read('records.json');result,rows=reduce(records)
buf=io.StringIO();fields=sorted(set().union(*(r.keys() for r in rows)));wr=csv.DictWriter(buf,fieldnames=fields,lineterminator='\n');wr.writeheader();wr.writerows(rows)
if '--check' in sys.argv:
 assert result==read('summary.json') and buf.getvalue()==(E/'processes.csv').read_text()
 for kind in ['missing','variant']:
  bad=copy.deepcopy(records)
  if kind=='missing':bad=[r for r in bad if not(r['parallel']==4 and r['mode']=='primary' and r['variant']=='candidate' and r['repetition']==0)]
  else:next(r for r in bad if r['mode']=='primary')['variant']='invalid'
  try:reduce(bad)
  except AssertionError:pass
  else:raise AssertionError('mutation admitted '+kind)
 print('PASS readonly exact matrix/JSON/CSV/gates and two rejection controls')
else:
 (E/'summary.json').write_text(json.dumps(result,indent=2)+'\n');(E/'processes.csv').write_text(buf.getvalue())
 for c in result['cells']:print(c['parallel'],c['mode'],c['variant'],{k:round(v,3) for k,v in c.items() if k.endswith('_median')})
 print(json.dumps({'paired':result['paired'],'gates':result['gates'],'prediction':result['prediction'],'recommendation':result['recommendation']},indent=2))
