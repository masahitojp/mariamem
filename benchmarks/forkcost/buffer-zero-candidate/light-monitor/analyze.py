from pathlib import Path
import json,statistics as st,csv,io
E=Path(__file__).resolve().parent;rs=json.loads((E/'measurement-records.json').read_text());assert len(rs)==32
assert {(r['p'],r['variant'],r['harness'],r['repetition']) for r in rs}=={(p,v,h,n) for p in (1,8) for v in ('baseline','candidate') for h in ('lifecycle','suite') for n in (-1,0,1,2)}
summary={'cells':{},'paired_changes':{}};children=[]
for p in (1,8):
 for v in ('baseline','candidate'):
  cell={}
  for h in ('lifecycle','suite'):
   rows=sorted([r for r in rs if (r['p'],r['variant'],r['harness'])==(p,v,h) and r['repetition']>=0],key=lambda r:r['repetition'])
   ds=[json.loads((E/'runs'/(r['name']+'.json')).read_text()) for r in rows]
   if h=='lifecycle':
    for d in ds:assert d['success'] and d['parallel']==p and not d['traced'] and not d['profile'] and len(d['children'])==48 and {c['index'] for c in d['children']}==set(range(48)) and all(c['oracle'] and c['closed'] for c in d['children'])
    cell[h]={k:{'p50_ms':st.median(c[k] for d in ds for c in d['children']),'process_p50_ms':[st.median(c[k] for c in d['children']) for d in ds]} for k in ('fork_ms','validation_sql_connection_ms','disconnect_wait_ms','close_ms')}
    for r,d in zip(rows,ds):
     for c in d['children']:children.append(dict(p=p,variant=v,repetition=r['repetition'],**{k:c[k] for k in ('index','fork_ms','validation_sql_connection_ms','disconnect_wait_ms','close_ms')}))
   else:
    assert all(d['meta']['server_version']=='12.3.3-MariaDB-embedded' and d['meta']['model']=='mariamem' for d in ds)
    cell[h]={'elapsed_ms':[d['elapsed_ms'] for d in ds],'median_ms':st.median(d['elapsed_ms'] for d in ds),'span_mean_ms':{k:st.mean(s['end_ms']-s['start_ms'] for d in ds for s in d['spans'] if s['kind']==k) for k in sorted({s['kind'] for d in ds for s in d['spans']})}}
   cell[h]['cpu_ms']=[r['cpu_user_ms']+r['cpu_system_ms'] for r in rows]
  summary['cells'][f'p{p}-{v}']=cell
 b=summary['cells'][f'p{p}-baseline'];c=summary['cells'][f'p{p}-candidate']
 summary['paired_changes'][str(p)]={'fork_p50_improvement_percent':100*(1-c['lifecycle']['fork_ms']['p50_ms']/b['lifecycle']['fork_ms']['p50_ms']),'suite_improvement_percent':100*(1-c['suite']['median_ms']/b['suite']['median_ms']),'fork_process_pairs_percent':[100*(1-y/x) for x,y in zip(b['lifecycle']['fork_ms']['process_p50_ms'],c['lifecycle']['fork_ms']['process_p50_ms'])],'suite_process_pairs_percent':[100*(1-y/x) for x,y in zip(b['suite']['elapsed_ms'],c['suite']['elapsed_ms'])]}
(E/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');o=io.StringIO();w=csv.DictWriter(o,fieldnames=list(children[0]),lineterminator='\n');w.writeheader();w.writerows(children);(E/'children.csv').write_text(o.getvalue());print(json.dumps(summary['paired_changes'],indent=2))
