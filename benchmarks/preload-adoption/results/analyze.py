import json,statistics as s,math
from pathlib import Path
e=Path(__file__).resolve().parent
rs=[r for r in json.loads((e/'large-records.json').read_text())if r['pair']>=0];assert len(rs)==40
out={}
for n in [4096,24576]:
 for p in [1,8]:
  rows=[r for r in rs if r['n']==n and r['p']==p];cell={};metrics=['elapsed_ms','batch_ms','prepare_ms','final_ms','cpu_ms','wall_ms','rss_bytes']
  for row in rows:
   for k in ['fork_ms','first_scan_ms','second_scan_ms','lifecycle_ms']:row[k]=s.median(x[k]for x in row['samples'])
  metrics+=['fork_ms','first_scan_ms','second_scan_ms','lifecycle_ms']
  for arm in ['ON','OFF']:
   ar=[r for r in rows if r['arm']==arm];cell[arm]={k:{'median':s.median(r[k]for r in ar),'mean':s.mean(r[k]for r in ar),'values':[r[k]for r in ar]}for k in metrics}
  cell['paired']={}
  for k in metrics:
   v=[]
   for pair in range(5):
    a=next(r for r in rows if r['pair']==pair and r['arm']=='ON');b=next(r for r in rows if r['pair']==pair and r['arm']=='OFF');v.append(100*(b[k]/a[k]-1))
   cell['paired'][k]={'percent':v,'median_percent':s.median(v),'off_faster':sum(x<0 for x in v)}
  cell['long_children']=[{'process':r['name'],'child':i,'sample':x}for r in rows for i,x in enumerate(r['samples'])if x['first_scan_ms']>200 or x['fork_ms']>100]
  out[f'n{n}-p{p}']=cell
(e/'large-summary.json').write_text(json.dumps(out,indent=2))
rows=[r for r in json.loads((e/'records.json').read_text())if r['block']>=0];assert len(rows)==20
q={}
for arm in ['ON','OFF']:
 ar=[r for r in rows if r['arm']==arm];q[arm]={k:{'median':s.median(r[k]for r in ar),'mean':s.mean(r[k]for r in ar),'values':[r[k]for r in ar]}for k in ['elapsed_ms','wall_ms','cpu_ms']}
q['paired']={}
for k in ['elapsed_ms','wall_ms','cpu_ms']:
 v=[]
 for block in range(5):
  m={a:math.exp(s.mean(math.log(r[k])for r in rows if r['block']==block and r['arm']==a))for a in ['ON','OFF']};v.append(100*(m['OFF']/m['ON']-1))
 q['paired'][k]={'percent':v,'median_percent':s.median(v),'off_faster':sum(x<0 for x in v)}
(e/'p1-summary.json').write_text(json.dumps(q,indent=2))
print('P1',q['paired'])
for c,j in out.items():print(c,{k:v for k,v in j['paired'].items()if k in ['elapsed_ms','batch_ms','fork_ms','first_scan_ms','second_scan_ms','lifecycle_ms']})
