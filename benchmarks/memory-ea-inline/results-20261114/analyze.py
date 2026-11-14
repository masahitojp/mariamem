from pathlib import Path
import json,statistics
E=Path(__file__).resolve().parent;D=E/'campaign';rows=json.loads((D/'records.json').read_text());assert len(rows)==24 and all(r['code']==0 for r in rows);out={}
for r in rows:
 spans=json.loads((D/(r['name']+'-trace.json')).read_text())['spans'];xs=[s['end_ms']-s['start_ms']for s in spans if s['name']=='raw_insert'];assert len(xs)==8;r['raw_p50_ms']=statistics.median(xs);r['raw_mean_ms']=statistics.mean(xs);r['cpu_ms']=r['user_ms']+r['system_ms'];assert (D/(r['name']+'.txt')).read_text().count('PASS raw=true')==8
for p in [1,8]:
 b=[r for r in rows if r['p']==p and r['label']=='baseline'and r['iteration']!='warm'];c=[r for r in rows if r['p']==p and r['label']=='candidate'and r['iteration']!='warm'];d={}
 for k in ['raw_p50_ms','wall_ms','cpu_ms','maxrss_bytes']:
  ds=[v[k]-u[k]for u,v in zip(b,c)];ps=[100*(v[k]/u[k]-1)for u,v in zip(b,c)];d[k]={'baseline_median':statistics.median(r[k]for r in b),'candidate_median':statistics.median(r[k]for r in c),'paired_delta':ds,'paired_percent':ps,'paired_percent_median':statistics.median(ps),'candidate_faster_pairs':sum(v<0 for v in ds)}
 out[p]=d
(E/'summary.json').write_text(json.dumps(out,indent=2));(E/'analyzed-records.json').write_text(json.dumps(rows,indent=2));print(json.dumps(out,indent=2))
