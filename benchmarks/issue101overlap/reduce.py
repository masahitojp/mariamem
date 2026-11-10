"""Reduce fixed scheduling comparison into compact, replayable observations."""
from pathlib import Path
import csv
import hashlib
import json
import shutil

E=Path(__file__).resolve().parents[3]/'evidence'
D=E/'compact'
D.mkdir(exist_ok=True)
def save(name,v): (D/name).write_text(json.dumps(v,indent=2)+'\n')
def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
for n in ['inputs.json','host.json','runs.json','completion.json','build-controls.txt']:
    shutil.copyfile(E/n,D/n)
shutil.copyfile(E.parent/'worktree/benchmarks/issue101overlap/plan.json',D/'plan.json')
runs=json.loads((E/'runs.json').read_text()); trials=[]; childrows=[]; stages=[]
for r in runs:
    p=E/r['name']; data=json.loads((p/'result.json').read_text())
    trial=dict(r,**{k:data[k] for k in ['suite_ms','batch_ms','suite_cpu_ms','batch_cpu_ms','lifetime_max_rss_bytes','max_active','resolved_max_forks','success','cleanup','cleanup_stats']})
    trial['error']=data.get('error');trial['samples']=len(data['samples']);trial['oracles']=sum(s['oracle'] for s in data['samples']);trial['root_spans']=data['root_spans']
    trials.append(trial)
    for s in data['samples']:
        spans={x['name']:x for x in s['spans']}
        row=dict(run=r['name'],index=s['index'],lane=s['lane'],begin_ms=s['begin_ms'],end_ms=s['end_ms'],oracle=s['oracle'],cleanup=s['cleanup'],error=s.get('error',''))
        for name in ['start_or_fork','connect','version','select1','count_sum','update','verify_update','retire','close','fork_barrier','sql_barrier']:
            for edge in ['begin_ms','end_ms']:row[name+'_'+edge]=spans.get(name,{}).get(edge,'')
        childrows.append(row)
    for f in sorted((p/'traces').glob('child-*.json')) if (p/'traces').exists() else []:
        trace=json.loads(f.read_text()); stages.append(dict(run=r['name'],index=int(f.stem.split('-')[1]),trace=trace))
save('trials.json',trials)
with (D/'children.csv').open('w') as f:
    writer=csv.DictWriter(f,fieldnames=list(childrows[0]));writer.writeheader();writer.writerows(childrows)
save('stages.json',stages)
save('original-files-sha256.json',{str(p.relative_to(E)):digest(p) for p in sorted(E.rglob('*')) if p.is_file() and D not in p.parents})
print('Reduced',len(trials),'processes',len(childrows),'children',len(stages),'stage traces')
