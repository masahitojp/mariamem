import pathlib,json,statistics,math,argparse
p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');a=p.parse_args();root=pathlib.Path(__file__).resolve().parent;obs=json.loads((root/'observations.json').read_text());med=statistics.median
assert len(obs)==14
phases=('order_insert','item_insert','stock_update','commit','begin','prepare','statement_close','rollback_cleanup')
def quant(v,p):return sorted(v)[math.ceil(p*len(v))-1]
summary={'scope':'Caller-only diagnostic: same70-case Pipe/P8 suite,5 alternating16/8 pairs;2 warmups and2 observer-off sanity runs separate. All observations retained; per-call wall includes engine/driver/host/scheduling. No CPU attribution or lock owner inference.','arms':{},'long_operations_ge100ms':[],'run_details':[]}
for arm in (16,8):
 runs=[r for r in obs if r['phase']=='primary' and r['pool_mib']==arm];assert len(runs)==5 and all(len(r['loaders'])==21 for r in runs)
 loaders=[l for r in runs for l in r['loaders']];values={}
 for phase in phases:
  calls=[v/1000 for l in loaders for v in l['durations_us'][phase]];totals=[sum(l['durations_us'][phase])/1000 for l in loaders]
  values[phase]={'calls':len(calls),'per_call_ms':{'p50':med(calls),'p95':quant(calls,.95),'p99':quant(calls,.99),'max':max(calls),'ge100ms':sum(x>=100 for x in calls),'ge500ms':sum(x>=500 for x in calls)},'per_loader_sum_ms':{'p50':med(totals),'p95':quant(totals,.95),'max':max(totals)}}
 total=[l['total_us']/1000 for l in loaders];residual=[(l['total_us']-sum(sum(v) for v in l['durations_us'].values()))/1000 for l in loaders]
 elapsed=[r['trace']['elapsed_ms'] for r in runs];cpu=[float(r['trace']['meta']['cpu_ms']) for r in runs]
 summary['arms'][str(arm)]={'suite_ms':elapsed,'suite_p50_ms':med(elapsed),'cpu_ms':cpu,'cpu_p50_ms':med(cpu),'loader_total_ms':{'p50':med(total),'p95':quant(total,.95),'max':max(total)},'loader_unattributed_ms':{'p50':med(residual),'max':max(residual)},'phases':values}
 for r in runs:
  largest=max(r['loaders'],key=lambda l:l['total_us']);events=[]
  for l in r['loaders']:
   sample_span=next(x for x in r['trace']['spans'] if x['kind']=='sample' and x['lane']==l['lane'])
   assert sample_span['start_ms']*1000<=l['start_us']+3
   assert l['start_us']+l['total_us']<=sample_span['end_ms']*1000+3
   for event in l['operations_ge50ms'] or []:
    assert not event.get('error')
    if event['duration_us']>=100000:
     v=dict(pool_mib=arm,pair=r['pair'],lane=l['lane'],**event)
     if event['phase']=='prepare':
      indices=[i for i,duration in enumerate(l['durations_us']['prepare']) if duration==event['duration_us']]
      assert len(indices)==1
      v['prepare_ordinal']=indices[0]+1
      v['prepared_statement']=('orders INSERT','order_items INSERT','products UPDATE')[indices[0]]
     events.append(v);summary['long_operations_ge100ms'].append(v)
  summary['run_details'].append({'pool_mib':arm,'pair':r['pair'],'suite_ms':r['trace']['elapsed_ms'],'largest_loader':{'lane':largest['lane'],'total_ms':largest['total_us']/1000,'phase_totals_ms':{k:sum(v)/1000 for k,v in largest['durations_us'].items()}},'operations_ge100ms':len(events)})
base=summary['arms']['16']['suite_ms'];cand=summary['arms']['8']['suite_ms'];d=[100*(c/b-1) for b,c in zip(base,cand)];summary['paired_suite']={'percent_changes':d,'median_percent':med(d),'improved_pairs':sum(c<b for b,c in zip(base,cand))}
summary['paired_loader_phase_medians']={}
for phase in phases:
 values={arm:[med(sum(l['durations_us'][phase])/1000 for l in next(r for r in obs if r['phase']=='primary' and r['pool_mib']==arm and r['pair']==pair)['loaders']) for pair in range(5)] for arm in (16,8)}
 summary['paired_loader_phase_medians'][phase]={'16_ms':values[16],'8_ms':values[8],'improved_pairs':sum(c<b for b,c in zip(values[16],values[8])),'deltas_ms':[c-b for b,c in zip(values[16],values[8])]}
summary['sanity_controls']=[{'pool_mib':r['pool_mib'],'suite_ms':r['trace']['elapsed_ms'],'cpu_ms':float(r['trace']['meta']['cpu_ms'])} for r in obs if r['phase']=='observer_off']
text=json.dumps(summary,indent=2)+'\n'
if a.check:assert (root/'summary.json').read_text()==text
else:(root/'summary.json').write_text(text)
for arm,r in summary['arms'].items():
 print(arm,'suite',r['suite_ms'],'CPU',r['cpu_p50_ms'],'loader',r['loader_total_ms'],'residual',r['loader_unattributed_ms'])
 for k,v in r['phases'].items():print(k,'loader',v['per_loader_sum_ms'],'call',v['per_call_ms'])
print('LONG',summary['long_operations_ge100ms']);print('PAIRED',summary['paired_suite'])
