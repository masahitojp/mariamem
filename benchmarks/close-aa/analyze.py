import json,statistics as st
from pathlib import Path
p=Path(__file__).parent
rs=[json.loads(x) for x in (p/'runs.jsonl').read_text().splitlines()];assert len(rs)==304
out=[]
for workers,cap in [(1,1),(1,2),(2,2),(2,4)]:
 for children in [48,480]:
  comps={}
  for comp in ['sync-aa','stop-aa','ab']:
   rows=[r for r in rs if r['phase']=='measure' and r['p']==workers and r['cap']==cap and r['children']==children and r['comparison']==comp];assert len(rows)==12
   pairs=[]
   for rep in range(6):
    a,b=[next(r for r in rows if r['rep']==rep and r['label']==label) for label in ['A','B']]
    expected={'sync-aa':('sync','sync'),'stop-aa':('stop','stop'),'ab':('sync','stop')}[comp];assert (a['mode'],b['mode'])==expected
    early,late=sorted([a,b],key=lambda r:r['position'])
    pairs.append({'rep':rep,'delta_ms':b['batch_drain_ms']-a['batch_drain_ms'],'signed_pct':100*(b['batch_drain_ms']/a['batch_drain_ms']-1),'cpu_pct':100*(b['batch_cpu_ms']/a['batch_cpu_ms']-1),'rss_pct':100*(b['peak_rss_bytes']/a['peak_rss_bytes']-1),'second_pct':100*(late['batch_drain_ms']/early['batch_drain_ms']-1)})
   comps[comp]={'pairs':pairs,'median_delta_ms':st.median(x['delta_ms'] for x in pairs),'median_signed_pct':st.median(x['signed_pct'] for x in pairs),'median_abs_pct':st.median(abs(x['signed_pct']) for x in pairs),'range_pct':[min(x['signed_pct'] for x in pairs),max(x['signed_pct'] for x in pairs)],'wins':sum(x['delta_ms']<0 for x in pairs),'median_cpu_pct':st.median(x['cpu_pct'] for x in pairs),'median_rss_pct':st.median(x['rss_pct'] for x in pairs),'median_second_pct':st.median(x['second_pct'] for x in pairs),'batch_medians_ms':{label:st.median(r['batch_drain_ms'] for r in rows if r['label']==label) for label in ['A','B']},'drain_medians_ms':{label:st.median(r['drain_ms'] for r in rows if r['label']==label) for label in ['A','B']}}
  out.append({'p':workers,'cap':cap,'children':children,'comparisons':comps})
print(json.dumps(out,indent=2))
