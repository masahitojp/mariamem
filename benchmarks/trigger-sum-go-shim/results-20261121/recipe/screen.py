"""Re-screen #233 stacks by candidate and count each sample once per candidate."""
from collections import Counter,defaultdict
import csv
import gzip
import json
from pathlib import Path
import re
import subprocess
import sys

prior,out,pprof=Path(sys.argv[1]),Path(sys.argv[2]),sys.argv[3]
names=dict(line.split(':',1) for line in gzip.decompress((prior/'functions.txt.gz').read_bytes()).decode().splitlines())
oracle={r['run']:r for r in json.loads((prior/'cpu/cpu.json').read_bytes())}
rows=[]; callers=[]; windows=[]; leaves=[]
for p in sorted((prior/'cpu').glob('*.pprof')):
    raw=subprocess.check_output([pprof,'-raw',p],text=True)
    prefix,tail=raw.split('\nLocations\n')
    locs={}
    for line in tail.split('\nMappings\n')[0].splitlines():
        m=re.match(r'\s*(\d+): 0x[0-9a-f]+ M=\d+\s*(.*)',line)
        if m:
            ident=int(m[1]); locs[ident]=[]; rest=m[2]
        else: rest=line.strip()
        if rest: locs[ident].append(rest.split()[0])
    groups={'crc':r'crc32|crc32c|crc32ieee','byte_string':r'^(strlen|strnlen|strcmp|strncmp|strcasecmp|strncasecmp|memcmp|bcmp|memchr|strchr|strrchr|strspn|strcspn|strstr|memmem)$',
            'bulk_copy_fill':r'^(memcpy|memmove|memset|bzero)$|/base\.Memory(Copy|Fill)$',
            'collation':r'my_strnncoll|my_strnxfrm|my_hash_sort|uca_scanner|my_well_formed',
            'hash_checksum':r'adler32|xxh(32|64|3)|murmur|ut_fold|fold_binary|my_checksum',
            'decimal':r'decimal_(add|sub|mul|div|round|cmp)|decimal2bin|bin2decimal|int2decimal|decimal2int',
            'bounds':r'/base\.(MemoryEA|MemoryInBounds|MemBound)$','allocator':r'^dlmalloc$',
            'wasi':r'\.(Clock_time_get|Fd_[A-Za-z0-9_]+|Futex_[A-Za-z0-9_]+|Sched_yield)$'}
    counts=defaultdict(Counter); own=Counter(); leaf_counts=Counter()
    for line in prefix.split('samples/count cpu/nanoseconds\n')[1].splitlines():
        weights,ids=line.split(':')
        n=int(weights.split()[0])
        frames=[f for i in map(int,ids.split()) for f in (locs[i] or ['[unresolved]'])]
        resolved=[names.get(m[1],f) if (m:=re.search(r'/p\d+\.Fn(\d+)$',f)) else f for f in frames]
        sql=[i for i,f in enumerate(frames) if f.endswith('.Fn5581')]
        if not sql:
            c=counts['outside_sql_stack']
            c['total']+=n
            for g,rx in groups.items():
                if any(re.search(rx,f,re.I) for f in resolved): c[g]+=n
            continue
        inside=resolved[:sql[-1]+1]
        if inside: leaf_counts[inside[0]]+=n
        domains=['sql']
        if any('process_triggers' in f for f in inside): domains.append('trigger')
        for scope in domains:
            c=counts[scope]; c['total']+=n
            for g,rx in groups.items():
                if any(re.search(rx,f,re.I) for f in inside): c[g]+=n
        if any(re.search(groups['bounds'],f) for f in inside):
            caller=next((names[m[1]] for f in frames[:sql[-1]+1] if (m:=re.search(r'/p\d+\.Fn(\d+)$',f))),'[none]')
            own[caller]+=n
    for scope in ('sql','trigger','outside_sql_stack'):
        c=counts[scope]
        ref=oracle[p.stem]['counts']
        expected=ref['process']-ref['sql'] if scope=='outside_sql_stack' else ref.get(scope,0)
        assert c['total']==expected
        rows.append(dict(run=p.stem,scope=scope,total=c['total'],**{g:c[g] for g in groups}))
    for k,n in leaf_counts.most_common():
        leaves.append(dict(run=p.stem,sql_leaf=k,samples=n))
    for k,n in own.most_common():
        callers.append(dict(run=p.stem,nearest_guest_caller=k,bounds_samples=n))
    events=json.loads(gzip.decompress((prior/'events'/(p.stem+'-events.json.gz')).read_bytes()))['Requests']
    assert len(events)==100
    t=Counter()
    for r in events:
        a,b,c,d=[r[key] for key in ('ClientBegin','SQLBegin','SQLEnd','ClientEnd')]
        assert a<=b<=c<=d and r['SQLCalls']==1
        t.update(before=b-a,inside=c-b,after=d-c)
    windows.append(dict(run=p.stem,**{g+'_ms':round(v/1e6,4) for g,v in t.items()}))
for name,table in [('screen',rows),('bounds-callers',callers),('request-windows',windows),('sql-leaves',leaves)]:
    with (out/(name+'.csv')).open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=table[0],lineterminator='\n')
        writer.writeheader();writer.writerows(table)
