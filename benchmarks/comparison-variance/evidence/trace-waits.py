from pathlib import Path
import json,re
w=Path(__file__).resolve().parent.parent;t=w/'temp';d=w/'evidence/diagnostic';lo=323443535175744;hi=323444016003840;resume=323443940340288;prev={};selected=[];block=[]
def consume(b):
 if not b:return
 h=b[0];m=re.search(r'StateTransition Time=(\d+) GoID=(\d+) (\w+)->(\w+)',h)
 if not m:return
 ts,gid,before,after=int(m[1]),int(m[2]),m[3],m[4]
 if ts>hi:return
 if gid in prev:
  a=prev[gid];dur=(ts-a['time'])/1e6
  if dur>100 and ts>=lo and (gid in [192,8654] or abs(ts-resume)<5e6):selected.append({'gid':gid,'duration_ms':dur,'start_ns':a['time'],'end_ns':ts,'header':a['header'],'end_header':h.strip(),'stack':a['stack']})
 prev[gid]={'time':ts,'header':h.strip(),'stack':''.join(b[1:])}
with (t/'run-7-events.txt').open()as f:
 for line in f:
  if line.startswith('M='):consume(block);block=[line]
  else:block.append(line)
consume(block);(d/'long-waits-near-response.json').write_text(json.dumps(selected,indent=2))
for x in selected:
 funcs=[z.strip() for z in x['stack'].splitlines() if '@'in z];print(x['gid'],round(x['duration_ms'],3),x['header'],x['end_header']);print('\n'.join(dict.fromkeys(funcs))[:4000])
