from pathlib import Path
import json,statistics as st,hashlib,re,gzip
E=Path(__file__).resolve().parent
rows=json.loads((E/'records.json').read_text());summary=json.loads((E/'summary.json').read_text())
assert len(rows)==36
assert len({r['name'] for r in rows})==36
for r in rows:
 j=json.loads((E/'campaign'/(r['name']+'.json')).read_text());assert r['code']==0 and j['elapsed_ms']==r['elapsed_ms']
 for name,count in [('test',70),('fork',20),('sample',21)]:assert sum(s['name']==name for s in j['spans'])==count
for p in [1,4,8]:
 arm={l:{r['iteration']:r for r in rows if r['p']==p and r['label']==l and r['iteration']!='warm'}for l in ['baseline','candidate']}
 for metric in ['elapsed_ms','wall_ms','cpu_ms']:
  rates=[100*(arm['candidate'][str(i)][metric]/arm['baseline'][str(i)][metric]-1)for i in range(5)]
  assert abs(st.median(rates)-summary[str(p)]['candidate_vs_baseline'][metric]['median_percent'])<1e-9
for label in ['baseline','candidate']:
 p=E/(label+'-runtime.log');text=p.read_text() if p.exists() else gzip.decompress(p.with_suffix('.log.gz').read_bytes()).decode();assert len(re.findall(r'^--- PASS: Test',text,re.M))==6
print('PASS: 36 processes, 2520 test spans, 720 writer forks, 756 sample spans; paired summary and 6 runtime tests per arm')
