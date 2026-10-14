import json, statistics, collections
from pathlib import Path
w=Path(__file__).resolve().parents[1]; ev=w/'evidence'
rows=json.loads((ev/'campaign.json').read_text()); result=[]
for r in rows:
    if r['returncode'] or 'suite_product_seconds' not in r: continue
    d=json.loads((ev/(r['label']+'.json')).read_text())
    row={k:v for k,v in r.items() if k!='command'}
    phases=collections.defaultdict(lambda:{'wall_seconds':0.,'cpu_seconds':0.})
    for o in d['operations']:
        n=o['name']; phase=n.rsplit('_',1)[0] if n.rsplit('_',1)[-1].isdigit() else n
        phases[phase]['wall_seconds']+=o['seconds']; phases[phase]['cpu_seconds']+=o['cpu_seconds'] or 0
    row['phases']=dict(phases)
    ap=ev/(r['label']+'-audit.json')
    if ap.exists():
        a=json.loads(ap.read_text()); points={p['phase']:p for p in a['points']}; start,end=points['children_begin'],points['children_end']
        row['child_counter_delta']={k:end[k]-start[k] for k in start if k!='phase'}
        row['snapshot_point']=points['snapshot_after']; row['child_end_point']=end
        row['per_child']=[]
        for i in range(d['forks']):
            begin,finish=points[f'fork_ready_{i:02d}_before'],points[f'child_close_{i:02d}_after']
            row['per_child'].append({'child':i,'gc_delta':finish['/gc/cycles/automatic:gc-cycles']-begin['/gc/cycles/automatic:gc-cycles'],'heap_begin':begin['/memory/classes/heap/objects:bytes'],'heap_end':finish['/memory/classes/heap/objects:bytes'],'goal_begin':begin['/gc/heap/goal:bytes'],'goal_end':finish['/gc/heap/goal:bytes'],'live_begin':begin['/gc/heap/live:bytes'],'live_end':finish['/gc/heap/live:bytes'],'estimated_gc_cpu_seconds':finish['/cpu/classes/gc/total:cpu-seconds']-begin['/cpu/classes/gc/total:cpu-seconds'],'estimated_gc_idle_seconds':finish['/cpu/classes/gc/mark/idle:cpu-seconds']-begin['/cpu/classes/gc/mark/idle:cpu-seconds']})
    result.append(row)
(ev/'analysis.json').write_text(json.dumps(result,indent=2))
for r in result:
    a=r.get('child_counter_delta',{})
    print(r['label'], 'suite',round(r['suite_product_seconds'],3),'children',round(r['child_wall_seconds'],3),'gc',a.get('/gc/cycles/automatic:gc-cycles'),'gc-est',round(a.get('/cpu/classes/gc/total:cpu-seconds',0),4),'assist-est',round(a.get('/cpu/classes/gc/mark/assist:cpu-seconds',0),4),'scav-est',round(a.get('/cpu/classes/scavenge/assist:cpu-seconds',0)+a.get('/cpu/classes/scavenge/background:cpu-seconds',0),4))
summary=[]
for kind in ['off','metrics','cpu','trace']:
    groups={m:[r for r in result if r['kind']==kind and r['mode']==m] for m in ['original','direct']}
    if not all(groups.values()):continue
    row={'kind':kind}
    for m,rs in groups.items():
        row[m]={'n':len(rs)}
        for k in ['snapshot_seconds','prepare_seconds','child_wall_seconds','suite_product_seconds','suite_cpu_seconds']:
            vs=[r[k] for r in rs];row[m][k]={'median':statistics.median(vs),'min':min(vs),'max':max(vs)}
    summary.append(row)
(ev/'summary.json').write_text(json.dumps(summary,indent=2))
