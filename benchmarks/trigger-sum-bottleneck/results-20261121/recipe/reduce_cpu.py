"""Reduce independent pprof stacks, counting recursive or inline ancestors once."""
import argparse
from collections import Counter, defaultdict
import gzip
import json
from pathlib import Path
import re
import subprocess

p=argparse.ArgumentParser()
p.add_argument('results',type=Path); p.add_argument('table',type=Path)
p.add_argument('source',type=Path); p.add_argument('binary',type=Path)
a=p.parse_args()
names={int(k):v for k,v in (line.split(':',1) for line in gzip.decompress(a.table.read_bytes()).decode().splitlines())}
def one(part):
    value, = [k for k,v in names.items() if part in v]
    return value
sql, trigger = one('emb_stmt_execute'), one('process_triggers')
fn_re=re.compile(r'/code/p\d+\.Fn(\d+)(?:\.|$)')
allocs={i for i,n in names.items() if n in ('dlmalloc','dlfree','dlrealloc','dlcalloc','dlmemalign','calloc','internal_memalign','__wrap_malloc','__wrap_calloc','__wrap_free','__wrap_realloc','__wrap_posix_memalign')}
base=(a.source/'internal/generatedgo/code/base/base.go').read_text()
wasi={method for block in re.findall(r'type (?:Wasi_snapshot_preview1|Wasix_32v1)Imports interface \{(.*?)^\}',base,re.M|re.S)
      for method in re.findall(r'^\s*(\w+)\(',block,re.M)}
source_lines={}
def at_indirect(file, line):
    if not line or '/code/p' not in file: return False
    path=a.source/'internal/generatedgo/code'/('/'.join(file.split('/')[-2:]))
    if path not in source_lines:
        source_lines[path]={i for i,l in enumerate(path.open(),1) if 'm.T0[' in l and '].(func(' in l}
    return line in source_lines[path]

def classify(frames,indices):
    # Prefer the nearest named cost when walking from the sampled PC toward SQL.
    # Keep generated frames transparent to an enclosing allocator/WASI boundary.
    for name,file,line in frames:
        if re.search(r'runtime\.(?:morestack|newstack|copystack|adjustframe)',name): return 'Go stack growth'
        if re.search(r'/base\.(?:MemoryEA|MemoryInBounds|MemBound)$',name): return 'linear memory bounds'
        if re.search(r'/base\.(?:Atomic|atomic|SpinRelax)|sync/atomic\.',name): return 'atomic helpers'
        if name.rsplit('.',1)[-1] in wasi: return 'WASI host calls'
        m=fn_re.search(name)
        if m and int(m[1]) in allocs: return 'guest allocator'
        if name.endswith('/base.MemoryGrow'): return 'memory growth'
    name,file,line=frames[0]
    if fn_re.search(name):
        return 'generated indirect call site' if at_indirect(file,line) else 'generated function body'
    if '/code/base.' in name: return 'other generated runtime helper'
    if name.startswith(('runtime.','internal/','sync.','syscall.')): return 'other Go runtime'
    return 'other or unresolved'

def decode(raw):
    pre,tail=raw.split('\nLocations\n')
    locs, _=tail.split('\nMappings\n',1)
    assert 'samples/count cpu/nanoseconds' in pre
    samples=[]
    for line in pre.split('samples/count cpu/nanoseconds\n',1)[1].splitlines():
        count,ns,ids=re.fullmatch(r'\s*(\d+)\s+(\d+):\s*([0-9 ]*)\s*',line).groups()
        samples.append((int(count),int(ns),[int(i) for i in ids.split()]))
    frames={}
    for line in locs.splitlines():
        loc=re.match(r'\s*(\d+): 0x[0-9a-f]+ M=\d+(?: (.*))?$',line)
        if loc:
            k=int(loc[1]); frames[k]=[]; rest=loc[2] or ''
        else: rest=line.strip()
        match=re.match(r'(.+?) (.*?):(\d+):\d+(?: |$)',rest)
        frames[k].append((match[1],match[2],int(match[3])) if match else ('[unresolved]','',0))
    return samples,frames

results=[]
for profile in sorted(a.results.glob('*.pprof')):
    raw=subprocess.check_output(['go','tool','pprof','-raw',a.binary,profile],text=True)
    samples,locations=decode(raw)
    counts=Counter(); cpu=Counter(); categories=defaultdict(Counter); paths=Counter()
    cohorts=[json.loads(l) for l in profile.with_suffix('.jsonl').read_text().splitlines()]
    inserts=sum(r.get('inserts',0) for r in cohorts)
    for count,ns,ids in samples:
        counts['process']+=count; cpu['process']+=ns
        frames=[f for i in ids for f in locations[i]]
        indices=[(j,int(m[1])) for j,f in enumerate(frames) if (m:=fn_re.search(f[0]))]
        sql_depth=[j for j,i in indices if i==sql]
        if not sql_depth:
            if any(i==trigger for j,i in indices): counts['trigger_seen_without_sql']+=count
            continue
        # Ignore caller frames outside the outermost target SQL invocation.
        inner=frames[:max(sql_depth)+1]
        cat=classify(inner,indices)
        below={i for j,i in indices if j<=max(sql_depth)}
        scopes=['sql','trigger'] if trigger in below else ['sql']
        for scope in scopes:
            counts[scope]+=count; cpu[scope]+=ns; categories[scope][cat]+=ns
        for i in below: paths[i]+=ns
    assert all(sum(categories[s].values())==cpu[s] for s in ('sql','trigger'))
    results.append(dict(run=profile.stem,inserts=inserts,raw_ns=sum(r.get('raw_ns',0) for r in cohorts),
                        counts=counts,cpu_ns=cpu,categories_ns=categories,functions_ns=paths))
(a.results/'cpu.json').write_text(json.dumps(results,separators=(',',':'))+'\n')
