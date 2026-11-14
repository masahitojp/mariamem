from pathlib import Path
import json,statistics,sys
D=Path(sys.argv[1]);rs=json.loads((D/'records.json').read_text());assert len(rs)==19 and all(r['code']==0 for r in rs);out={}
for p in [1,8]:
 group=[r for r in rs if r['p']==p and not r['profile']and 'warm'not in r['name']];arms={}
 for a in [0,1]:
  rows=[r for r in group if r['arm']==a]
  for r in rows:
   spans=json.loads((D/(r['name']+'-trace.json')).read_text())['spans'];r['raw_p50']=statistics.median(s['end_ms']-s['start_ms']for s in spans if s['name']=='raw_insert')
  arms[a]=rows
 out[p]={'off_raw_p50':statistics.median(r['raw_p50']for r in arms[0]),'on_raw_p50':statistics.median(r['raw_p50']for r in arms[1]),'observer_paired_pct':[100*(a['raw_p50']/b['raw_p50']-1)for a,b in zip(arms[1],arms[0])]}
 reduced=[json.loads((D/(r['name']+'-reduced.json')).read_text())for r in arms[1]];out[p]['on_means']={k:statistics.mean(r[k]for r in reduced)for k in reduced[0]}
for i in range(3):
 assert len(list((D/f'profile-{i}').glob('*.pprof')))==8
 assert (D/f'profile-{i}.txt').read_text().count('PASS raw=true')==64
(D/'summary.json').write_text(json.dumps(out,indent=2));print('SUMMARY/PROFILE COUNTS PASS')
