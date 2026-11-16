from pathlib import Path
import re,json
w=Path(__file__).resolve().parent.parent;t=w/'temp';d=w/'evidence/diagnostic';start=323443535175744;end=323444016003840;events=[];block=[]
def consume(block):
 if not block:return
 h=block[0];m=re.search(r'Time=(\d+)',h)
 if not m:return
 ts=int(m[1])
 if not start<=ts<=end:return
 if 'GoID=192 'in h or (' G=192 'in h and 'Region'in h):events.append({'time':ts,'header':h.strip(),'stack':''.join(block[1:])})
with (t/'run-7-events.txt').open()as f:
 for line in f:
  if line.startswith('M='):consume(block);block=[line]
  else:block.append(line)
consume(block)
trans=[x for x in events if 'StateTransition'in x['header']];segments=[]
for a,b in zip(trans,trans[1:]):
 ms=(b['time']-a['time'])/1e6
 if ms>=1:segments.append({'duration_ms':ms,'from_ms':(a['time']-start)/1e6,'to_ms':(b['time']-start)/1e6,**a,'end_header':b['header']})
segments.sort(key=lambda x:x['duration_ms'],reverse=True)
(d/'slow-caller-segments.json').write_text(json.dumps({'region_start_ns':start,'region_end_ns':end,'goroutine':192,'transitions':len(trans),'segments_ge_1ms':segments},indent=2))
for x in segments[:5]:print(x['duration_ms'],x['header'],x['end_header']);print(x['stack'][:6000])
