from pathlib import Path
import json,statistics as st,collections
E=Path(__file__).resolve().parent;rs=json.loads((E/'records.json').read_text());assert len(rs)==30
for r in rs:
 assert r['code']==0
 d=json.loads((E/(r['name']+'.json')).read_text());assert len([s for s in d['spans']if s['kind']in ['read','write']])==70
 r['suite_ms']=d['elapsed_ms'];r['sample_p50_ms']=st.median((s['end_ms']-s['start_ms'])for s in d['spans']if s['kind']=='sample')
summary={}
for p in [1,8]:
 arms=[[r for r in rs if r['parallel']==p and r['phase']=='primary' and r['arm']==a]for a in [0,1]];x={}
 for key in ['wall_ms','suite_ms','user_ms','system_ms','cpu_ms','sample_p50_ms']:
  v=[[r[key]for r in arm]for arm in arms];x[key]={'baseline':st.median(v[0]),'candidate':st.median(v[1]),'pairs':[[b,c]for b,c in zip(*v)],'paired_change_percent_p50':st.median((c/b-1)*100 for b,c in zip(*v)),'candidate_faster_pairs':sum(c<b for b,c in zip(*v))}
 summary[p]=x
counts=[]
for i in range(3):
 for arm in [0,1]:
  name=f'count-r{i}-a{arm}';fs=list((E/name).glob('*.json'));assert len(fs)==22
  cs={k:collections.Counter()for k in ['host_read','host_write','guest_read','guest_write']}
  for f in fs:
   d=json.loads(f.read_text());assert not d['exit_error'];ds=d['directions']
   for a,b in [('guest_write','host_read'),('host_write','guest_read')]:
    for k in ['bytes','frames']:assert ds[a][k]==ds[b][k],(f,a,b,k)
   for k in cs:
    for n in ['calls','frames','bytes']:cs[k][n]+=ds[k][n]
  counts.append({'round':i,'arm':arm,'counts':cs,'read_per_response':cs['host_read']['calls']/cs['host_read']['frames']})
out={'performance':summary,'counts':counts,'processes':len(rs),'test_bodies':len(rs)*70,'observed_dbs':132}
(E/'summary.json').write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))
