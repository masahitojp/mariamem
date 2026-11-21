import csv,gzip,json,statistics as stat
from collections import Counter,defaultdict
from pathlib import Path
e=Path('evidence')
trials=[];phases=[]
def write(name,rows):
    with (e/name).open('w') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
for f in sorted((e/'runs').glob('*.json.gz')):
    role,b,pos,arm,p=f.name.split('.')[0].replace('-diag-p','_diag-p').split('-')
    if role not in ('base','diag'):continue
    tr=json.loads(gzip.decompress(f.read_bytes()))
    vals=Counter()
    for s in tr['spans']:vals[s['kind']]+=s['end_ms']-s['start_ms']
    engine=arm.split('_')[0]
    trials.append(dict(role=role,block=int(b),engine=engine,total=tr['elapsed_ms'],**{k:vals[k] for k in ('sample','fork','import','boot','snapshot','close','read','write')}))
    if role=='diag':
        means=[sum(col)/21e6 for col in zip(*tr['phase_ns'])]
        phases.append(dict(block=int(b),engine=engine,begin=means[0],prepare=means[1],orders=means[2],items=means[3],stock=means[4],commit=means[5],other=vals['sample']/21-sum(means),sample=vals['sample']/21))
write('trials.csv',trials);write('seed.csv',phases)
def summarize(rows,keys):
    out=[]
    for key in keys:
        groups={engine:[float(r[key]) for r in sorted(rows,key=lambda x:x['block']) if r['engine']==engine] for engine in ('maria','pg')}
        a,b=groups.values();assert len(a)==len(b)==6
        out.append(dict(phase=key,maria=stat.median(a),pg=stat.median(b),paired_gap=stat.median([x-y for x,y in zip(a,b)])))
    return out
write('suite-summary.csv',summarize([r for r in trials if r['role']=='base'],['total','sample','fork','read','write','close','boot','import','snapshot']))
write('seed-summary.csv',summarize(phases,['sample','orders','items','stock','prepare','begin','commit','other']))
