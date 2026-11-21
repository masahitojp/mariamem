"""Check all request traces, then aggregate matched four-block measurements."""
from collections import Counter, defaultdict
import copy
import csv
import gzip
import json
from pathlib import Path
from statistics import mean
import subprocess
import sys
from campaign import MODES, validate

def save(path, rows):
    with path.open('w') as out:
        writer = csv.DictWriter(out,fieldnames=rows[0],lineterminator='\n')
        writer.writeheader()
        for row in rows:
            writer.writerow({k:round(v,8) if isinstance(v,float) else v for k,v in row.items()})

def run(dst):
    catalog=json.loads((dst/'edges.json').read_text())
    sites=catalog['edges']
    labels={str(e['id']):e for e in sites}
    symbols=sorted(set(catalog['parents'].values()) | {e['symbol'] for e in sites})
    full=subprocess.check_output(['c++filt'],input='\n'.join(symbols)+'\n',text=True).splitlines()
    short={s:v.split('(')[0] for s,v in zip(symbols,full)}
    assert len(short)==len(symbols)
    meta=json.loads((dst/'runs/environment.json').read_text())
    assert len({meta['binaries'][m]['sha256'] for m in MODES})==4
    totals=Counter()
    controls=[]; blocks=[]; distributions=[]; per_position=[]
    sample_values=defaultdict(list)
    input_counts={}
    registered={}
    for b in range(5):
        for sql in 'ABC':
            for mode in MODES:
                p=dst/'runs'/f'{b}-{sql}-{mode}'
                observations=[json.loads(s) for s in p.with_suffix('.jsonl').read_text().splitlines()]
                setup=observations[0];group=observations[1:]
                assert setup['arm']==sql and len(setup['registered'])==(4 if sql=='C' else 5)
                assert registered.setdefault(sql,setup['registered'])==setup['registered']
                assert len(group)==(12 if b else 1)
                assert all(r['db']==i and r['close']=='pass' and r['inserts']==100 for i,r in enumerate(group))
                totals['processes']+=1;totals['databases']+=len(group);totals['inserts']+=100*len(group)
                if mode!='base':
                    data=json.loads(gzip.decompress(p.with_suffix('.json.gz').read_bytes()))
                    validate(data,group,sql,mode)
                    level=MODES.index(mode)-1
                    assert all(labels[k]['level']<=level for items in data for r in items for k in r['Join'])
                    totals['traced']+=100*len(group)
                    if sql=='A':
                        for items in data:
                            assert [r['Join']['0']['Calls'] for r in items]==[2]+[1]*99
                    if mode in ('branch','deep') and sql=='A':
                        for items in data:
                            for r in items:
                                observed=sorted((k,v['Calls']) for k,v in r['Join'].items() if labels[k]['level']<=1)
                                key=(b,r['DB'],r['Ordinal'])
                                if mode=='branch':input_counts[key]=observed
                                else:assert input_counts.pop(key)==observed
                if not b:continue
                n=len(group)-2
                totals['steady_inserts']+=100*n
                den=n*1e6
                raw=mean(r['raw_ns'] for r in group[2:])/1e6
                ctrl=dict(block=b,sql=sql,mode=mode,raw_ms100=raw,trigger_ms100='',join_ms100='',join_calls100='')
                controls.append(ctrl)
                if mode=='base':continue
                calls=Counter();exclusive=Counter();inclusive=Counter()
                trig=0; db_times=[]
                positions=[(o,k) for o in range(1,41) for k in range(1,2+o%4)]
                assert len(positions)==100
                pos=defaultdict(list)
                for batch in data[2:]:
                    db_join=0
                    for r in batch:
                        trig+=r['TriggerNS']
                        for k,v in r['Join'].items():
                            calls[k]+=v['Calls']
                            exclusive[k]+=v['Exclusive']
                            inclusive[k]+=v['Inclusive']
                        if r['Join']:
                            root=r['Join']['0']
                            db_join+=root['Inclusive']
                            order,idx=positions[r['Ordinal']]
                            pos[idx].append(root['Inclusive'])
                    db_times.append(db_join/1e6)
                assert sum(exclusive.values())==inclusive['0']
                ctrl.update(trigger_ms100=trig/den,join_ms100=inclusive['0']/den,join_calls100=calls['0']/n)
                if sql!='A':continue
                for db,t in enumerate(db_times,2):
                    distributions.append(dict(block=b,mode=mode,db=db,join_ms100=t))
                for idx,v in sorted(pos.items()):
                    per_position.append(dict(block=b,mode=mode,item_position=idx,inserts=len(v),join_us=mean(v)/1000))
                for k in sorted(calls,key=int):
                    site=labels[k]
                    v=dict(block=b,mode=mode,id=int(k),caller=short[catalog['parents'][site['caller']]] if k!='0' else 'trigger',
                           target=short[site['symbol']],calls100=calls[k]/n,exclusive_ms100=exclusive[k]/den,
                           inclusive_ms100=inclusive[k]/den,exclusive_pct=100*exclusive[k]/inclusive['0'])
                    blocks.append(v)
                    sample_values[mode,k].append(v)
    assert not input_counts
    assert totals==dict(processes=60,databases=588,inserts=58800,traced=44100,steady_inserts=48000)
    summary=[]
    for (mode,k),records in sample_values.items():
        # A site never called in a block contributes zero for that block.
        row={key:records[0][key] for key in ('mode','id','caller','target')}
        block_values={r['block']:r for r in records}
        for key in ('calls100','exclusive_ms100','inclusive_ms100','exclusive_pct'):
            vals=[block_values[b][key] if b in block_values else 0 for b in range(1,5)]
            row[key]=mean(vals)
            if key.endswith('ms100'):
                row[key+'_min']=min(vals);row[key+'_max']=max(vals)
        summary.append(row)
    summary.sort(key=lambda r:(MODES.index(r['mode']),-r['exclusive_ms100']))
    save(dst/'edges-by-block.csv',blocks);save(dst/'ranked.csv',summary)
    save(dst/'controls.csv',controls);save(dst/'databases.csv',distributions);save(dst/'positions.csv',per_position)
    p=dst/'runs/0-A-deep.jsonl'
    raw=[json.loads(line) for line in p.read_text().splitlines()][1:]
    trace=json.loads(gzip.decompress(p.with_suffix('.json.gz').read_bytes()))
    checks=[lambda x:x[0].pop(),lambda x:x[0][1].update(ID=x[0][0]['ID']),
            lambda x:x[0][0]['Join']['0'].update(Exclusive=-1),
            lambda x:x[0][0]['Join']['0'].update(Inclusive=0),
            lambda x:x[0][0]['Join']['0'].update(Calls=0)]
    for damage in checks:
        x=copy.deepcopy(trace);damage(x)
        try:validate(x,raw,'A','deep')
        except AssertionError:continue
        raise AssertionError('corrupt measurement passed')
    (dst/'verification.json').write_text(json.dumps(dict(totals=totals,negative_checks=len(checks),static_sites=len(sites)),indent=2)+'\n')
if __name__=='__main__':
    run(Path(sys.argv[1]))
