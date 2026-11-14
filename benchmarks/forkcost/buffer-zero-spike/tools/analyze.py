from pathlib import Path
import json,statistics as st,csv,io
E=Path(__file__).resolve().parent;records=json.loads((E/'measurement-records.json').read_text());assert len(records)==48
measured=[r for r in records if r['repetition']>=0];assert len(measured)==36
assert {(r['p'],r['variant'],r['harness'],r['repetition']) for r in measured}=={(p,v,h,n) for p in (1,8) for v in ('canonical','baseline','metadata') for h in ('probe','suite') for n in range(3)}
cells={};children=[];processes=[]
for p in (1,8):
 for v in ('canonical','baseline','metadata'):
  out={}
  for h in ('probe','suite'):
   rs=[r for r in measured if (r['p'],r['variant'],r['harness'])==(p,v,h)];assert len(rs)==3
   ds=[json.loads((E/'runs'/(r['name']+'.json')).read_text()) for r in rs]
   metric={}
   if h=='probe':
    for d in ds:assert d['success'] and not d['traced'] and not d['profile'] and d['parallel']==p and len(d['children'])==48 and {c['index'] for c in d['children']}==set(range(48)) and all(c['oracle'] and c['closed'] for c in d['children'])
    vals=[c['fork_ms'] for d in ds for c in d['children']];metric={'n':len(vals),'fork_p50_ms':st.median(vals),'fork_mean_ms':st.mean(vals),'process_fork_p50_ms':[st.median(c['fork_ms'] for c in d['children']) for d in ds]}
    for r,d in zip(rs,ds):
     for c in d['children']:children.append({'p':p,'variant':v,'repetition':r['repetition'],'index':c['index'],'fork_ms':c['fork_ms']})
   else:
    assert all(d['meta']['server_version']=='12.3.3-MariaDB-embedded' and d['meta']['model']=='mariamem' for d in ds)
    metric={'elapsed_ms':[d['elapsed_ms'] for d in ds],'elapsed_median_ms':st.median(d['elapsed_ms'] for d in ds),'kind_duration_mean_ms':{k:st.mean(s['end_ms']-s['start_ms'] for d in ds for s in d['spans'] if s['kind']==k) for k in sorted({s['kind'] for d in ds for s in d['spans']})},'kind_count_per_process':[{k:sum(s['kind']==k for s in d['spans']) for k in sorted({s['kind'] for s in d['spans']})} for d in ds]}
   metric.update(cpu_median_ms=st.median(r['cpu_user_ms']+r['cpu_system_ms'] for r in rs),minor_faults=[r['minor_faults'] for r in rs],process_wall_ms=[r['process_wall_ms'] for r in rs]);out[h]=metric
   processes.extend(rs)
  cells[f'p{p}-{v}']=out
summary={'cells':cells,'within_binary_pairs':{}}
for p in (1,8):
 b=cells[f'p{p}-baseline'];m=cells[f'p{p}-metadata'];summary['within_binary_pairs'][str(p)]={'fork_p50_improvement_percent':(1-m['probe']['fork_p50_ms']/b['probe']['fork_p50_ms'])*100,'suite_median_improvement_percent':(1-m['suite']['elapsed_median_ms']/b['suite']['elapsed_median_ms'])*100,'paired_fork_process_p50_improvement_percent':[(1-y/x)*100 for x,y in zip(b['probe']['process_fork_p50_ms'],m['probe']['process_fork_p50_ms'])],'paired_suite_improvement_percent':[(1-y/x)*100 for x,y in zip(b['suite']['elapsed_ms'],m['suite']['elapsed_ms'])]}
(E/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
b=io.StringIO();w=csv.DictWriter(b,fieldnames=list(children[0]),lineterminator='\n');w.writeheader();w.writerows(children);(E/'children.csv').write_text(b.getvalue())
for key,c in cells.items():print(key,'fork',round(c['probe']['fork_p50_ms'],3),'suite',round(c['suite']['elapsed_median_ms'],3),'CPU',round(c['probe']['cpu_median_ms'],1),round(c['suite']['cpu_median_ms'],1))
print(json.dumps(summary['within_binary_pairs'],indent=2))
life=json.loads((E/'lifecycle-records.json').read_text());assert len(life)==24;life=[r for r in life if r['repetition']>=0];assert len(life)==18
close={}
for p in (1,8):
 for v in ('canonical','baseline','metadata'):
  rs=[r for r in life if r['p']==p and r['variant']==v];ds=[json.loads((E/'lifecycle-runs'/(r['name']+'.json')).read_text()) for r in rs];cs=[c for d in ds for c in d['children']];assert len(cs)==144 and all(c['closed'] and c['oracle'] for c in cs)
  close[f'p{p}-{v}']={k:{'p50_ms':st.median(c[k] for c in cs),'mean_ms':st.mean(c[k] for c in cs),'process_p50_ms':[st.median(c[k] for c in d['children']) for d in ds]} for k in ['fork_ms','validation_sql_connection_ms','disconnect_wait_ms','close_ms']}
summary['close_supplement']=close;(E/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
for key,c in close.items():print(key,{k:round(d['p50_ms'],3) for k,d in c.items()})
