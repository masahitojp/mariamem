import collections,json,re,subprocess
from pathlib import Path
w=Path(__file__).resolve().parents[1]; ev=w/'evidence'
results=[]
pattern=re.compile(r'Range(Begin|End|Active) Time=(\d+) Name="([^"]+)" Scope=(\S+)')
statepat=re.compile(r'StateTransition Time=(\d+) GoID=1 (\w+)->(\w+) Reason="([^"]*)"')
for p in sorted(ev.glob('*.trace')):
 proc=subprocess.Popen([str(w/'temp/tools/trace'),'-d=parsed',str(p)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
 starts={}; spans=[]; states=[]; open_state=None; unmatched=[]
 for line in proc.stdout:
  m=pattern.search(line)
  if m:
   kind,t,name,scope=m.groups();t=int(t);key=(name,scope)
   if kind=='Begin':
    if key in starts: unmatched.append({'duplicate_begin':key})
    starts[key]=t
   elif kind=='End':
    if key not in starts: unmatched.append({'missing_begin':key})
    else:spans.append({'name':name,'scope':scope,'begin_ns':starts.pop(key),'end_ns':t})
   elif kind=='Active':
    unmatched.append({'active_at_boundary':key})
  m=statepat.search(line)
  if m:
   t,old,new,reason=m.groups();t=int(t)
   if open_state is not None:states.append(dict(open_state,end_ns=t))
   open_state={'begin_ns':t,'state':new,'reason':reason}
 stderr=proc.stderr.read();rc=proc.wait();assert rc==0,(rc,stderr)
 groups=collections.defaultdict(list)
 for s in spans:groups[s['name']].append((s['end_ns']-s['begin_ns'])/1e9)
 state_groups=collections.defaultdict(list)
 for s in states:state_groups[s['state']+':'+s['reason']].append((s['end_ns']-s['begin_ns'])/1e9)
 summary=lambda g:{k:{'count':len(v),'sum_seconds':sum(v),'max_seconds':max(v)} for k,v in g.items()}
 row={'file':p.name,'ranges':summary(groups),'main_goroutine_states':summary(state_groups),'boundary_ranges':unmatched,'unclosed_ranges':list(starts),'spans':spans,'scope':'Range durations may overlap; main goroutine wait is the benchmark client, not guest CPU. No causal inference from overlap.'}
 results.append(row)
 print(p.name, json.dumps(row['ranges']),json.dumps(row['main_goroutine_states']))
(ev/'trace-ranges.json').write_text(json.dumps(results,indent=2))
