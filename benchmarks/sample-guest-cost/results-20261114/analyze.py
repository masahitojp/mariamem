from pathlib import Path
import json,re,statistics as st
E=Path(__file__).resolve().parent
out={}
for engine in ['maria','pg']:
 runs=[]
 for i in range(3):
  txt=(E/f'{engine}-query-{i}.txt').read_text();pairs=json.loads(re.search(r'REVENUE_PAIRS (.+)',txt)[1]);runs.append({'original_p50_ms':st.median(x[0] for x in pairs),'preagg_p50_ms':st.median(x[1] for x in pairs),'paired_delta_p50_ms':st.median(x[1]-x[0]for x in pairs)})
 out[engine]={'query_processes':runs,'suite':{}}
 for p in [1,8]:
  vals=[[],[]]
  for arm in [0,1]:
   for i in range(3):
    d=json.loads((E/f'{engine}-p{p}-r{i}-a{arm}.json').read_text());vals[arm].append(d.get('elapsed_ms'))
  out[engine]['suite'][p]=vals
(E/'summary.json').write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))
