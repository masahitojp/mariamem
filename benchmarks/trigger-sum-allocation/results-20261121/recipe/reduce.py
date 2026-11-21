"""Validate the capture and reduce the fixed direct call path by process."""
from collections import Counter,defaultdict
import csv
import gzip
import json
import math
from pathlib import Path
import statistics
import sys

from campaign import verify

def write(path,rows):
    with path.open('w',newline='') as f:
        out=csv.DictWriter(f,fieldnames=rows[0].keys(),lineterminator='\n')
        out.writeheader()
        out.writerows(rows)

def percentile(vals,p):
    return sorted(vals)[math.ceil(len(vals)*p)-1]

def main():
    dest=Path(sys.argv[1])
    summary, transitions, calibration, arena = [],[],[],[]
    for p in sorted((dest/'runs').glob('*.json.gz')):
        name=p.name.split('.')[0]
        d=json.loads(gzip.decompress(p.read_bytes()))
        verify(d)
        c=d['Controls']
        tick_ns=c['Numer']/c['Denom']
        byname={k:[(r['Before'],r['After']) for r in rows] for k,rows in c['Rows'].items()}
        assert all(x==(0,0) for x in byname['anonymous_empty'])
        assert all(x[0]==0 and x[1]&9==9 for x in byname['anonymous_first'])
        assert all(x[0]&128 and x[1]&32 and not x[1]&128 for x in byname['file_first'])
        for key,rows in c['Rows'].items():
            for (before,after),n in Counter(byname[key]).items():
                vals=[r['Ticks']*tick_ns for r in rows if (r['Before'],r['After'])==(before,after)]
                calibration.append(dict(run=name,control=key,before=before,after=after,n=n,
                    median_ns=round(statistics.median(vals),2),p95_ns=round(percentile(vals,.95),2)))
        oracle=[json.loads(line) for line in (dest/'runs'/(name+'.jsonl')).read_text().splitlines()]
        assert len(oracle[0]['registered'])=={'A':5,'B':5,'C':4}[name[-1]]
        assert [(r['db'],r['inserts'],r['close']) for r in oracle[1:]]==[(i,100,'pass') for i in range(8)]
        for mode in ['queried','timer_only']:
            reqs=[r for r in d['Requests'] if (mode=='queried')==(r['DB'] in (0,3,5,6))]
            counts=Counter()
            pages=set()
            transitions_ns=defaultdict(list)
            downstream=Counter()
            guests=[]
            for req in reqs:
                events=req['Events'] or []
                path=[e for e in events if e['Plan'] and e['SameArena'] and e['Kind'] in ('root','dlmalloc')]
                refills=[(i,e) for i,e in enumerate(path) if e['Kind']=='dlmalloc']
                if name[-1]=='A':
                    assert len(refills)==1
                    pos,refill=refills[0]
                    assert refill['DL']==8176
                    if req['Ordinal']==0:
                        assert [e['Root'] for e in path[:pos]]==[8,8,44,8] and not refill['Possible']
                    else:
                        assert pos==1 and refill['Site']=='string'
                else:
                    assert not refills
                for i,e in enumerate(events):
                    kind=e['Kind']
                    if kind=='plan': counts['plans']+=1
                    if kind=='store': counts['all_store']+=1
                    if kind=='dlmalloc' and e['SameArena'] and e['Plan']:
                        counts['plan_dl']+=1
                        if not e['Possible']: counts['other_plan_dl']+=1
                    if not e['Possible']: continue
                    assert e['Key']=='PRIMARY'
                    if kind=='append': counts['append']+=1
                    elif kind in ('root','dlmalloc','store'):
                        assert e['SameArena'] and e['Root']==8
                        counts[(kind,e['Site'])]+=1
                        if kind=='dlmalloc':
                            assert (e['My'],e['Wrap'],e['DL'])==(8160,8176,8176)
                        if kind=='store':
                            assert e['Site']=='string' and (e['My'],e['Wrap'],e['DL'])==(8160,8176,8176)
                            pages.add((req['DB'],e['HostPage']))
                            guests.append(e['Guest'])
                            transitions_ns[e['Before'],e['After']].append(e['Ticks']*tick_ns)
                            suffix=[]
                            for other in events[i+1:]:
                                if other['Kind']=='plan': break
                                if other['Kind']=='root' and other['Arena']==e['Arena'] and other['SameArena']:
                                    suffix.append(str(other['Root'])+'@'+(other['Site'] or 'other'))
                            downstream[tuple(suffix)]+=1
            vals=[v for vs in transitions_ns.values() for v in vs]
            summary.append(dict(run=name,mode=mode,inserts=len(reqs),plans=counts['plans'],
                append=counts['append'],root_string=counts['root','string'],root_node=counts['root','list_node'],
                plan_arena_dl=counts['plan_dl'],other_plan_dl=counts['other_plan_dl'],
                dl_string=counts['dlmalloc','string'],dl_node=counts['dlmalloc','list_node'],
                store=counts['store','string'],all_sql_store=counts['all_store'],
                unique_db_pages=len(pages),guest_min=min(guests,default=''),guest_max=max(guests,default=''),
                store_us_per_100=round(sum(vals)/1000/(len(reqs)/100),3),
                store_median_ns=round(statistics.median(vals),2) if vals else '',
                store_p95_ns=round(percentile(vals,.95),2) if vals else ''))
            for (before,after),vs in transitions_ns.items():
                transitions.append(dict(run=name,mode=mode,before=before,after=after,n=len(vs),
                    median_ns=round(statistics.median(vs),2),p95_ns=round(percentile(vs,.95),2),
                    us_per_100=round(sum(vs)/1000/(len(reqs)/100),3)))
            for sequence,n in downstream.items():
                arena.append(dict(run=name,mode=mode,narrow_stores=n,later_same_arena_root_requests=' '.join(sequence)))
    for name,rows in [('summary',summary),('transitions',transitions),('calibration',calibration),('arena',arena)]:
        write(dest/(name+'.csv'),rows)
if __name__=='__main__':
    main()
