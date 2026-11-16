import json,statistics as s,math
from pathlib import Path
e=Path(__file__).resolve().parent
rows=json.loads((e/'records.json').read_text());rs=[r for r in rows if r['block']>=0];assert len(rs)==40
out={'arms':{},'paired':{},'aa':{}}
for arm in ['ON','OFF']:
 ar=[r for r in rs if r['arm']==arm];v=[r['elapsed_ms']for r in ar];med=s.median(v)
 out['arms'][arm]={'elapsed_values_ms':v,'median_ms':med,'mean_ms':s.mean(v),'min_ms':min(v),'max_ms':max(v),'above_1_2_median':[r['name']for r in ar if r['elapsed_ms']>med*1.2],'metrics_medians':{k:s.median(r[k]for r in ar)for k in ['wall_ms','cpu_ms','maxrss_bytes']},'partition_medians':{k:s.median(r['partition'][k]for r in ar)for k in ar[0]['partition']},'phase_medians':{k:{a:s.median(r['phases'][k][a]for r in ar)for a in ['p50_ms','max_ms','sum_ms']}for k in ar[0]['phases']}}
 aa=[]
 for block in range(10):
  ar=[r for r in rs if r['arm']==arm and r['block']==block]
  if ar[1]['seq']-ar[0]['seq']==1:aa.append(100*(ar[1]['elapsed_ms']/ar[0]['elapsed_ms']-1))
 out['aa'][arm]={'adjacent_percent':aa,'absolute_median_percent':s.median(map(abs,aa))}
for metric in ['elapsed_ms','wall_ms','cpu_ms','maxrss_bytes']:
 ratios=[]
 for block in range(10):
  values={arm:math.exp(s.mean(math.log(r[metric])for r in rs if r['block']==block and r['arm']==arm))for arm in ['ON','OFF']}
  ratios.append(100*(values['OFF']/values['ON']-1))
 out['paired'][metric]={'block_percent':ratios,'median_percent':s.median(ratios),'off_faster_blocks':sum(x<0 for x in ratios)}
(e/'summary.json').write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))
