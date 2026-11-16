from pathlib import Path
import subprocess,json,re,collections
w=Path(__file__).resolve().parent.parent;t=w/'temp';e=w/'evidence';summary=[]
for i in range(8):
 events=[];p=subprocess.Popen([str(t/'gotrace'),'-d=parsed',str(e/f'run-{i}.trace')],stdout=subprocess.PIPE,text=True)
 for line in p.stdout:
  if ' Category="owner" 'not in line:continue
  m=re.search(r'G=(\d+) Log Time=(\d+).*Message="([^"]+)"',line)
  if not m:raise ValueError(line)
  msg=m[3].split();fields=dict(s.split('=',1)for s in msg[1:]);events.append(dict(gid=int(m[1]),ns=int(m[2]),event=msg[0],**fields))
 assert p.wait()==0
 (e/f'events-{i}.json').write_text(json.dumps(events,indent=2))
 stacks={};waits=[];pages=[];pending=collections.defaultdict(collections.deque);queues=[]
 for x in events:
  kind=x['event'];g=x['gid'];module=x['module']
  if kind in ['futex_wait_begin','page_wait_begin']:stacks[(g,kind)]=x
  elif kind in ['futex_wait_end','page_wait_end']:
   start=stacks.pop((g,kind.replace('_end','_begin')),None)
   if start:
    item={'start':start,'end':x,'ms':(x['ns']-start['ns'])/1e6}
    (waits if kind.startswith('futex')else pages).append(item)
  if kind=='submit_begin':pending[(module,x['l1'])].append(x)
  elif kind=='task_execute_begin':
   q=pending[(module,x['l0'])]
   if q:
    start=q.popleft();queues.append({'submit':start,'execute':x,'entry_to_execute_ms':(x['ns']-start['ns'])/1e6})
 longpages=[x for x in pages if x['ms']>=100];longwaits=[x for x in waits if x['ms']>=100];longq=[x for x in queues if x['entry_to_execute_ms']>=100]
 item={'run':i,'events':len(events),'long_pages':longpages,'long_waits':longwaits,'long_tasks':longq,'max_page_ms':max([x['ms']for x in pages],default=0),'max_submit_to_execute_ms':max([x['entry_to_execute_ms']for x in queues],default=0)};summary.append(item)
 print(i,len(events),'page',item['max_page_ms'],'task',item['max_submit_to_execute_ms'],'longpages',len(longpages),flush=True)
(e/'analysis.json').write_text(json.dumps(summary,indent=2))
