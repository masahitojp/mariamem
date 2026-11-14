from pathlib import Path
import json,statistics
E=Path(__file__).resolve().parent;med=statistics.median
rows=json.loads((E/'records.json').read_text())
assert len(rows)==32 and all(r['code']==0 for r in rows)
for r in rows:
 n=r['name'];tr=json.loads((E/(n+'-trace.json')).read_text());sp=[v['end_ms']-v['start_ms']for v in tr['spans']if v['name']=='raw_insert'];assert len(sp)==8;r['raw_p50']=med(sp);r['raw_mean']=statistics.mean(sp)
 if r['arm']:
  mods=json.loads((E/(n+'-stages.json')).read_text());assert len(mods)==8
  es=[v for m in mods for v in m['records']];assert len(es)==800
  for v in es:assert v['Counts']==[1]*7 and v['TriggerDepth']==0 and 0<=v['TriggerNS']<=v['T'][4]-v['T'][3]
  r['sql']=sum(v['T'][4]-v['T'][3]for v in es)/8e6;r['trigger']=sum(v['TriggerNS']for v in es)/8e6;r['rest']=r['sql']-r['trigger'];r['calls']=sum(v['TriggerCalls']for v in es)/8
out={}
for p in [1,8]:
 group=[r for r in rows if r['phase']=='primary'and r['parallel']==p];d={}
 for mode in ['sum','incremental']:
  off=[r for r in group if r['mode']==mode and r['arm']==0];on=[r for r in group if r['mode']==mode and r['arm']==1]
  d[mode]={'off_raw_p50_median':med(r['raw_p50']for r in off),'off_raw_mean':statistics.mean(r['raw_mean']for r in off),'observer_paired_pct':[100*(a['raw_p50']/b['raw_p50']-1)for a,b in zip(on,off)]}
  for k in ['sql','trigger','rest','calls']:d[mode][k]=statistics.mean(r[k]for r in on)
 for arm in [0,1]:
  a=[r for r in group if r['mode']=='sum'and r['arm']==arm];b=[r for r in group if r['mode']=='incremental'and r['arm']==arm];d['paired_arm'+str(arm)]={k:[v[k]-u[k]for u,v in zip(a,b)]for k in (['raw_p50']if arm==0 else['raw_p50','sql','trigger','rest'])}
 out[p]=d
(E/'sum-summary.json').write_text(json.dumps(out,indent=2));(E/'sum-runs.json').write_text(json.dumps(rows,indent=2));print(json.dumps(out,indent=2))
