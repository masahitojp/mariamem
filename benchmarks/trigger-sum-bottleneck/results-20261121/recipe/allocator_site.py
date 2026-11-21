"""Measure the dominant SUM allocator PC using the existing CPU profiles."""
import csv
import json
from pathlib import Path
import re
import subprocess
import sys

e,binary=map(Path,sys.argv[1:])
text=subprocess.check_output(['otool','-l',binary],text=True)
image=int(re.search(r'segname __TEXT\s+vmaddr (0x\w+)',text)[1],16)
dump=subprocess.check_output(['go','tool','objdump','-s',r'p1\.Fn152$',binary],text=True)
site,=[line for line in dump.splitlines() if 'p1_pure.go:11788' in line and 'MOVW R4, (R5)(R0)' in line]
pc=int(site.split()[1],16)
asm=dump.splitlines(); i=asm.index(site)
(e/'allocator-store.asm').write_text('\n'.join(l.rstrip() for l in asm[i-4:i+5])+'\n')
import gzip
names={int(i):name for i,name in (l.split(':',1) for l in gzip.decompress((e/'functions.txt.gz').read_bytes()).decode().splitlines())}
explain,=[i for i,n in names.items() if n.startswith('_ZN11Update_plan24save_explain_data_intern')]
append_str,=[i for i,n in names.items() if n.startswith('_ZN11String_list10append_str')]
rows=[]
for p in sorted((e/'cpu').glob('*.pprof')):
    raw=subprocess.check_output(['go','tool','pprof','-raw',p],text=True)
    samples,locations=raw.split('\nLocations\n'); locations,maps=locations.split('\nMappings\n')
    map_start=int(re.search(r'(?m)^1: (0x[0-9a-f]+)/',maps)[1],16)
    site_ids=set(); sql=set(); trigger=set(); plan=set(); append=set()
    for line in locations.splitlines():
        loc=re.match(r'\s*(\d+): (0x[0-9a-f]+) M=(\d+) (.*)',line)
        if loc:
            idx=int(loc[1])
            if loc[3]=='1' and int(loc[2],16)-map_start+image==pc:
                assert '/p1.Fn152 ' in loc[4] and ':11788:' in loc[4]
                site_ids.add(idx)
        if re.search(r'/p7\.Fn5581 ',line): sql.add(idx)
        if re.search(r'/p4\.Fn15566 ',line): trigger.add(idx)
        if re.search(r'/p\d+\.Fn'+str(explain)+r' ',line): plan.add(idx)
        if re.search(r'/p\d+\.Fn'+str(append_str)+r' ',line): append.add(idx)
    target=under=plan_leaf=0
    for line in samples.split('samples/count cpu/nanoseconds\n')[1].splitlines():
        vals,stack=line.split(':'); weight=int(vals.split()[0]); frames=list(map(int,stack.split()))
        if frames[0] in site_ids and sql.intersection(frames):
            target+=weight
            if trigger.intersection(frames):
                under+=weight
                if plan.intersection(frames) and append.intersection(frames): plan_leaf+=weight
    cohort=[json.loads(l) for l in p.with_suffix('.jsonl').read_bytes().splitlines()]
    n=sum(r.get('inserts',0) for r in cohort)
    period=int(re.search(r'(?m)^Period: (\d+)$',raw)[1])
    rows.append([p.stem,n,hex(pc-image),target,under,target*period/(n/100)/1e6,under*period/(n/100)/1e6,plan_leaf,plan_leaf*period/(n/100)/1e6])
with (e/'allocator-site.csv').open('w',newline='') as f:
    w=csv.writer(f,lineterminator="\n"); w.writerow(['process','inserts','image_offset','SQL_leaf_samples','trigger_leaf_samples','SQL_ms_per_100','trigger_ms_per_100','update_plan_append_trigger_leaf_samples','update_plan_append_ms_per_100']); w.writerows(rows)
