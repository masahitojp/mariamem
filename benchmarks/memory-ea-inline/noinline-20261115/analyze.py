from pathlib import Path
import json,statistics as st
E=Path(__file__).resolve().parent;rows=json.loads((E/'records.json').read_text());assert len(rows)==54 and all(r['code']==0 for r in rows);out={}
for p in [1,4,8]:
 d={};by={}
 for label in ['baseline','direct','noinline']:
  xs=[r for r in rows if r['p']==p and r['label']==label and r['iteration']!='warm'];assert len(xs)==5;by[label]={r['iteration']:r for r in xs};d[label]={k:st.median(r[k]for r in xs)for k in ['elapsed_ms','wall_ms','cpu_ms','maxrss_bytes']};d[label]['phases']={phase:{metric:st.median(r['phases'][phase][metric]for r in xs)for metric in ['count','sum_ms','p50_ms']}for phase in xs[0]['phases']}
 for x,y,name in [('baseline','direct','direct_vs_baseline'),('baseline','noinline','noinline_vs_baseline'),('direct','noinline','noinline_vs_direct')]:
  a,b=by[x],by[y];d[name]={}
  for key in ['elapsed_ms','wall_ms','cpu_ms']:
   deltas=[b[i][key]-a[i][key]for i in a];rates=[100*(b[i][key]/a[i][key]-1)for i in a];d[name][key]={'paired_delta_ms':deltas,'paired_percent':rates,'median_delta_ms':st.median(deltas),'median_percent':st.median(rates),'negative_pairs':sum(v<0 for v in deltas)}
 out[p]=d
(E/'summary.json').write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))
