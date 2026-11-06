from pathlib import Path
import json,sys,statistics,math,csv,io,tarfile,collections
from undo_analysis import analyze_trace
E=Path(__file__).resolve().parent

def q(xs,p):a=sorted(xs);return a[min(len(a)-1,max(0,math.ceil(len(a)*p)-1))]
def stat(xs):return {'n':len(xs),'p50':statistics.median(xs),'p95':q(xs,.95),'max':max(xs)}
def read_trace(n):
 p=E/n
 if p.exists():return json.loads(p.read_text())
 with tarfile.open(E/'undo-traces.tar.gz') as a:return json.load(a.extractfile(n))
def analyze():
 records=json.loads((E/'records.json').read_text());assert len(records)==16
 assert sum(r['negative'] for r in records)==2 and sum(r['warmup'] for r in records)==2 and sum(r['diagnostic'] for r in records)==2
 processes=[];children=[];holder_rows=[];links=[];pages=[];qwaits=[];scopes=0;tracecount=0;maxevents=0;slowdiag=[];aborts=0
 for r in records:
  d=json.loads((E/r['report']).read_text());assert d['cleanup_complete'] and d['root_closed_before_forks']
  if r['negative']:assert not d['success'] and 'pristine oracle' in d['error'];continue
  assert d['success'] and len(d['samples'])==48 and {x['index'] for x in d['samples']}==set(range(48))
  fields=['retire_ms','wait_ms','close_ms','cleanup_ms','fork_ms','sql_ms','update_ms'];local=[]
  for x in d['samples']:
   assert x['oracle'] and x['cleanup_complete'] and all(x[k]>=0 for k in fields)
   assert x['retire_ms']+x['wait_ms']+x['close_ms']<=x['cleanup_ms']+.05
   row={'report':r['report'],'variant':r['variant'],'rep':r['rep'],'warmup':r['warmup'],'diagnostic':r['diagnostic'],'child':x['index'],**{k:x[k] for k in fields}}
   if r['diagnostic']:
    a=x['wait_trace'];assert a['success'] and a['idle_observed'] and a['checks'][-1]['active']==0
    if r['variant']=='notify':assert a['sleep_requests']==0
    row.update(sleep_requests=a['sleep_requests'],confirmation_ms=max(0,a['checks'][-1]['offset_ms']-max(0,a['idle_offset_ms'])))
    if x['update_ms']>100:slowdiag.append(row)
   local.append(row);children.append(row)
  process={'report':r['report'],'variant':r['variant'],'rep':r['rep'],'warmup':r['warmup'],'diagnostic':r['diagnostic'],'batch_ms':d['batch_ms'],'cpu_per_child_ms':(d['cpu_user_ms']+d['cpu_system_ms'])/48,'sql_gt100':sum(x['sql_ms']>100 for x in local),'update_gt100':sum(x['update_ms']>100 for x in local),'phases':{k:stat([x[k] for x in local]) for k in fields}}
  if r['diagnostic']:process['confirmation_ms']=stat([x['confirmation_ms'] for x in local])
  processes.append(process)
  if r['diagnostic']:assert len(r['trace_reports'])==48
  for name in r['trace_reports']:
   tr=read_trace(name);assert not tr['truncated'];events=tr['events'] or [];maxevents=max(maxevents,len(events));tracecount+=1
   a=analyze_trace(name,tr['child'],events);scopes+=a['purge_scopes'];aborts+=a['purge_aborts']
   for key,target in [('links',links),('background_page_waits',pages),('query_rseg_waits',qwaits)]:
    for x in a[key]:target.append(dict(x,report=r['report'],variant=r['variant'],trace=name))
   relevant={(x['thread'],x['scope']) for x in a['background_page_waits']}
   for event in events:
    if event['kind'] not in ['wait_registered','owner_still_waiting','purge_acquired','purge_release_before','purge_release_after']:continue
    if event['kind'].startswith('purge_') and (event['thread'],event.get('query')) not in relevant:continue
    own=event.get('owner') or {}
    holder_rows.append({'report':r['report'],'variant':r['variant'],'child':tr['child'],'kind':event['kind'],'ns':event['ns'],'thread':event['thread'],'role':event.get('role',''),'scope':event.get('query',''),'wait':event.get('wait',''),'held_rseg':event.get('held_rseg',''),'waiting_rseg':event.get('waiting_rseg',''),'ea':event.get('ea',''),'page':event.get('page',''),'space':event.get('space',''),'owner_kind':own.get('kind',''),'owner_before':own.get('owner_before',''),'owner_after':own.get('owner_after',''),'io_state':own.get('io_state','')})
 pairs=[]
 for rep in range(5):
  a=[x for x in processes if x['rep']==rep and not x['warmup'] and not x['diagnostic']];assert len(a)==2 and {x['variant'] for x in a}=={'poll','notify'};b=next(x for x in a if x['variant']=='poll');c=next(x for x in a if x['variant']=='notify')
  pairs.append({'rep':rep,'wait_reduction_ms':b['phases']['wait_ms']['p50']-c['phases']['wait_ms']['p50'],'cleanup_reduction_ms':b['phases']['cleanup_ms']['p50']-c['phases']['cleanup_ms']['p50'],'batch_reduction_pct':100*(b['batch_ms']-c['batch_ms'])/b['batch_ms'],'cpu_reduction_pct':100*(b['cpu_per_child_ms']-c['cpu_per_child_ms'])/b['cpu_per_child_ms']})
 groups={}
 for variant in ['poll','notify']:
  rr=[x for x in children if x['variant']==variant and not x['warmup'] and not x['diagnostic']];pp=[x for x in processes if x['variant']==variant and not x['warmup'] and not x['diagnostic']];assert len(rr)==240 and len(pp)==5
  groups[variant]={'phases':{k:stat([x[k] for x in rr]) for k in fields},'batch_ms':[x['batch_ms'] for x in pp],'cpu_per_child_ms':[x['cpu_per_child_ms'] for x in pp],'sql_gt100':sum(x['sql_gt100'] for x in pp),'update_gt100':sum(x['update_gt100'] for x in pp)}
 gates={'wait_pairs_ge3ms':sum(x['wait_reduction_ms']>=3 for x in pairs),'cleanup_pairs_ge2ms':sum(x['cleanup_reduction_ms']>=2 for x in pairs),'batch_median_reduction_pct':statistics.median(x['batch_reduction_pct'] for x in pairs),'cpu_median_reduction_pct':statistics.median(x['cpu_reduction_pct'] for x in pairs)}
 lead=gates['wait_pairs_ge3ms']>=4 and gates['cleanup_pairs_ge2ms']>=4;guard=gates['batch_median_reduction_pct']>=-5 and gates['cpu_median_reduction_pct']>=-5
 gates.update(local_cleanup_lead_pass=lead,batch_guard_pass=gates['batch_median_reduction_pct']>=-5,cpu_guard_pass=gates['cpu_median_reduction_pct']>=-5)
 out={'result':'LOCAL_CANDIDATE_LEAD' if lead and guard else 'CONDITIONAL_OR_DEFER','gates':gates,'groups':groups,'pairs':pairs,'processes':processes,'undo':{'traces':tracecount,'purge_scopes':scopes,'purge_aborts':aborts,'max_events_per_child':maxevents,'query_rseg_waits':qwaits,'background_page_waits':pages,'links':links,'slow_diagnostic_updates':slowdiag,'owner_samples':dict(collections.Counter(x['owner_kind'] for x in holder_rows if x['owner_kind']))}}
 return out,children,holder_rows

def csvtext(rows):
 buf=io.StringIO(newline='');writer=csv.DictWriter(buf,fieldnames=sorted(set().union(*(r.keys() for r in rows))),lineterminator='\n');writer.writeheader();writer.writerows(rows);return buf.getvalue()
if __name__=='__main__':
 out,children,holders=analyze();outputs={'summary.json':json.dumps(out,indent=2)+'\n','children.csv':csvtext(children),'holders.csv':csvtext(holders)}
 if '--check' in sys.argv:
  for n,v in outputs.items():assert (E/n).read_text()==v,n
  print('READ-ONLY REPLAY PASS')
 else:
  for n,v in outputs.items():(E/n).write_text(v)
  print(json.dumps({'result':out['result'],'gates':out['gates'],'groups':out['groups'],'undo_counts':{k:(len(v) if isinstance(v,list) else v) for k,v in out['undo'].items()}},indent=2))
