"""Attach the sampled generated Go statements to the line profile."""
from pathlib import Path
import re
w=Path.cwd()
profile=w/'evidence/cpu-lines.txt'
source=(w/'temp/p0_pure.go').read_text().splitlines()
original=(w/'worktree/internal/generatedgo/code/p0/p0_pure.go').read_text().splitlines()
# Instrumentation only inserts entire lines into this generated partition.
inserted=('defer base.MeasureForkPhase(', 'base.MarkEmbeddedStartup(')
original_line={}
old=0
for i,line in enumerate(source,1):
    if line.strip().startswith(inserted):continue
    assert original[old]==line,(i,old)
    old+=1
    original_line[i]=old
assert old==len(original)
print('# Sampled statements in init_embedded_server')
for row in profile.read_text().splitlines():
    m=re.search(r'\.Fn5583 .*p0_pure.go:(\d+)',row)
    if not m:continue
    n=int(m[1]);print(row)
    for i in range(n-2,n+3):
        print(f'{i}: source {original_line.get(i,"overlay")}: {source[i-1].strip()}')
