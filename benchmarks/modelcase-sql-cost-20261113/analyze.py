from pathlib import Path
import json,statistics,collections
r=Path(__file__).resolve().parent;summary={}
for file,prefix in [('runs.json','primary-'),('poolequal-runs.json','poolequal-primary-')]:
 rows=json.loads((r/file).read_text());groups=collections.defaultdict(list)
 for row in rows:
  if row['name'].startswith(prefix):
   assert row['returncode']==0 and row['leaf_pass']==70,row
   t=json.loads((r/(row['name']+'-trace.json')).read_text());assert sum(s['name']=='test' for s in t['spans'])==70
   groups[row['arm']].append(row)
 for arm,a in groups.items():
  assert len(a)==3
  d={'wall_samples_ms':[x['wall_ms'] for x in a],'wall_median_ms':statistics.median(x['wall_ms'] for x in a)}
  for phase in ['boot','import','snapshot','fork','sample','test']:
   per=[]
   for x in a:
    t=json.loads((r/(x['name']+'-trace.json')).read_text());per.append(statistics.median(s['end_ms']-s['start_ms'] for s in t['spans'] if s['name']==phase))
   d[phase+'_median_ms']=statistics.median(per)
  summary[file+':'+arm]=d
(r/'summary.json').write_text(json.dumps(summary,indent=2));print(json.dumps(summary,indent=2))
