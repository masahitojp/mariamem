"""Preserve compact, verifiable reproduction inputs and all nine raw profiles."""
import gzip
import hashlib
from pathlib import Path
import shutil
import sys

root=Path(sys.argv[1]).resolve()
dest=Path(sys.argv[2]).resolve()
e=root/'evidence'; t=root/'temp'
dest.mkdir(parents=True,exist_ok=False)
def copy(p,name=None):
    name=name or p.name
    out=dest/name; out.parent.mkdir(parents=True,exist_ok=True); shutil.copyfile(p,out)
for file in (t/'recipe').iterdir():
    if file.is_file(): copy(file,'recipe/'+file.name)
for name in ('verify-map.py','regenerate.sh','run-builder.py'):
    copy(e/name,'recipe/'+name)
for name in ('phase1.json','build-inputs.json','functions.txt.gz','builder-space.jsonl','bindings.json','pairs.csv','allocator-site.csv','allocator-store.asm','T1.csv','T2.csv','T3.csv'):
    if (e/name).is_file(): copy(e/name)
for p in (t/'output').iterdir():
    if p.suffix in {'.jsonl','.json'} or p.name=='guest-hashes.txt': copy(p,'producer/'+p.name)
for group in ('cpu','events'):
    folder=e/group
    if not folder.exists(): continue
    for p in sorted(folder.iterdir()):
        if p.stat().st_size==0 and p.suffix=='.stderr': continue
        if p.suffix in {'.jsonl','.json'} and p.stat().st_size>40_000:
            out=dest/group/(p.name+'.gz'); out.parent.mkdir(exist_ok=True)
            out.write_bytes(gzip.compress(p.read_bytes(),mtime=0))
        else: copy(p,group+'/'+p.name)
for log in sorted(e.glob('*build.log')):
    if log.stat().st_size: copy(log)
with (dest/'producer'/'builder.log.gz').open('wb') as f:
    f.write(gzip.compress((e/'builder.log').read_bytes(),mtime=0))
