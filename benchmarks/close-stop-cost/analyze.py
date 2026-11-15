import json,statistics
from pathlib import Path
runs=[json.loads(x) for x in (Path(__file__).parent/'runs.jsonl').read_text().splitlines()]
phases={'admission':('close_begin','admission_stopped'),'sessions':('admission_stopped','sessions_joined'),'open':('rpc_1_begin','rpc_1_end'),'set':('rpc_2_begin','rpc_2_end'),'session_close':('rpc_3_begin','rpc_3_end'),'configuration':('rpc_1_begin','rpc_3_end'),'shutdown_to_stopped':('shutdown_begin','transport_workers_stopped'),'precleanup':('close_begin','transport_workers_stopped'),'cleanup_tail':('transport_workers_stopped','backend_cleanup_end')}
summary=[]
for r in runs:
 if r['phase']!='diagnostic':continue
 children={}
 for e in r['events']: children.setdefault(e['id'],{})[e['kind']]=e['ns']
 assert len(children)==48 and not r['failures']
 values={k:[(c[b]-c[a])/1e6 for c in children.values()] for k,(a,b) in phases.items()}
 row={'p':r['p'],'repeat':r['pair'],'batch_ms':r['batch_drain_ms'],'phases':{k:{'mean_ms':statistics.mean(v),'p50_ms':statistics.median(v),'max_ms':max(v)} for k,v in values.items()}}
 summary.append(row)
print(json.dumps(summary,indent=2))
