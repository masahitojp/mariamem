from pathlib import Path
import json,statistics
E=Path(__file__).resolve().parent;out={}
for p in [1,8]:
 a=[]
 for i in range(3):
  obs=json.loads((E/f'p{p}-r{i}-a1-stages.json').read_text())
  for m in obs:
   rs=m['records'];sql=sum(r['T'][4]-r['T'][3]for r in rs)/1e6;trigger=sum(r['TriggerNS']for r in rs)/1e6
   a.append({'sql_ms':sql,'trigger_ms':trigger,'rest_ms':sql-trigger,'calls':sum(r['TriggerCalls']for r in rs)})
 out[p]={k:statistics.mean(r[k]for r in a)for k in a[0]};out[p]['dbs']=len(a);out[p]['trigger_pct']=out[p]['trigger_ms']/out[p]['sql_ms']*100
(E/'trigger-summary.json').write_text(json.dumps(out,indent=2));print(json.dumps(out,indent=2))
