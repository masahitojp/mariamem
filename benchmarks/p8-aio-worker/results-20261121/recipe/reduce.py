"""Reduce saved observations. Retain unmatched foreground waits as such."""
import csv
import gzip
import hashlib
import itertools
import json
import math
import re
import statistics
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

out=Path(sys.argv[1]).resolve()
repo=Path(sys.argv[2]).resolve()
pins=json.loads((repo/'release/generated-license-evidence.json').read_text())
assert pins['guest_sha256'] in (repo/'internal/generatedgo/guest_identity.go').read_text()
source='7c5893b3d5198d2c5087dbb100e631dfe63a58bb:benchmarks/trigger-sum-bottleneck/results-20261121/functions.txt.gz'
data=gzip.decompress(subprocess.check_output(['git','show',source],cwd=repo))
assert len(data.splitlines())==pins['symbol_map_entries'] and hashlib.sha256(data).hexdigest()==pins['symbol_map_sha256']
symbols=dict(line.split(':',1) for line in data.decode().splitlines())
def table(name, rows):
    if not rows:return
    with (out/name).open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n')
        w.writeheader()
        w.writerows(rows)
def ms(ns):return round(ns/1e6,5)
def delta(a,b):return ms(b-a) if a and b else None
def stack(r,index):
    frames=r['stacks'][index] if index is not None else []
    result=[]
    for frame in frames:
        match=re.search(r'/p\d+\.Fn(\d+)$',frame)
        if match:
            name=symbols[match[1]]
            if name not in demangled:
                demangled[name]=subprocess.check_output(['c++filt','-n',name],text=True).strip()
            frame+=f' ({demangled[name]})'
        result.append(frame)
    return result
suites=[];waits=[];samples=[];details=[];demangled={}
for file in sorted((out/'runs').glob('main-*.gz')):
    r=json.loads(gzip.decompress(file.read_bytes()))
    identity=dict(block=r['block'],position=r['position'],setting=r['arm'])
    assert set(r['settings'])==set(r['windows']) and len(r['windows'])==21
    assert all(r['counts'][k]==n for k,n in dict(read=50,write=20,fork=21,sample=21).items())
    tail_count=0
    maximum=0
    for lane,window in r['windows'].items():
        start,end=window['start'],window['end']
        elapsed=ms(end-start);tail=end-start>=400_000_000
        tail_count+=tail;maximum=max(maximum,elapsed)
        matched=[]
        for e in r['dbs'][lane]['events'] or []:
            a,b=e['Start'],e['Selected']
            if not e.get('Host') or not e.get('ClientOp') or a<start-2000 or b>end+2000:continue
            host=e['Host'];op=e['ClientOp']
            assert e['Waiting']['Request']==host['ID'] and host['Slot']==host['ReplySlot']
            assert op['Start']<=a<=b<=op['End'] and host['Call']<=a<=b<=host['Resume']
            agent=e['Waker'];task=agent['Current'];f=task['Flush']
            wake=stack(r,e['WakeStack'])
            io=e['Branch']=='notify' and any('write_io_callback(' in v for v in wake)
            page_size=int(r['settings'][lane]['after'][6])
            page_ok=bool(io and task['Unique'] and task['ParentUnique'] and f['Generation']
                         and agent['CallbackPage']==f['Page']!=0 and task['Arg']==agent['WriteArg']==f['Control']
                         and f['Offset']==f['Number']*page_size
                         and 0<f['Decision']<=f['File']<=f['Submit']<=task['ParentEnqueue']
                         <=task['ParentInvoke']<=task['Enqueued']<=task['Invoked']<=e['Notified']<=b)
            v=dict(**identity,lane=lane,tail=tail,sample_ms=elapsed,operation=op['Op'],request=host['ID'],
                   reason=e['Branch'],wait_ms=ms(b-a),share_pct=round(100*(b-a)/(end-start),2),
                   write_io=io,matched_page=page_ok,space=f['Space'],page=f['Number'],
                   futex_minus_page=e['Address']-f['Page'] if page_ok else None,
                   cleaner=f['Cleaner'],batch_fn=f['BatchFn'],origin_request=f['Origin'],
                   wait_to_flush_ms=delta(a,f['Decision']),flush_to_file_ms=delta(f['Decision'],f['File']),
                   file_to_submit_ms=delta(f['File'],f['Submit']),submit_to_callback_ms=delta(f['Submit'],agent['WriteAt']),
                   callback_to_wake_ms=delta(agent['WriteAt'],e['Notified']),wake_to_resume_ms=delta(e['Notified'],b))
            if page_ok:
                segments=list(v.values())[-6:]
                assert abs(sum(segments)-v['wait_ms'])<0.0001
            buffered=bool(page_ok and f['Buffered'] and f['BufferedPage']==f['Page']
                          and f['Decision']<=f['Buffered']<=f['File'])
            v.update(buffered=buffered,from_write_callback=f['FromWriteCallback'],
                     buffer_to_file_ms=delta(f['Buffered'],f['File']) if buffered else None,
                     buffer_slot=f['Slot'] if buffered else None,
                     buffer_relative_to_load_ms=delta(start,f['Buffered']) if buffered else None,
                     flush_relative_to_load_ms=delta(start,f['Decision']) if page_ok else None,
                     aio_queue_ms=delta(task['ParentEnqueue'],task['ParentInvoke']) if page_ok else None,
                     completion_queue_ms=delta(task['Enqueued'],task['Invoked']) if page_ok else None)
            waits.append(v);matched.append(v)
            if tail:details.append(dict(summary=v,event=e,wait_stack=stack(r,e['WaitStack']),wake_stack=wake))
        samples.append(dict(**identity,lane=lane,sample_ms=elapsed,tail=tail,
                            long_waits=len(matched),write_io=sum(v['write_io'] for v in matched),
                            page_matches=sum(v['matched_page'] for v in matched)))
    suites.append(dict(**identity,suite_ms=r['suite_ms'],cpu_ms=round(r['cpu_ms'],4),tail_count=tail_count,max_sample_ms=maximum))
assert suites
arms=sorted({r['setting'] for r in suites})
orders=list(itertools.permutations([a for a in ['default','off'] if a in arms]))
blocks=max(r['block'] for r in suites)
assert blocks in (96,192)
for block in range(1,blocks+1):
    rows=sorted((s for s in suites if s['block']==block),key=lambda s:s['position'])
    assert [s['setting'] for s in rows]==list(orders[(block-1)%len(orders)])
summary=[]
base={r['block']:r for r in suites if r['setting']=='default'}
for arm in arms:
    rows=[r for r in suites if r['setting']==arm]
    tails=[r for r in samples if r['setting']==arm and r['tail']]
    better=sum(bool(base[r['block']]['tail_count']) and not r['tail_count'] for r in rows)
    worse=sum(bool(r['tail_count']) and not base[r['block']]['tail_count'] for r in rows)
    n=better+worse
    prob=min(1,2*sum(math.comb(n,i) for i in range(min(better,worse)+1))/2**n)
    paired=lambda k:round(statistics.median(100*(r[k]/base[r['block']][k]-1) for r in rows),2)
    summary.append(dict(setting=arm,suites=len(rows),loads=len(rows)*21,tail_suites=sum(bool(r['tail_count']) for r in rows),
        tail_loads=len(tails),io_tail_loads=sum(bool(r['write_io']) for r in tails),page_tail_loads=sum(bool(r['page_matches']) for r in tails),
        suite_median_ms=statistics.median(r['suite_ms'] for r in rows),cpu_median_ms=round(statistics.median(r['cpu_ms'] for r in rows),2),
        paired_wall_pct=paired('suite_ms'),paired_cpu_pct=paired('cpu_ms'),base_only=better,arm_only=worse,mcnemar_exact_p=round(prob,5),max_load_ms=max(r['max_sample_ms'] for r in rows)))
for name,rows in [('suites',suites),('samples',samples),('waits',waits),('summary',summary)]:table(name+'.csv',rows)
(out/'details.json').write_text(json.dumps(details,indent=2)+'\n')
print(json.dumps(summary,indent=2))
