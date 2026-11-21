from pathlib import Path
import collections,csv,gzip,json,statistics as stats
e=Path('evidence')
rows=[];summary=[]
for p in (1,8):
    current=[]
    for b in range(1,7):
        order=('normal','pgo','normal') if b%2 else ('pgo','normal','pgo')
        elapsed=[];sample=[];fork=[]
        for i,a in enumerate(order):
            data=json.loads(gzip.decompress((e/'runs'/f'candidate-{b}-{i}-{a}-p{p}.json.gz').read_bytes()))
            elapsed.append(data['elapsed_ms'])
            for name,array in [('sample',sample),('fork',fork)]:
                spans=[s for s in data['spans'] if s['kind']==name];assert len(spans)==21
                array.append(sum(s['end_ms']-s['start_ms'] for s in spans))
        def avg(vals,arm):return stats.mean(v for v,a in zip(vals,order) if a==arm)
        normal,pgo=[avg(elapsed,a) for a in ('normal','pgo')]
        r=dict(p=p,block=b,order='/'.join(order),normal_ms=normal,pgo_ms=pgo,saved_ms=normal-pgo,noise_ms=abs(elapsed[0]-elapsed[2]),normal_max=max(v for v,a in zip(elapsed,order) if a=='normal'),pgo_max=max(v for v,a in zip(elapsed,order) if a=='pgo'),sample_delta=avg(sample,'normal')-avg(sample,'pgo'),fork_delta=avg(fork,'normal')-avg(fork,'pgo'))
        current.append(r);rows.append(r)
    def values(k):return [r[k] for r in current]
    delta=stats.median(values('saved_ms'));noise=stats.median(values('noise_ms'))
    summary.append(dict(p=p,normal_median=stats.median(values('normal_ms')),pgo_median=stats.median(values('pgo_ms')),paired_ms=delta,noise_ms=noise,positive=sum(v>0 for v in values('saved_ms')),normal_total=sum(values('normal_ms')),pgo_total=sum(values('pgo_ms')),normal_max=max(values('normal_max')),pgo_max=max(values('pgo_max')),sample_delta=stats.median(values('sample_delta')),fork_delta=stats.median(values('fork_delta')),threshold=delta>=50 and delta>noise))
for name,data in [('candidate-pairs',rows),('candidate-summary',summary)]:
    with (e/(name+'.csv')).open('w') as f:
        wr=csv.DictWriter(f,fieldnames=data[0],lineterminator='\n');wr.writeheader();wr.writerows(data)
print(summary)
