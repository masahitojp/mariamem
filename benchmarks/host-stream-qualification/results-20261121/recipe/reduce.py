from pathlib import Path
from statistics import mean,median
import csv,json,sys
p=Path(sys.argv[1]);out=p/'runs'
metrics={'wall_ms':('wall_ns',1e6),'cpu_ms':('cpu_ns',1e6),'allocated_MiB':('allocated_bytes',2**20),'heap_ready_MiB':('live_heap_before',2**20),'rss_highwater_MiB':('peak_rss_bytes',2**20)}
def save(path,rows):
    with path.open('w') as f:
        w=csv.DictWriter(f,fieldnames=rows[0],lineterminator='\n');w.writeheader();w.writerows(rows)
pairs=[];summary=[];waves=0;workers=0;db_count=0;ops=0
assert len(list(out.iterdir()))==70
for work in ('A','B','C','mixed','large'):
    workpairs=[]
    for b in range(7):
        values={}
        for mode in ('os','both'):
            rows=[json.loads(l) for l in (out/f'{b}-{work}-{mode}.jsonl').read_text().splitlines()]
            assert len(rows)==(6 if b else 1) and all(r['wave']==i and r['workers']==8 and r['all_workers_closed'] for i,r in enumerate(rows))
            for k,_ in metrics.values():assert all(r[k]>0 for r in rows)
            waves+=len(rows);workers+=8*len(rows);db_count+=(8 if work in ('A','B','C') else 1)*len(rows)
            ops+=(96 if work=='large' else 800)*len(rows)
            if not b: continue
            values[mode]={k:(max(r[v] for r in rows) if k=='rss_highwater_MiB' else mean(r[v] for r in rows[1:]))/factor for k,(v,factor) in metrics.items()}
        if b:
            for m in metrics:
                a=values['os'][m];v=values['both'][m]
                row=dict(work=work,block=b,metric=m,os=a,both=v,saved=a-v,pct=100*(a-v)/a)
                workpairs.append(row);pairs.append(row)
    for m in metrics:
        ds=[r for r in workpairs if r['metric']==m];pct=[r['pct'] for r in ds]
        summary.append(dict(work=work,metric=m,os_mean=mean(r['os'] for r in ds),both_mean=mean(r['both'] for r in ds),
            median_saved=median(r['saved'] for r in ds),median_pct=median(pct),min_pct=min(pct),max_pct=max(pct),positive=sum(v>0 for v in pct),slower_by_5=sum(v<=-5 for v in pct)))
save(p/'pairs.csv',pairs);save(p/'summary.csv',summary)
counts=dict(processes=70,waves=waves,workers=workers,workload_databases=db_count,sql_operations=ops)
assert waves==370 and workers==2960 and db_count==1924
(p/'verification.json').write_text(json.dumps(counts,indent=2)+'\n')
