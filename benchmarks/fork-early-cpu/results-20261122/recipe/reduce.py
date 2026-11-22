from pathlib import Path
import csv,gzip,json,statistics
out=Path('evidence')
labels={int(k):v for k,v in json.loads((out/'functions.json').read_bytes()).items()}
rows=[];suites=[]
for f in sorted((out/'runs').glob('*.json.gz')):
    arm,b=f.name.split('.')[0].split('-')
    data=json.loads(gzip.decompress(f.read_bytes()))
    tr=data.pop('suite.json')
    suites.append(dict(arm=arm,block=b,suite_ms=tr['elapsed_ms'],fork_ms=sum(s['end_ms']-s['start_ms'] for s in tr['spans'] if s['kind']=='fork')))
    prior=-1;startup=None;index=0
    for k,d in sorted(data.items(),key=lambda x:int(x[0][:-5].rsplit('-',1)[1])):
        seq=int(k[:-5].rsplit('-',1)[1])
        if d['operation']=='startup':startup=(seq,d)
        if d['operation']!='fork':continue
        assert startup and prior<startup[0]<seq
        prior=seq;index+=1
        if arm=='host':
            assert not startup[1].get('phase')
            continue
        events=startup[1]['phase']
        marks={e['name']:e['start_ns'] for e in events if 'name' in e}
        start=marks['embedded_begin'];stop=marks['embedded_options_complete']
        assert start<stop
        row=dict(block=b,fork=index,early_ms=(stop-start)/1e6)
        for n,name in labels.items():
            if n in (5749,5583):continue
            matches=[e for e in events if e['id']==n and start<=e['start_ns']<=e['end_ns']<=stop]
            row[str(n)+'_calls']=len(matches)
            row[str(n)+'_ms']=sum(e['end_ns']-e['start_ns'] for e in matches)/1e6
        rows.append(row)
    assert index==21
assert len(rows)==84 and len(suites)==8
for filename,values in [('timing',rows),('suites',suites)]:
    with (out/(filename+'.csv')).open('w') as f:
        w=csv.DictWriter(f,fieldnames=values[0],lineterminator='\n');w.writeheader();w.writerows(values)
for k in rows[0]:
    if k.endswith('_ms'):
        v=[r[k] for r in rows]
        print(k,round(statistics.median(v),4),round(min(v),4),round(max(v),4),labels.get(int(k[:-3]) if k[:-3].isdigit() else -1,''))
