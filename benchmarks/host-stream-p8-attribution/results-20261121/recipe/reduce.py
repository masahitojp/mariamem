"""Account for the full elapsed time of every sample with nonoverlapping intervals."""
import csv,gzip,json,statistics,sys,tarfile
from collections import Counter,defaultdict
from pathlib import Path
out=Path(sys.argv[1]).resolve()
def dump(name,data):
    (out/name).write_text(json.dumps(data,indent=2)+'\n')
def table(name,rows):
    if not rows:return
    with (out/name).open('w',newline='') as f:
        wr=csv.DictWriter(f,fieldnames=rows[0],lineterminator='\n');wr.writeheader();wr.writerows(rows)
def ms(n):return round(n/1e6,4)
summaries=[]; allsamples=[]; tails=[];series=defaultdict(list)
phases=['admission','send_schedule','request_transfer','dispatch','worker','serialize','response_transfer','body','decode_notify','caller_resume']
stamps='Call Queue Write Input Worker Reply Output Header Body Notify Resume'.split()
def observations():
    archive=out/'observations.tar.xz'
    if archive.exists():
        with tarfile.open(archive,'r|xz') as tar:
            for member in tar:
                yield member.name,json.load(tar.extractfile(member))
    else:
        for file in sorted((out/'runs').glob('*.json.gz')):
            yield file.name[:-3],json.loads(gzip.decompress(file.read_bytes()))
for name,r in observations():
    file=Path(name)
    suite=r['suite']; sp=[s for s in suite['spans'] if s['kind']=='sample']
    assert len(sp)==21
    diag='requests' in r
    offset=int(suite['meta'].get('probe_ns',0))
    meta={k:r[k] for k in ('series','block','position','arm')}
    slow=0;longest=0
    for s in sp:
        lane=s['lane']; start=offset+round(s['start_ms']*1e6);end=offset+round(s['end_ms']*1e6)
        length=end-start;longest=max(longest,length);slow+=int(length>=400_000_000)
        row=dict(**meta,lane=lane,elapsed_ms=ms(length),requests=None,**{k:None for k in phases+['outside_call','overlap']})
        if diag:
            req=[dict(zip(r['request_columns'],a)) for a in r['requests'][lane]]
            req=[a for a in req if a['Call']<end and a['Resume']>start]
            assert req,(file,lane)
            events=defaultdict(list);events[start];events[end]
            byid={a['ID']:a for a in req}
            for a in req:
                ts=[a[k] for k in stamps]
                assert min(ts)>0 and ts==sorted(ts),(file,lane,a)
                for phase,left,right in zip(phases,ts,ts[1:]):
                    left=max(start,left);right=min(end,right)
                    if right>left:
                        events[left].append((1,phase,a['ID']))
                        events[right].append((-1,phase,a['ID']))
            intervals=[];active=set();prev=start;totals=Counter()
            for tm,changes in sorted(events.items()):
                if tm>prev:
                    (phase,rid)=next(iter(active)) if len(active)==1 else ('overlap' if active else 'outside_call',0)
                    totals[phase]+=tm-prev
                    intervals.append((tm-prev,phase,rid,prev,tm))
                for sign,phase,rid in sorted(changes):
                    if sign<0:active.remove((phase,rid))
                    else:active.add((phase,rid))
                prev=tm
            assert not active and sum(totals.values())==length
            row.update(requests=len(req),**{k:ms(totals[k]) for k in phases+['outside_call','overlap']})
            if length>=400_000_000:
                hot=[]
                for ns,phase,rid,left,right in sorted(intervals,reverse=True)[:5]:
                    ops=sorted(((min(right,o['End'])-max(left,o['Start']),i,o) for i,o in enumerate(r['clients'][lane])),key=lambda v:-v[0])
                    hit,i,op=ops[0]
                    hot.append(dict(phase=phase,id=rid,interval_ms=ms(ns),start=left,end=right,client_op=op['Op'] if hit>0 else None,
                        client_index=i if hit>0 else None,op_overlap_ms=ms(max(hit,0)),row=byid.get(rid)))
                tails.append(dict(file=file.stem,lane=lane,sample=row,intervals=hot))
        allsamples.append(row)
    summary=dict(**meta,suite_ms=suite['elapsed_ms'],cpu_ms=round(r['cpu_ms'],4),longest_sample_ms=ms(longest),tail_samples=slow)
    summaries.append(summary);series[(r['series'],r['arm'])].append(summary)
table('samples.csv',allsamples);table('suites.csv',summaries);dump('tails.json',tails)
stats=[]
for (group,arm),rows in sorted(series.items()):
    stats.append(dict(series=group,arm=arm,runs=len(rows),tail_runs=sum(v['tail_samples']>0 for v in rows),tail_samples=sum(v['tail_samples'] for v in rows),
        suite_median_ms=round(statistics.median(v['suite_ms'] for v in rows),2),median_max_sample_ms=round(statistics.median(v['longest_sample_ms'] for v in rows),2),
        max_sample_ms=max(v['longest_sample_ms'] for v in rows)))
table('summary.csv',stats)
