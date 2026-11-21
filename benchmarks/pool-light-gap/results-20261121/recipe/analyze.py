"""Summarize the bounded campaign and replay stock, timing and detector checks."""
import csv,itertools,json,sys
from pathlib import Path
from check import validate

out=Path(sys.argv[1])
pilot=list(sorted(out.glob('pilot-*.json')))
for pos,arm in enumerate(('current','split')):
    validate(out/f'pilot-1-{pos}-{arm}.json',arm,1,True)
rows=[];forks=[];captures=[]
def write(name,data):
    with (out/(name+'.csv')).open('w',newline='') as f:
        w=csv.DictWriter(f,fieldnames=data[0].keys(),lineterminator='\n')
        w.writeheader();w.writerows(data)
ordered=[]
for b in range(1,13):
    for pos,arm in enumerate(('current','split') if b%2 else ('split','current')):
        ordered.append((b,pos,arm))
for b,pos,arm in ordered:
    path=out/f'main-{b}-{pos}-{arm}.json'
    if not path.exists():break
    r=validate(path,arm,b,False)
    m=r['Monitor'];ws=[q for wave in r['Waves'] for q in wave['Wakes']]
    ss=m['Last']
    for i,s in enumerate(ss,1):
        forks.append(dict(block=b,arm=arm,db=i,handler=s['HandlerID'],low=s['Low'],ended=s['HandlerEnded'],
            entered=s['Entered'],exited=s['Exited'],reinserted=s['Inserted']))
    rows.append(dict(block=b,arm=arm,requests=len(ws),scans=m['Scans'],captured=m['Captured'],
            max_scan_interval_ms=round(m['MaxScanIntervalMS'],3),entered=sum(s['Entered'] for s in ss),
            exited=sum(s['Exited'] for s in ss),reinserted=sum(s['Inserted'] for s in ss),
            max_wave_ms=round(max(v['AllResponsesMS'] for v in r['Waves']),4),
            max_on_wave_age_ms=round(max((v['Before']['SinceTickMS'] for v in ws if not v['Before']['Low']),default=0),4)))
    if m['Captured']:
        captures.append(path.name);break
files=[p for p in out.glob('main-*.json') if not p.name.endswith('.capture.json')]
assert rows and len(rows)==len(files) and (captures or len(rows)==24)
write('trials',rows);write('forks',forks)
summary=[]
for arm in ('current','split'):
    a=[r for r in rows if r['arm']==arm]
    if a:
        summary.append(dict(arm=arm,trials=len(a),forks=len(a)*8,requests=sum(t['requests'] for t in a),
            scans=sum(t['scans'] for t in a),captured=sum(t['captured'] for t in a),entered=sum(t['entered'] for t in a),
            exited=sum(t['exited'] for t in a),reinserted=sum(t['reinserted'] for t in a),
            max_scan_interval_ms=max(t['max_scan_interval_ms'] for t in a),
            max_wave_ms=max(t['max_wave_ms'] for t in a),max_on_wave_age_ms=max(t['max_on_wave_age_ms'] for t in a)))
write('summary',summary)
print('PASS',len(rows),'processes,',len(forks),'forks,',sum(r['requests'] for r in rows),'requests. Captures:',captures)
