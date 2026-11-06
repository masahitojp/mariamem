from pathlib import Path
import json,sys,statistics,math,csv,io,tarfile,random,collections
from undo_analysis import analyze_trace
E=Path(__file__).resolve().parent
_archives={}
def read(n):
 p=E/n
 if p.exists():return json.loads(p.read_text())
 archive='undo-traces.tar.gz' if '-undo-child-' in n else 'raw-processes.tar.gz'
 key=str(E/archive)
 if key not in _archives:
  with tarfile.open(E/archive) as a:_archives[key]={m.name:a.extractfile(m).read() for m in a if m.isfile()}
 return json.loads(_archives[key][n])
def q(a,p):s=sorted(a);return s[min(len(s)-1,max(0,math.ceil(len(s)*p)-1))]
def stat(a):return {'n':len(a),'p50':statistics.median(a),'p95':q(a,.95),'max':max(a)}
def peak(intervals):
 n=hi=0
 for _,d in sorted([(a,1) for a,b in intervals]+[(b,-1) for a,b in intervals]):n+=d;hi=max(hi,n)
 assert n==0;return hi
def analyze():
 records=read('records.json');assert len(records)==134
 assert sum(r['negative'] for r in records)==2 and sum(r['warmup'] for r in records)==6 and sum(r['diagnostic'] for r in records)==6
 for cap in [1,2,4]:
  for variant in ['poll','notify']:
   assert sum(x['cap']==cap and x['variant']==variant and x['warmup'] for x in records)==1
   assert sum(x['cap']==cap and x['variant']==variant and x['diagnostic'] for x in records)==1
 fields=['retire_ms','wait_ms','close_ms','cleanup_ms','fork_ms','sql_ms','update_ms'];processes=[];rows=[];holder_rows=[];pages=[];links=[];qwaits=[];nscopes=aborts=traces=maximum=0
 for r in records:
  d=read(r['report']);assert d['cleanup_complete'] and d['root_closed_before_forks'];assert d['max_forks']==d['resolved_max_forks']==r['cap']
  if r['negative']:assert not d['success'] and 'pristine oracle' in d['error'];continue
  assert d['success'] and d['parallel']==4 and len(d['samples'])==48 and {x['index'] for x in d['samples']}==set(range(48))
  assert peak([(x['child_ready_offset_ms'],x['disposed_offset_ms']) for x in d['samples']])<=r['cap']
  local=[]
  for x in d['samples']:
   assert x['oracle'] and x['cleanup_complete'] and all(x[k]>=0 for k in fields)
   assert x['disposed_offset_ms']>=x['child_ready_offset_ms']>0
   assert x['retire_ms']+x['wait_ms']+x['close_ms']<=x['cleanup_ms']+.05
   row={'report':r['report'],'cap':r['cap'],'variant':r['variant'],'rep':r['rep'],'warmup':r['warmup'],'diagnostic':r['diagnostic'],'child':x['index'],**{k:x[k] for k in fields}}
   if r['diagnostic']:
    tr=x['wait_trace'];assert tr['success'] and tr['idle_observed'] and tr['checks'][-1]['active']==0
    if r['variant']=='notify':assert tr['sleep_requests']==0
    row['confirmation_ms']=max(0,tr['checks'][-1]['offset_ms']-max(0,tr['idle_offset_ms']))
   local.append(row);rows.append(row)
  pp={'report':r['report'],'cap':r['cap'],'variant':r['variant'],'rep':r['rep'],'warmup':r['warmup'],'diagnostic':r['diagnostic'],'batch_ms':d['batch_ms'],'cpu_per_child_ms':(d['cpu_user_ms']+d['cpu_system_ms'])/48,'sql_gt100':sum(x['sql_ms']>100 for x in local),'update_gt100':sum(x['update_ms']>100 for x in local),'peak_ready_children':r['peak_ready_children'],'phases':{k:stat([x[k] for x in local]) for k in fields}}
  if r['diagnostic']:pp['confirmation_ms']=stat([x['confirmation_ms'] for x in local])
  processes.append(pp)
  if r['diagnostic']:assert len(r['trace_reports'])==48
  for n in r['trace_reports']:
   tr=read(n);assert not tr['truncated'];ev=tr['events'] or [];maximum=max(maximum,len(ev));traces+=1;a=analyze_trace(n,tr['child'],ev);nscopes+=a['purge_scopes'];aborts+=a['purge_aborts']
   for k,target in [('links',links),('background_page_waits',pages),('query_rseg_waits',qwaits)]:
    for v in a[k]:target.append(dict(v,trace=n,report=r['report'],cap=r['cap'],variant=r['variant']))
   relevant={(x['thread'],x['scope']) for x in a['background_page_waits']}
   for v in ev:
    if v['kind'] not in ['wait_registered','owner_still_waiting','purge_acquired','purge_release_before','purge_release_after']:continue
    if v['kind'].startswith('purge_') and (v['thread'],v.get('query')) not in relevant:continue
    own=v.get('owner') or {};holder_rows.append({'report':r['report'],'cap':r['cap'],'variant':r['variant'],'child':tr['child'],'kind':v['kind'],'ns':v['ns'],'thread':v['thread'],'role':v.get('role',''),'scope':v.get('query',''),'held_rseg':v.get('held_rseg',''),'waiting_rseg':v.get('waiting_rseg',''),'ea':v.get('ea',''),'page':v.get('page',''),'space':v.get('space',''),'owner_kind':own.get('kind',''),'owner_before':own.get('owner_before',''),'owner_after':own.get('owner_after',''),'io_state':own.get('io_state','')})
 plan=read('plan.json');paired={};cells={};rng=random.Random(117);draws=[[rng.randrange(20) for _ in range(20)] for _ in range(10000)]
 def ci(a):return [q(a,.025),q(a,.975)]
 for cap in [1,2,4]:
  pairs=[]
  for rep in range(20):
   pp=[p for p in processes if p['cap']==cap and p['rep']==rep and not p['diagnostic'] and not p['warmup']];assert len(pp)==2 and {x['variant'] for x in pp}=={'poll','notify'}
   b=next(x for x in pp if x['variant']=='poll');n=next(x for x in pp if x['variant']=='notify');values={}
   for name,bv,nv in [('wall_ms',b['batch_ms'],n['batch_ms']),('cpu_per_child_ms',b['cpu_per_child_ms'],n['cpu_per_child_ms'])]+[(f,b['phases'][f]['p50'],n['phases'][f]['p50']) for f in ['wait_ms','cleanup_ms','close_ms','fork_ms']]:values[name]={'poll':bv,'notify':nv,'difference':nv-bv,'change_pct':100*(nv/bv-1)}
   cell=next(x for x in plan['protocol']['rounds'][rep]['cells'] if x['cap']==cap);pairs.append({'rep':rep,'cap':cap,'first':cell['order'][0],'values':values})
  paired[str(cap)]=pairs;metrics={}
  for name in pairs[0]['values']:
   diffs=[p['values'][name]['difference'] for p in pairs];pct=[p['values'][name]['change_pct'] for p in pairs];bp=[p['values'][name]['poll'] for p in pairs];np=[p['values'][name]['notify'] for p in pairs]
   metrics[name]={'poll_mean':statistics.mean(bp),'notify_mean':statistics.mean(np),'poll_median':statistics.median(bp),'notify_median':statistics.median(np),'mean_difference':statistics.mean(diffs),'mean_difference_bootstrap95':ci([sum(diffs[i] for i in draw)/20 for draw in draws]),'median_pair_change_pct':statistics.median(pct),'median_pair_change_pct_bootstrap95':ci([statistics.median(pct[i] for i in draw) for draw in draws]),'notify_lower_pairs':sum(x<0 for x in diffs),'pairs':20}
  cells[str(cap)]={'metrics':metrics,'tails':{v:{'sql_gt100':sum(x['sql_gt100'] for x in processes if x['cap']==cap and x['variant']==v and not x['diagnostic'] and not x['warmup']),'update_gt100':sum(x['update_gt100'] for x in processes if x['cap']==cap and x['variant']==v and not x['diagnostic'] and not x['warmup'])} for v in ['poll','notify']},'ready_peak_max':max(x['peak_ready_children'] for x in processes if x['cap']==cap),'order_cpu_change_pct_mean':{first:statistics.mean(x['values']['cpu_per_child_ms']['change_pct'] for x in pairs if x['first']==first) for first in ['poll','notify']}}
 a=[paired['4'][i]['values']['cpu_per_child_ms']['change_pct']-paired['1'][i]['values']['cpu_per_child_ms']['change_pct'] for i in range(20)]
 contrasts={'cap4_minus_cap1_cpu_change_percentage_points':{'mean':statistics.mean(a),'mean_bootstrap95':ci([sum(a[i] for i in draw)/20 for draw in draws]),'median':statistics.median(a)}}
 out={'result':'FIXED_CAP_MATRIX_COMPLETE','cells':cells,'contrasts':contrasts,'paired_values':paired,'processes':processes,'undo':{'traces':traces,'purge_scopes':nscopes,'purge_aborts':aborts,'max_events_per_child':maximum,'query_rseg_waits':qwaits,'background_page_waits':pages,'links':links,'owner_samples':dict(collections.Counter(x['owner_kind'] for x in holder_rows if x['owner_kind']))},'limits':['Four callers at every cap; cap1 is not one OS thread','Fork elapsed includes admission capacity wait','Ready/disposed census excludes startup interval; immutable resolved cap and unchanged product limiter cover admission','Only this Mac/fixture; whole-round bootstrap does not resolve temporal dependence','All SQL tails retained; no cause assigned to primary tails without diagnostic logs']}
 return out,rows,holder_rows

def csvtext(rows):
 b=io.StringIO(newline='');w=csv.DictWriter(b,fieldnames=sorted(set().union(*(r.keys() for r in rows))),lineterminator='\n');w.writeheader();w.writerows(rows);return b.getvalue()
if __name__=='__main__':
 d,rows,holders=analyze();outputs={'summary.json':json.dumps(d,indent=2)+'\n','children.csv':csvtext(rows),'holders.csv':csvtext(holders)}
 if '--check' in sys.argv:
  for n,v in outputs.items():assert (E/n).read_text()==v,n
  print('READ-ONLY REPLAY PASS')
 else:
  for n,v in outputs.items():(E/n).write_text(v)
  print(json.dumps({'result':d['result'],'cells':d['cells'],'contrasts':d['contrasts'],'undo_counts':{k:len(v) if isinstance(v,list) else v for k,v in d['undo'].items()}},indent=2))
