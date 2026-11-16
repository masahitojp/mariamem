import json,statistics as s,re
from pathlib import Path
e=Path(__file__).resolve().parent
rows=json.loads((e/'runs.json').read_text());out={}
for work in ['query','suite']:
 out[work]={}
 for comp in ['aa','ab']:
  rr=[x for x in rows if x['workload']==work and x['comparison']==comp and x['phase']=='measure'];o={}
  for metric in (['query_ms','process_ms','cpu_ms']if work=='query'else['suite_ms','process_ms','cpu_ms']):
   pairs=[]
   for rep in range(5):
    a=next(x[metric]for x in rr if x['rep']==rep and x['label']=='A');b=next(x[metric]for x in rr if x['rep']==rep and x['label']=='B');pairs.append({'rep':rep,'a':a,'b':b,'delta_ms':b-a,'percent':(b/a-1)*100})
   pp=[p['percent']for p in pairs]
   o[metric]={'pairs':pairs,'a_median':s.median(p['a']for p in pairs),'b_median':s.median(p['b']for p in pairs),'paired_delta_median_ms':s.median(p['delta_ms']for p in pairs),'paired_percent_median':s.median(pp),'absolute_percent_median':s.median(abs(p)for p in pp),'percent_range':[min(pp),max(pp)],'faster':sum(p<0 for p in pp)}
  out[work][comp]=o
out['diagnostic']={}
for mode in ['os','go']:
 st=json.loads(re.search(r'TRANSPORT_STATS (.*)',(e/f'diag-{mode}.txt').read_text())[1]);o={}
 for k,v in st.items():o[k]={'calls':sum(v.values()),'bytes':sum(int(n)*c for n,c in v.items()),'empty':v.get('0',0),'histogram':v}
 out['diagnostic'][mode]=o
(e/'summary.json').write_text(json.dumps(out,indent=2))
for w in ['query','suite']:
 for c in ['aa','ab']:
  for m,v in out[w][c].items():print(w,c,m,{k:round(v[k],3)if isinstance(v[k],float)else v[k]for k in ['a_median','b_median','paired_delta_median_ms','paired_percent_median','absolute_percent_median','percent_range','faster']})
for mode,stats in out['diagnostic'].items():print(mode,{k:{q:v[q]for q in ['calls','bytes','empty']}for k,v in stats.items()})
