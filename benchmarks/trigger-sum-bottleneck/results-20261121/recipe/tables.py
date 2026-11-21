"""Materialize triplet-normalized CPU, path and counter tables from raw reductions."""
import csv
import gzip
import json
from pathlib import Path
import subprocess
import sys

e=Path(sys.argv[1])
cpu={r['run']:r for r in json.loads((e/'cpu/cpu.json').read_bytes())}
events={r['run']:r for r in json.loads((e/'events/counters.json').read_bytes())}
bindings=json.loads((e/'bindings.json').read_bytes())
names={int(i):name for i,name in (s.split(':',1) for s in gzip.decompress((e/'functions.txt.gz').read_bytes()).decode().splitlines())}

def table(name,cols,rows):
    with (e/name).open('w',newline='') as f:
        writer=csv.writer(f,lineterminator="\n"); writer.writerow(cols)
        for row in rows: writer.writerow([round(x,7) if isinstance(x,float) else x for x in row])

def norm(r,ns): return ns/(r['inserts']/100)/1e6

pairs=[]; t1=[]; t2=[]; t3=[]
for triplet in (1,2,3):
    group=[cpu[f'{triplet}-{arm}'] for arm in 'ABC']
    sql=[norm(r,r['cpu_ns']['sql']) for r in group]
    gap=sql[0]-sql[1]
    for arm,r in zip('ABC',group):
        pairs.append([triplet,arm,r['inserts'],norm(r,r['raw_ns']),r['counts']['process'],r['counts']['sql'],
                      r['counts'].get('trigger',0),r['cpu_ns']['sql']/1e9,norm(r,r['cpu_ns']['sql']),norm(r,r['cpu_ns'].get('trigger',0))])
    for scope in ('sql','trigger'):
        cats=sorted(set().union(*(r['categories_ns'][scope] for r in group)))
        for cat in cats:
            values=[norm(r,r['categories_ns'][scope].get(cat,0)) for r in group]
            diff=values[0]-values[1]
            share=group[0]['categories_ns'][scope].get(cat,0)/group[0]['cpu_ns'][scope]*100
            t1.append([triplet,scope,cat,*values,diff,share,100*diff/gap if gap>0 and scope=='sql' else ''])
    indices=set().union(*(r['functions_ns'] for r in group))
    rows=[]
    for i in indices:
        values=[norm(r,r['functions_ns'].get(i,0)) for r in group]
        rows.append([triplet,int(i),names[int(i)],*values,values[0]-values[1]])
    top=set()
    for col in (3,4,6):
        top.update(r[1] for r in sorted(rows,key=lambda r: r[col],reverse=True)[:30])
    t2+=sorted([r for r in rows if r[1] in top],key=lambda r:(-r[3],r[1]))
    event_group=[events[f'{triplet}-{arm}'] for arm in 'ABC']
    known=set(bindings['wasi_sites'])|set(bindings['functions'])|{'call_indirect','memory.grow','memory.grow_requested_pages','AtomicEA','AtomicWait','MemoryEA','dlmalloc_requested_bytes','process_triggers','sp.reparse_at_parse_sql'}
    known-= {'trigger','target'}
    known.update('helper.'+k for k in bindings['atomic_helpers'])
    known.update('inline.'+k for k in bindings['atomic_inline'])
    for field in ('calls','trigger_calls','times_ns','interval_totals'):
        keys=set().union(*(r[field] for r in event_group))
        if field in ('calls','trigger_calls'): keys|=known
        for key in sorted(keys):
            ns=field=='times_ns' or key.endswith('_ns')
            unit='ms/100 INSERT' if ns else ('bytes/INSERT' if 'bytes' in key else 'pages/INSERT' if 'pages' in key else 'count/INSERT')
            vals=[r[field].get(key,0)*(100/1e6 if ns else 1)/r['inserts'] for r in event_group]
            t3.append([triplet,field,key,unit,*vals])
mangled=[row[2] for row in t2]
demangled=subprocess.check_output(['c++filt'],input='\n'.join(mangled)+'\n',text=True).splitlines()
assert len(demangled)==len(t2)
for row,name in zip(t2,demangled): row[2]=name
table('pairs.csv',['triplet','arm','inserts','raw_ms_per_100','process_samples','sql_samples','trigger_samples','sql_cpu_seconds','sql_cpu_ms_per_100','trigger_cpu_ms_per_100'],pairs)
table('T1.csv',['triplet','scope','exclusive_category','A_ms_per_100','B_ms_per_100','C_ms_per_100','A_minus_B_ms_per_100','A_scope_percent','percent_of_SQL_gap'],t1)
table('T2.csv',['triplet','Fn','function','A_cum_ms_per_100','B_cum_ms_per_100','C_cum_ms_per_100','A_minus_B_ms_per_100'],t2)
table('T3.csv',['triplet','scope_or_metric','event','unit','A','B','C'],t3)
