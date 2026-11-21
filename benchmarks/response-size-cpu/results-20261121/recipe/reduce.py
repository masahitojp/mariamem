import csv,statistics
from pathlib import Path
out=Path('evidence')
def rows(name):
    return list(csv.DictReader((out/(name+'.csv')).open()))
r=rows('perf')+rows('wire-perf')
d=rows('diag')+rows('wire-diag')
assert len(r)==180 and len(d)==20
summary=[]
for size in sorted({int(t["size"]) for t in r}):
    pairs=[{t['arm']:t for t in r if int(t['size'])==size and int(t['block'])==b} for b in range(1,7)]
    os_probe,ring_probe=sorted((t for t in d if int(t['size'])==size),key=lambda t:t['arm'])
    wire=float(ring_probe['wire-read-B'])
    assert wire==float(os_probe['wire-read-B'])==float(ring_probe['wire-write-B'])==float(os_probe['wire-write-B'])
    assert float(ring_probe['copy-B'])==wire*2
    record={'payload':size,'wire_B_per_request':round(wire/96,2),'full_waits':int(float(ring_probe['full-waits']))}
    for field,prefix in [('cpu-ns/op','cpu'),('ns/op','wall')]:
        pct=[];noise=[]
        for pair in pairs:
            os,os2,ring=[float(pair[a][field]) for a in ('os','os2','ring')]
            pct.append(100*(ring/os-1))
            noise.append(abs(100*(os2/os-1)))
        record[prefix+'_pct']=round(statistics.median(pct),3)
        record[prefix+'_os_noise_pct']=round(statistics.median(noise),3)
        record[prefix+'_positive']=sum(d>0 for d in pct)
    summary.append(record)
with (out/'summary.csv').open('w') as f:
    wr=csv.DictWriter(f,fieldnames=summary[0],lineterminator="\n");wr.writeheader();wr.writerows(summary)
