from pathlib import Path
import json,gzip,subprocess,re
w=Path(__file__).resolve().parent.parent;e=w/'evidence';t=w/'temp';r=w/'worktree'
p=r/'benchmarks/comparison-variance/evidence/diagnostic/run-7.trace.gz';raw=gzip.decompress(p.read_bytes());(t/'saved.trace').write_bytes(raw)
# Retain all state transitions for timer-to-worker lineage candidates, not full parsed dump.
targets={17593,17594,17595,17598,8817};events=[];b=[]
def consume(b):
 if not b:return
 h=b[0];m=re.search(r'GoID=(\d+)',h)
 if m and int(m[1])in targets:events.append({'header':h.strip(),'stack':''.join(b[1:])})
p=subprocess.Popen([str(t/'gotrace'),'-d=parsed',str(t/'saved.trace')],stdout=subprocess.PIPE,text=True)
for line in p.stdout:
 if line.startswith('M='):consume(b);b=[line]
 else:b.append(line)
consume(b);assert p.wait()==0
(e/'saved-selected-events.json').write_text(json.dumps(events,indent=2))
for x in events:
 if 'NotExist->Runnable' in x['header']:print(x['header'],x['stack'][:900])
