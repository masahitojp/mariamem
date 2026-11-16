from pathlib import Path
import json,re
w=Path(__file__).resolve().parent.parent;d=w/'evidence/diagnostic';ids={192,8654,8430,8429,8817,8657,8658,17595,17598,8919,8920};found=[];block=[]
def consume(b):
 if not b:return
 h=b[0];m=re.search(r'GoID=(\d+) NotExist->Runnable',h)
 if m and int(m[1])in ids:found.append({'gid':int(m[1]),'header':h.strip(),'stack':''.join(b[1:])})
with (w/'temp/run-7-events.txt').open()as f:
 for line in f:
  if line.startswith('M='):consume(block);block=[line]
  else:block.append(line)
consume(block);(d/'goroutine-lineage.json').write_text(json.dumps(found,indent=2))
for x in found:
 print(x['header']);print('\n'.join(z for z in x['stack'].splitlines()if '@'in z)[:2300])
