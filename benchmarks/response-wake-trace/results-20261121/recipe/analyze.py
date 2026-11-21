"""Decode standard Go 1.27 parsed traces, matching state transitions by goroutine ID."""
import bisect,collections,csv,gzip,math,re,sys
from pathlib import Path

root=Path('evidence')
header=re.compile(r'M=(-?\d+) P=(-?\d+) G=(-?\d+) (\w+) Time=(\d+)(.*)')
state=re.compile(r'GoID=(\d+) (\w+)->(\w+)')
def events(path):
    with path.open() as f:
        head=None;detail=[]
        for line in f:
            if line.startswith('M='):
                if head:yield head,''.join(detail)
                head=header.match(line).groups();detail=[]
            else:detail.append(line)
        if head:yield head,''.join(detail)
def csv_out(name,rows):
    path=root/name
    with (gzip.open(path,'wt') if name.endswith('.gz') else path.open('w')) as f:
        wr=csv.DictWriter(f,fieldnames=rows[0],lineterminator='\n');wr.writeheader();wr.writerows(rows)
def quant(v,p):
    return sorted(v)[max(0,math.ceil(p*len(v))-1)]/1000 if v else None
summary=[];overlaps=[];allrows=[];osrows=[];reader_states=[]
for path in sorted(Path('temp').glob('*.parsed')):
    arm,block=path.stem.split('-')
    history=collections.defaultdict(list);opened={};spans=collections.defaultdict(list);wait={};oscall={};osdur=[];matches=[]
    tags=collections.defaultdict(set);nwait=0
    for h,detail in events(path):
        m,p,g,kind,t,extra=h;p,g,t=map(int,(p,g,t))
        q=state.search(extra)
        if not q:continue
        target=int(q[1]);a,b=q[2],q[3]
        history[target].append((t,b))
        actor=detail.partition('\nStack=\n')[2] or (detail[7:] if detail.startswith('Stack=\n') else '')
        if g>=0:
            if 'guest.(*Process).read ' in actor:tags[g].add('reader')
            if 'runtime.gcBgMarkWorker' in actor:tags[g].add('gc')
            if '/internal/generatedgo/' in actor:tags[g].add('guest')
        if a=='Running' and p in opened:
            start,owner=opened.pop(p)
            assert owner==target,(owner,target,h)
            spans[p].append((start,t,owner))
        if b=='Running' and p>=0:
            if p in opened:
                start,owner=opened.pop(p);spans[p].append((start,t,owner))
            opened[p]=t,target
        if arm=='os':
            if a=='Running' and b in ('Syscall','Waiting') and '.Fd_write ' in detail and 'os.(*File).Write ' in detail:
                oscall[target]=t,b
            elif target in oscall and a in ('Syscall','Waiting') and b!=a:
                start,typ=oscall.pop(target);osdur.append((typ,t-start))
            continue
        if a=='Running' and b=='Waiting' and 'guest.byteWriter.Write ' in detail and 'byte_pipe.go:65' in detail and '.Fd_write ' in detail:
            assert target not in wait
            nwait+=1;tags[target].add('writer');wait[target]=dict(block=block,writer=target,park=t)
        elif target in wait:
            r=wait[target]
            if a=='Waiting' and b=='Runnable':
                r.update(wake=t,waker=g,wake_p=p,by_reader=int('guest.byteReader.Read ' in actor and 'guest.(*Process).read ' in actor))
            elif a=='Runnable' and b=='Running':
                assert 'wake' in r
                r.update(resume=t,resume_p=p,park_ns=r['wake']-r['park'],ready_ns=t-r['wake'])
                matches.append(wait.pop(target))
    if arm=='os':
        for typ in sorted({k for k,d in osdur}):
            ds=[d for k,d in osdur if k==typ]
            osrows.append(dict(block=block,state=typ,n=len(ds),p50_us=quant(ds,.5),p95_us=quant(ds,.95),max_us=max(ds)/1000))
        continue
    assert matches and not wait and nwait==len(matches)
    starts={p:[s for s,e,g in v] for p,v in spans.items()}
    cats=collections.Counter()
    for r in matches:
        p=r['resume_p'];start,end=r['wake'],r['resume'];used=0
        i=max(0,bisect.bisect_right(starts[p],start)-1)
        while i<len(spans[p]):
            s,e,g=spans[p][i];i+=1
            if s>=end:break
            ns=max(0,min(e,end)-max(s,start))
            if ns:
                role=next((x for x in ('reader','writer','gc','guest') if x in tags[g]),'other')
                cats[role]+=ns;used+=ns
        assert used<=end-start
        cats['unassigned']+=end-start-used
    long=[r for r in matches if r['park_ns']>=1000000 and r['by_reader']]
    durations=collections.Counter()
    for r in long:
        states=history[r['waker']]
        i=bisect.bisect_right(states,(r['park'],chr(0x10ffff)))-1
        t=r['park']
        while t<r['wake']:
            stop=min(r['wake'],states[i+1][0]) if i+1<len(states) else r['wake']
            durations[states[i][1] if i>=0 else 'unknown']+=stop-t
            t=stop;i+=1
    assert sum(durations.values())==sum(r['park_ns'] for r in long)
    for name,ns in sorted(durations.items()):
        reader_states.append(dict(block=block,long_parks=len(long),waker_state=name,ns=ns))
    for role,ns in sorted(cats.items()):
        overlaps.append(dict(block=block,resume_P_role=role,overlap_ns=ns))
    x=dict(block=block,matched=nwait,reader_wakes=sum(r['by_reader'] for r in matches),
           same_P=sum(r['wake_p']==r['resume_p'] for r in matches))
    for field in ('park_ns','ready_ns'):
        v=[r[field] for r in matches]
        for label,pct in [('p50',.5),('p95',.95),('p99',.99),('max',1)]:
            x[field.split('_')[0]+'_'+label+'_us']=quant(v,pct)
    summary.append(x);allrows.extend(matches)
assert len(summary)==3 and len(osrows)>=3
csv_out('waits.csv.gz',allrows);csv_out('summary.csv',summary);csv_out('resume-p.csv',overlaps);csv_out('os.csv',osrows)

csv_out('reader-long-parks.csv',reader_states)
