import json,statistics as s,math
from pathlib import Path
e=Path(__file__).resolve().parent;rs=[r for r in json.loads((e/'records.json').read_text())if r['block']>=0];assert len(rs)==60
out={'arms':{},'paired':{}}
for arm in ['maria','async','pg']:
 rr=[r for r in rs if r['arm']==arm];v=[r['elapsed_ms']for r in rr];med=s.median(v)
 out['arms'][arm]={'median_ms':med,'mean_ms':s.mean(v),'min_ms':min(v),'max_ms':max(v),'values_ms':v,'above_1_2_median':[r['name']for r in rr if r['elapsed_ms']>med*1.2],'cpu_median_ms':s.median(r['cpu_ms']for r in rr),'wall_median_ms':s.median(r['wall_ms']for r in rr),'sample_max_ms':max(r['phases']['sample']['max_ms']for r in rr),'final_cleanup_median_ms':s.median(r['partition']['final_ms']for r in rr)}
for candidate,baseline in [('async','maria'),('async','pg'),('maria','pg')]:
 o={}
 for metric in ['elapsed_ms','wall_ms','cpu_ms']:
  vals=[]
  for block in range(10):
   v={a:math.exp(s.mean(math.log(r[metric])for r in rs if r['arm']==a and r['block']==block))for a in [candidate,baseline]};vals.append(100*(v[candidate]/v[baseline]-1))
  o[metric]={'block_percent':vals,'median_percent':s.median(vals),'candidate_faster_blocks':sum(x<0 for x in vals)}
 out['paired'][candidate+'/'+baseline]=o
(e/'summary.json').write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))
