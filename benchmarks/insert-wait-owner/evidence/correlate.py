from pathlib import Path
import json
w=Path(__file__).resolve().parent.parent;e=w/'evidence';a=json.loads((e/'analysis.json').read_text());out=[]
for i in range(8):
 xs=json.loads((e/f'events-{i}.json').read_text());active={};spans=[]
 for x in xs:
  if x['event']=='page_wait_begin':active[x['gid']]=x
  elif x['event']=='page_wait_end':
   s=active.pop(x['gid']);spans.append((x['ns']-s['ns'],s,x))
 _,start,end=max(spans,key=lambda x:x[0]);module=start['module'];page=start['l0'];between=[x for x in xs if x['module']==module and start['ns']<=x['ns']<=end['ns']]
 complete=[x for x in between if x['event']=='page_complete_begin'and x['l0']==page]
 waits=[x for x in between if x['gid']==start['gid'] and x['event']=='futex_wait_begin']
 row={'run':i,'page_wait_start':start,'page_wait_end':end,'page_complete':complete,'futex_waits':waits}
 if complete:
  c=complete[-1];cg=c['gid'];ce=c['ns'];execs=[x for x in xs if x['module']==module and x['gid']==cg and x['event']=='task_execute_begin'and x['ns']<=ce]
  if execs:
   ex=execs[-1];subs=[x for x in xs if x['module']==module and x['event']=='submit_end'and x['l1']==ex['l0']and x['ns']<=ex['ns']]
   row['execute']=ex;row['submit_end']=subs[-1]if subs else None
   if subs:row['submit_return_to_execute_ms']=(ex['ns']-subs[-1]['ns'])/1e6
  row['matching_wakes']=[x for x in between if x['event']=='futex_wake'and x['gid']==cg and any(y['addr']==x['addr']for y in waits)]
 out.append(row)
(e/'matched-page-examples.json').write_text(json.dumps(out,indent=2))
print([(x['run'],len(x['page_complete']),len(x['futex_waits']),len(x.get('matching_wakes',[])),x.get('submit_return_to_execute_ms'))for x in out])
