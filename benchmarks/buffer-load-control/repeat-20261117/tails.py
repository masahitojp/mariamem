import json,statistics as st,subprocess
from pathlib import Path
e=Path(__file__).resolve().parent
rs=[r for r in json.loads((e/'records.json').read_text())if r['block']>=0]
out={'arms':{},'power_observations':{},'previous_campaign_power':'not recorded; user reports AC used in recent turns; do not infer battery baseline'}
for arm in ['ON','OFF']:
 rows=[r for r in rs if r['arm']==arm];med=st.median(r['elapsed_ms']for r in rows)
 flags=[r for r in rows if r['elapsed_ms']>med*1.2 or r['elapsed_ms']>500 or r['phases']['sample']['max_ms']>200]
 selected={r['name']:r for r in sorted(rows,key=lambda r:r['elapsed_ms'],reverse=True)[:3]+flags};details=[]
 for r in selected.values():
  spans=json.loads((e/'campaign'/(r['name']+'.json')).read_text())['spans'];details.append({'name':r['name'],'elapsed_ms':r['elapsed_ms'],'wall_ms':r['wall_ms'],'cpu_ms':r['cpu_ms'],'partition':r['partition'],'sample_max_ms':r['phases']['sample']['max_ms'],'longest_spans':sorted([x|{'duration_ms':x['end_ms']-x['start_ms']} for x in spans if x['name']not in ['suite_run','final_cleanup']],key=lambda x:x['duration_ms'],reverse=True)[:6],'final_cleanup':next(x for x in spans if x['name']=='final_cleanup'),'load_before':r['load_before'],'load_after':r['load_after'],'involuntary_switches':r['involuntary_switches']})
 out['arms'][arm]={'flagged':[r['name']for r in flags],'top_and_flagged':details,'sample_max_across_runs_ms':max(r['phases']['sample']['max_ms']for r in rows),'whole_above500':sum(r['elapsed_ms']>500 for r in rows),'sample_above200':sum(r['phases']['sample']['max_ms']>200 for r in rows)}
allrows=json.loads((e/'records.json').read_text());obs=[r[k]for r in allrows for k in ['power_before','power_after']]
out['power_observations']={'count':len(obs),'ac':sum("'AC Power'" in x['stdout']for x in obs),'errors':sum(x['returncode']!=0 for x in obs),'different':list({x['stdout']for x in obs})}
(e/'tails.json').write_text(json.dumps(out,indent=2))
prev=json.loads(subprocess.check_output(['git','show','a0b61c8a:benchmarks/buffer-load-control/evidence/summary.json']))
now=json.loads((e/'summary.json').read_text())
print(json.dumps({'previous':{k:prev[k]for k in ['paired','aa']},'repeat':{k:now[k]for k in ['paired','aa']},'tails':out},indent=2))
