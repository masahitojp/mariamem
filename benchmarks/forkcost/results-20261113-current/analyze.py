from pathlib import Path
import json,statistics as s,csv,io
E=Path(__file__).resolve().parent
def ev(t):return {x['name']:x['offset_ns']/1e6 for x in t['events']}
def phases(c):
 h=ev(c['traces']['startup']);g=ev(c['traces']['startup']['guest']);a=lambda x,y:h[y]-h[x];b=lambda x,y:g[y]-g[x]
 d=dict(host_setup=c['fork_ms']-h['end']+h['runtime/instance_begin'],filesystem=a('runtime/instance_begin','runtime/prepared_handles_ready'),image_module=a('runtime/prepared_handles_ready','runtime/guest_execute_begin'),server_init=b('server_init_begin','server_init_complete'),bootstrap=b('server_init_complete','routine_schema_begin'),routine_schema=b('routine_schema_begin','routine_schema_complete'),guest_other=b('guest_main','ready_prepared')-b('server_init_begin','server_init_complete')-b('server_init_complete','routine_schema_begin')-b('routine_schema_begin','routine_schema_complete'),execution_residual=a('runtime/guest_execute_begin','ready_response_observed')-b('guest_main','ready_prepared'),post_ready=a('ready_response_observed','end'))
 assert min(d.values())>=-.1 and abs(sum(d.values())-c['fork_ms'])<1e-6
 return d
summary={};rows=[]
for p in (1,8):
 for t in (0,1):
  ds=[json.loads((E/f'runs/main-p{p}-r{r}-t{t}.json').read_text()) for r in range(3)]
  assert all(d['success'] and len(d['children'])==48 for d in ds)
  cs=[c for d in ds for c in d['children']];assert all(c['oracle'] and c['closed'] for c in cs)
  v=sorted(c['fork_ms'] for c in cs)
  out={'n':len(v),'mean_ms':s.mean(v),'p50_ms':s.median(v),'p95_ms':v[int(.95*(len(v)-1))],'process_p50_ms':[s.median(c['fork_ms'] for c in d['children']) for d in ds]}
  if t:
   ps=[phases(c) for c in cs];out['stage_mean_ms']={k:s.mean(d[k] for d in ps) for k in ps[0]}
   assert abs(sum(out['stage_mean_ms'].values())-out['mean_ms'])<1e-6
  summary[f'p{p}-t{t}']=out
  for r,d in enumerate(ds):
   for c in d['children']:rows.append(dict(p=p,traced=t,repetition=r,index=c['index'],fork_ms=c['fork_ms'],**(phases(c) if t else {})))
(E/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
b=io.StringIO();w=csv.DictWriter(b,fieldnames=list(dict.fromkeys(k for r in rows for k in r)));w.writeheader();w.writerows(rows);(E/'children.csv').write_text(b.getvalue())
print(json.dumps(summary,indent=2))
