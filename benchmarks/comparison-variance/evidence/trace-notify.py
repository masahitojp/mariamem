from pathlib import Path
import re,json
w=Path(__file__).resolve().parent.parent;d=w/'evidence/diagnostic';blocks=[];cur=[];wanted={17594,17595,17598,8817,8654,192};lo=323443930000000;hi=323443942000000

def keep(b):
 if not b:return
 h=b[0];m=re.search(r'StateTransition Time=(\d+) GoID=(\d+)',h)
 if m and int(m[2])in wanted and (lo<=int(m[1])<=hi or ('GoID=17594 NotExist->Runnable'in h)):
  blocks.append({'header':h.strip(),'stack':''.join(b[1:])})
with (w/'temp/run-7-events.txt').open()as f:
 for line in f:
  if line.startswith('M='):keep(cur);cur=[line]
  else:cur.append(line)
keep(cur);(d/'notify-resume-events.json').write_text(json.dumps(blocks,indent=2))
for b in blocks:
 print(b['header'])
 if 'GoID=8817 Waiting->Runnable'in b['header'] or 'GoID=17594 NotExist'in b['header']:print(b['stack'][:4000])
