from pathlib import Path
import json,statistics as st,re,gzip
E=Path(__file__).resolve().parent
def read(p):return p.read_text() if p.exists() else gzip.decompress(p.with_suffix(p.suffix+'.gz').read_bytes()).decode()
rows=json.loads(read(E/'records.json'));s=json.loads(read(E/'summary.json'));assert len(rows)==54 and len({r['name']for r in rows})==54
for r in rows:
 j=json.loads(read(E/'campaign'/(r['name']+'.json')));assert r['code']==0 and j['elapsed_ms']==r['elapsed_ms']
 for k,n in [('test',70),('fork',20),('sample',21)]:assert sum(x['name']==k for x in j['spans'])==n
for p in [1,4,8]:
 by={l:{r['iteration']:r for r in rows if r['p']==p and r['label']==l and r['iteration']!='warm'}for l in ['baseline','direct','noinline']}
 for a,b in [('baseline','direct'),('baseline','noinline'),('direct','noinline')]:
  for key in ['elapsed_ms','wall_ms','cpu_ms']:
   rates=[100*(by[b][str(i)][key]/by[a][str(i)][key]-1)for i in range(5)];assert abs(st.median(rates)-s[str(p)][b+'_vs_'+a][key]['median_percent'])<1e-9
for l in ['baseline','direct','noinline']:
 text=read(E/(l+'-runtime.txt'));assert len(re.findall(r'^--- PASS: Test',text,re.M))==6
 text=read(E/(l+'-base-tests.txt'));assert '\nPASS\n' in text and '--- FAIL:' not in text
assert json.loads(read(E/'stage1.json'))['status']=='PASS'
print('PASS: stage1, three arms base/runtime; 54 processes, 3780 test/1080 writerFork/1134 sample spans; all paired statistics')
