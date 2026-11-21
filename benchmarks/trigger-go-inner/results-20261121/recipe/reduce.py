"""Sum disjoint wall-clock intervals first, compare paired A/B blocks second."""
from collections import defaultdict
import csv
import gzip
import json
from pathlib import Path
from statistics import mean
import sys
from campaign import MODES,validate

def write(p,rows):
    with p.open('w',newline='') as f:
        out=csv.DictWriter(f,fieldnames=rows[0].keys(),lineterminator='\n')
        out.writeheader()
        for r in rows: out.writerow({k:round(v,7) if isinstance(v,float) else v for k,v in r.items()})
def run(dst):
    sites=json.loads((dst/'recipe/sites.json').read_bytes())
    phases=['dispatch']+[s['label'] for s in sites if s['kind']=='phase']
    mem=['outside_memory_hooks']+[s['label'] for s in sites if s['kind']=='mem']
    order_pos=[j+1 for o in range(1,41) for j in range(1+(o%4))]
    assert len(order_pos)==100
    result={}; controls=[]; cross=[]; fields=[]; bypos=[]; checks=[]
    for b in range(5):
        for sql in 'ABC':
            for mode in MODES:
                prefix=dst/'runs'/f'{b}-{sql}-{mode}'
                out=[json.loads(l) for l in prefix.with_suffix('.jsonl').read_text().splitlines()]
                cohorts=out[1:]
                assert len(cohorts)==(12 if b else 1) and len(out[0]['registered'])==(4 if sql=='C' else 5)
                assert all(r['db']==i and r['inserts']==100 and r['close']=='pass' for i,r in enumerate(cohorts))
                if mode!='base':
                    batches=json.loads(gzip.decompress(prefix.with_suffix('.json.gz').read_bytes()))
                    validate(batches,cohorts,sql,mode)
                if not b:continue
                rows=[r for g in batches[2:] for r in g] if mode!='base' else []
                n=10;den=n*1e6
                wall=mean(g['raw_ns'] for g in cohorts[2:])/1e6
                outer=sum(r['TriggerNS'] for r in rows)/den if rows else None
                result[b,sql,mode]=dict(raw=wall,trigger=outer)
                if not rows or mode=='outer':continue
                mat=[[0]*len(mem) for _ in phases]
                calls=[[0]*len(mem) for _ in phases]
                pc=[0]*len(phases); refills=pc.copy(); requested=pc.copy()
                count=defaultdict(int); nspos=defaultdict(float); addpos=defaultdict(int)
                sums=defaultdict(int)
                mem_scopes=defaultdict(int)
                for r in rows:
                    x=r['Inner']
                    for i,label in enumerate(phases):
                        for j,k in enumerate(mem):
                            mat[i][j]+=x['NS'][i][j];calls[i][j]+=x['MemCalls'][i][j]
                        pc[i]+=x['PhaseCalls'][i]; refills[i]+=x['ArenaRefills'][i];requested[i]+=x['MallocBytes'][i]
                    sq,upd,both=x['SubtreeNS']
                    sums['subquery_join']+=sq
                    sums['update_outside_subquery']+=upd-both
                    sums['other_trigger']+=r['TriggerNS']-sq-(upd-both)
                    sub_mem,upd_mem,both_mem=(sum(cols[1:]) for cols in x['SubtreeMem'])
                    total_mem=sum(sum(cols[1:]) for cols in x['NS'])
                    mem_scopes['memory_in_subquery_join']+=sub_mem
                    mem_scopes['memory_in_update_outside_subquery']+=upd_mem-both_mem
                    mem_scopes['memory_in_other_trigger']+=total_mem-sub_mem-upd_mem+both_mem
                    pos=order_pos[r['Ordinal']]
                    nspos[pos]+=sq;addpos[pos]+=x['PhaseCalls'][11];count[pos]+=1
                assert sum(sums.values())==sum(sum(a) for a in mat)==sum(r['TriggerNS'] for r in rows)
                for i,label in enumerate(phases):
                    fields.append(dict(block=b,sql=sql,mode=mode,phase=label,ms100=sum(mat[i])/den,
                                       calls100=pc[i]/n,memory_ms100=sum(mat[i][1:])/den,
                                       dlmalloc_ms100=mat[i][4]/den,dlmalloc_calls100=calls[i][4]/n,
                                       dlmalloc_bytes100=requested[i]/n,arena_refill_calls100=refills[i]/n))
                    if mode=='detail':
                        for j,k in enumerate(mem):
                            cross.append(dict(block=b,sql=sql,phase=label,memory=k,ms100=mat[i][j]/den,calls100=calls[i][j]/n))
                metrics={**{k:v/den for k,v in sums.items()},**{p:sum(mat[i])/den for i,p in enumerate(phases)}}
                metrics.update({k:sum(row[j] for row in mat)/den for j,k in enumerate(mem) if j})
                metrics['all_memory_hooks']=sum(sum(row[1:]) for row in mat)/den
                assert sum(mem_scopes.values())==sum(sum(row[1:]) for row in mat)
                if mode=='detail':
                    metrics.update({k:v/den for k,v in mem_scopes.items()})
                metrics['trigger_total']=outer
                result[b,sql,mode].update(metrics)
                for p in range(1,5):
                    bypos.append(dict(block=b,sql=sql,mode=mode,position=p,inserts=count[p],
                                      subquery_us_per_insert=nspos[p]/count[p]/1000,
                                      sum_add_calls_per_insert=addpos[p]/count[p]))
    for b in range(1,5):
        for s in 'ABC':
            rs=[result[b,s,m] for m in MODES]
            controls.append(dict(block=b,sql=s,**{m+'_raw_ms100':r['raw'] for m,r in zip(MODES,rs)},
                **{m+'_trigger_ms100':r['trigger'] for m,r in zip(MODES[1:],rs[1:])},
                phase_outer_trigger_pct=100*(rs[2]['trigger']/rs[1]['trigger']-1),
                detail_phase_trigger_pct=100*(rs[3]['trigger']/rs[2]['trigger']-1)))
    summary=[]
    for mode in ('phase','detail'):
        for k in result[1,'A',mode]:
            vs={s:[result[b,s,mode][k] for b in range(1,5)] for s in 'ABC'}
            gaps=[a-b for a,b in zip(vs['A'],vs['B'])]
            summary.append(dict(mode=mode,metric=k,**{s:mean(v) for s,v in vs.items()},A_minus_B=mean(gaps),
                                min_gap=min(gaps),max_gap=max(gaps)))
    write(dst/'summary.csv',summary);write(dst/'phases.csv',fields);write(dst/'memory-cross.csv',cross)
    write(dst/'observer.csv',controls);write(dst/'item-position.csv',bypos)
if __name__=='__main__':run(Path(sys.argv[1]))
