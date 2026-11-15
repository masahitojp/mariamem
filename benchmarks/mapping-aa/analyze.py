import json,statistics as st
from pathlib import Path
p=Path(__file__).parent
rs=json.loads((p/'runs.json').read_text());assert len(rs)==156
out=[]
for workers in [1,2]:
 for dirty in [0,1,64]:
  for cycles in [48,480]:
   rows=[r for r in rs if r['phase']=='measure' and r['p']==workers and r['dirty_mib']==dirty and r['cycles_per_worker']==cycles];assert len(rows)==12
   pairs=[]
   for rep in range(6):
    a,b=[next(r for r in rows if r['rep']==rep and r['label']==label) for label in ['A','Aprime']]
    early,late=sorted([a,b],key=lambda r:r['position'])
    pairs.append({'rep':rep,'delta_ms':b['wall_ms']-a['wall_ms'],'signed_pct':100*(b['wall_ms']/a['wall_ms']-1),'cpu_pct':100*(b['cpu_ms']/a['cpu_ms']-1),'second_over_first_pct':100*(late['wall_ms']/early['wall_ms']-1)})
   out.append({'p':workers,'dirty_mib':dirty,'cycles':cycles,'pairs':pairs,'median_wall_ms':st.median(r['wall_ms'] for r in rows),'median_signed_pct':st.median(x['signed_pct'] for x in pairs),'median_abs_pct':st.median(abs(x['signed_pct']) for x in pairs),'max_abs_pct':max(abs(x['signed_pct']) for x in pairs),'median_abs_ms':st.median(abs(x['delta_ms']) for x in pairs),'median_second_pct':st.median(x['second_over_first_pct'] for x in pairs),'minor_faults_range':[min(r['minor_faults'] for r in rows),max(r['minor_faults'] for r in rows)],'major_faults_range':[min(r['major_faults'] for r in rows),max(r['major_faults'] for r in rows)]})
print(json.dumps(out,indent=2))
