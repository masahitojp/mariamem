from pathlib import Path
import subprocess,json,re,collections
w=Path(__file__).resolve().parent.parent;t=w/'temp';e=w/'evidence';summary=[]
for i in range(8):
 events=[];block=[]
 def consume(b):
  if not b or ' Category="pool" 'not in b[0]:return
  m=re.search(r'G=(\d+) Log Time=(\d+).*Message="([^"]+)"',b[0]);assert m,b[0];msg=m[3].split();fields=dict(s.split('=',1)for s in msg[1:]);events.append(dict(gid=int(m[1]),ns=int(m[2]),event=msg[0],frames=list(dict.fromkeys(re.findall(r'\.Fn(\d+)', ''.join(b[1:])))),**fields))
 p=subprocess.Popen([str(t/'gotrace'),'-d=parsed',str(e/f'run-{i}.trace')],stdout=subprocess.PIPE,text=True)
 for line in p.stdout:
  if line.startswith('M='):consume(block);block=[line]
  else:block.append(line)
 consume(block);assert p.wait()==0;(e/f'events-{i}.json').write_text(json.dumps(events,indent=2))
 pending=collections.defaultdict(collections.deque);matched=[];active={};pages=[]
 for x in events:
  key=(x['instance'],x['pool']);kind=x['event']
  if kind=='enqueue':pending[(key,x['task'])].append(x)
  elif kind=='dequeue':
   q=pending[(key,x['task'])]
   if q:
    start=q.popleft();matched.append({'enqueue':start,'dequeue':x,'ms':(x['ns']-start['ns'])/1e6})
  elif kind=='page_wait_begin':active[(x['instance'],x['gid'],x['pool'])]=x
  elif kind=='page_wait_end':
   start=active.pop((x['instance'],x['gid'],x['pool']));pages.append({'start':start,'end':x,'ms':(x['ns']-start['ns'])/1e6})
 counts=collections.Counter(x['event']for x in events);longq=[x for x in matched if x['ms']>=100];longpages=[x for x in pages if x['ms']>=100]
 item={'run':i,'mode':'natural'if i%2==0 else'hold20','events':len(events),'counts':counts,'matched_tasks':len(matched),'unmatched_enqueues':sum(len(q)for q in pending.values()),'max_queue_ms':max([x['ms']for x in matched],default=0),'long_queue':longq,'max_page_wait_ms':max([x['ms']for x in pages],default=0),'long_pages':longpages}
 summary.append(item);print(i,item['mode'],'pending',counts['reject_pending'],'maxq',item['max_queue_ms'],'longq',len(longq),'page',item['max_page_wait_ms'],flush=True)
(e/'analysis.json').write_text(json.dumps(summary,indent=2))
