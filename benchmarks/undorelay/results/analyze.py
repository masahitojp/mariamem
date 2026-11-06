from pathlib import Path
import json,statistics,sys,tarfile,collections
E=Path(__file__).resolve().parent

def read(n):
 p=E/n
 if p.exists():return json.loads(p.read_text())
 with tarfile.open(E/'raw-evidence.tar.gz') as a:return json.load(a.extractfile(n))
def one(events,kind,field,value):
 xs=[x for x in events if x['kind']==kind and x.get(field)==value]
 return xs[0] if len(xs)==1 else None

def link(q,b,h):
 # All three inputs are already within one instance trace. Keep child in each
 # record so mutation tests and future aggregation cannot erase that boundary.
 return (q['child']==b['child']==h['child'] and q['rseg']==b['rseg']==h['rseg'] and q['ea']==q['rseg']+4 and b['scope']==h['scope'] and b['thread']==h['thread'] and b['page_matches'] and h['acquired']<=b['start']<=b['end']<=h['release_before'] and max(q['start'],b['start'])<min(q['end'],b['end']))
def analyze_trace(name,child,events):
 scopes=[];pagewaits=[];qwaits=[];pairs=[];aborts=[x for x in events if x['kind']=='purge_scope_abort']
 for x in events:
  if x.get('owner'):assert x['owner']['page_matches'],(name,x)
  if x['kind']=='purge_acquired':
   rb=one(events,'purge_release_before','query',x['query']);ra=one(events,'purge_release_after','query',x['query']);end=one(events,'purge_scope_end','query',x['query'])
   if rb and ra and end:
    assert x['ns']<=rb['ns']<=ra['ns']<=end['ns']
    scopes.append({'child':child,'scope':x['query'],'thread':x['thread'],'rseg':x['held_rseg'],'acquired':x['ns'],'release_before':rb['ns'],'release_after':ra['ns'],'scope_end':end['ns']})
  if x['kind']!='wait_registered':continue
  end=one(events,'wait_return','wait',x['wait']);resume=one(events,'wait_resume','wait',x['wait']);assert end,(name,x)
  rel=[v for v in events if v.get('wait')==x['wait']];before=[v for v in rel if v['kind']=='signal_before'];after=[v for v in rel if v['kind']=='signal_after'];late=[v for v in rel if v['kind']=='owner_still_waiting']
  rec={'child':child,'scope':x.get('query',0),'thread':x['thread'],'wait':x['wait'],'ea':x['ea'],'start':x['ns'],'end':resume['ns'] if resume else end['ns'],'returned':end['ns'],'resume':resume['ns'] if resume else None,'ms':((resume['ns'] if resume else end['ns'])-x['ns'])/1e6,'signal_before':before[0]['ns'] if before else None,'signal_after':after[0]['ns'] if after else None,'notify':before[0].get('notify') if before else None}
  if x.get('role')=='update' and x.get('waiting_rseg'):
   rec['rseg']=x['waiting_rseg'];qwaits.append(rec)
  if x.get('role')=='purge' and x.get('owner'):
   assert x['held_rseg']==x['rseg'];assert x['mutex']==x['owner']['block']+24
   rec.update(rseg=x['rseg'],page=x.get('page',0),space=x.get('space',0),page_matches=x['owner']['page_matches'],owner_at_registration=x['owner'],owner_at_threshold=late[0]['owner'] if late else None)
   ends=[z for z in events if z['kind']=='page_mutex_slow_end' and z.get('query')==rec['scope'] and z.get('thread')==rec['thread'] and z.get('mutex')==x['mutex'] and z['ns']>=rec['returned']]
   rec['page_mutex_return']=min((z['ns'] for z in ends),default=None)
   gets=[z for z in events if z['kind']=='rseg_page_end' and z.get('query')==rec['scope'] and z.get('thread')==rec['thread'] and z.get('rseg')==rec['rseg'] and rec['page_mutex_return'] is not None and z['ns']>=rec['page_mutex_return']]
   rec['header_get_return']=min((z['ns'] for z in gets),default=None)
   pagewaits.append(rec)
 for q in qwaits:
  for h in scopes:
   for b in pagewaits:
    if not link(q,b,h):continue
    nt=one(events,'notify_return','notify',q['notify']) if q['notify'] else None
    releasing_thread_matches=bool(nt and nt['thread']==h['thread'] and nt['ea']==q['ea'])
    order=bool(b['header_get_return'] is not None and b['header_get_return']<=h['release_before'] and q['signal_before'] is not None and q['resume'] is not None and b['end']<=h['release_before']<=h['release_after']<=q['signal_before']<=q['resume'])
    pairs.append({'trace':name,'child':child,'query_wait':q,'purge_hold':h,'background_page_wait':b,'matched_releasing_thread':releasing_thread_matches,'release_order_observed':order,'overlap_ms':(min(q['end'],b['end'])-max(q['start'],b['start']))/1e6,'conservative_pre_release_overlap_ms':(min(q['end'],b['end'],h['release_before'])-max(q['start'],b['start'],h['acquired']))/1e6})
 return {'purge_scopes':len(scopes),'purge_aborts':len(aborts),'query_rseg_waits':qwaits,'background_page_waits':pagewaits,'links':pairs}

def main():
 records=read('records.json');assert len(records)==6
 processes=[];slow=[];alllinks=[];allpages=[];allq=[];capture=[];nscopes=aborts=0;counts=[]
 for r in records:
  d=read(r['report']);assert d['cleanup_complete'] and d['root_closed_before_forks']
  if not r['negative']:assert d['success'] and len(d['samples'])==r['count'] and all(x['oracle'] and x['cleanup_complete'] for x in d['samples'])
  vals=[x['update_ms'] for x in d['samples']];processes.append({'report':r['report'],'primary':r['repetition']>=0,'warmup':r['warmup'],'preflight':r['preflight'],'negative':r['negative'],'children':len(vals),'max_update_ms':max(vals,default=None),'update_gt100':sum(v>100 for v in vals),'batch_ms':d['batch_ms']})
  for x in d['samples']:
   if x['update_ms']>100:slow.append({'report':r['report'],'primary':r['repetition']>=0,'warmup':r['warmup'],'preflight':r['preflight'],'sample':x})
  for f in r['capture_files']:
   if f.endswith('.json'):capture.append(dict(read(f),file=f,report=r['report']))
  for n in r['trace_reports']:
   tr=read(n);assert not tr['truncated'],n;events=tr['events'] or [];counts.append(len(events));a=analyze_trace(n,tr['child'],events);nscopes+=a['purge_scopes'];aborts+=a['purge_aborts']
   for k,dest in [('links',alllinks),('background_page_waits',allpages),('query_rseg_waits',allq)]:
    for x in a[k]:dest.append(dict(x,report=r['report'],primary=r['repetition']>=0,warmup=r['warmup'],preflight=r['preflight']))
 long=[x for x in alllinks if x['query_wait']['ms']>100 and x['matched_releasing_thread'] and x['release_order_observed']]
 result='NOT_REPRODUCED' if not slow else 'LONG_RELAY_BOUND' if long else 'LONG_UPDATE_WITHOUT_BOUND_RELAY'
 out={'result':result,'mechanism_result':('SHORT_RELAY_BOUND' if alllinks and not long else 'LONG_RELAY_BOUND' if long else 'NO_BOUND_RELAY'),'processes':processes,'slow_updates':slow,'purge_scopes':nscopes,'purge_aborts':aborts,'max_events_per_child':max(counts,default=0),'query_rseg_waits':allq,'background_page_waits':allpages,'links':alllinks,'long_bound_links':long,'captures':capture,'limits':read('plan.json')['limits'],'stopped_without_extra_runs':True}
 if '--check' in sys.argv:assert out==read('summary.json');print('READ-ONLY REPLAY PASS')
 else:(E/'summary.json').write_text(json.dumps(out,indent=2)+'\n')
 print(json.dumps({'result':result,'processes':processes,'purge_scopes':nscopes,'purge_aborts':aborts,'max_events_per_child':out['max_events_per_child'],'query_rseg_waits':len(allq),'background_page_waits':len(allpages),'links':len(alllinks),'long_links':len(long)},indent=2))
if __name__=='__main__':main()
