from collections import Counter
from pathlib import Path
import csv,gzip,json,statistics as stat
out=Path('evidence');rows=[];suites=[]
def offsets(r):
    return {e['name']:e['offset_ns']/1e6 for e in r['events']}
for path in sorted((out/'runs').glob('*.json.gz')):
    arm,b=path.name.split('.')[0].split('-')
    d=json.loads(gzip.decompress(path.read_bytes()))
    tr=d.pop('suite.json')
    forks=[s['end_ms']-s['start_ms'] for s in tr['spans'] if s['kind']=='fork']
    assert len(forks)==21
    suites.append(dict(arm=arm,block=b,suite_ms=tr['elapsed_ms'],fork_sum_ms=sum(forks),fork_median_ms=stat.median(forks)))
    if arm=='normal':continue
    owner=None;previous=-1;i=0
    for name,r in sorted(d.items(),key=lambda item:int(item[0][:-5].rsplit('-',1)[1])):
        seq=int(name[:-5].rsplit('-',1)[1])
        if r.get('operation')=='startup':owner=(seq,r)
        if r.get('operation')!='fork':continue
        assert owner and previous<owner[0]<seq
        previous=seq;i+=1
        f=offsets(r);h=offsets(owner[1])
        g=owner[1].get('guest')
        def span(w,a,b):return w[b]-w[a]
        row=dict(arm=arm,block=b,fork=i,api_ms=span(f,'begin','end'),
          maps_ms=span(h,'runtime/maps_begin','runtime/module_begin'),
          module_ms=span(h,'runtime/module_begin','runtime/module_ready'),
          execute_to_ready_ms=span(h,'runtime/execute_begin','ready_header_received'),
          guest_document=bool(g),server_init_ms='',bootstrap_ms='',routine_ms='',ready_prepare_ms='')
        if g:
            assert g['clock']=='guest_monotonic'
            read=offsets(g)
            row.update(server_init_ms=span(read,'server_init_begin','server_init_complete'),
             bootstrap_ms=span(read,'server_init_complete','bootstrap_complete'),
             routine_ms=span(read,'routine_schema_begin','routine_schema_complete'),
             ready_prepare_ms=span(read,'guest_main','ready_prepared'))
            assert 0<=row['server_init_ms']<=row['ready_prepare_ms']<=row['execute_to_ready_ms']+.1
        assert 0<row['execute_to_ready_ms']<=row['api_ms']
        rows.append(row)
    assert i==21
assert len(suites)==12 and len(rows)==168
for file,values in [('suites.csv',suites),('forks.csv',rows)]:
    with (out/file).open('w') as f:
        writer=csv.DictWriter(f,fieldnames=values[0],lineterminator='\n')
        writer.writeheader();writer.writerows(values)
for arm in ('normal','host','guest'):
    print(arm,{k:round(stat.median(r[k] for r in suites if r['arm']==arm),3) for k in ('suite_ms','fork_sum_ms','fork_median_ms')})
    a=[r for r in rows if r['arm']==arm]
    if a:
        print('guest documents',sum(r['guest_document'] for r in a))
        for k in ('api_ms','maps_ms','module_ms','execute_to_ready_ms','server_init_ms','bootstrap_ms','routine_ms','ready_prepare_ms'):
            v=[r[k] for r in a if r[k]!='']
            if v: print(k,round(stat.median(v),4),round(min(v),4),round(max(v),4))
