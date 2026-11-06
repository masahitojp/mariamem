from pathlib import Path
import json,collections,hashlib,sys,tarfile
e=Path(__file__).resolve().parent
check='--check' in sys.argv
def read(name):
 p=e/name
 if p.exists():return json.loads(p.read_text())
 with tarfile.open(e/'raw-evidence.tar.gz','r:gz') as a:return json.load(a.extractfile(name))
records=read('records.json');natural=[r for r in records if r['name'].startswith('natural-')]
rows=[];owner_counts=collections.Counter();threshold_counts=collections.Counter();scope_counts=collections.Counter();issues=[];runtime=[]
for r in records:
 for filename in r['notify_reports']:
  d=read(filename);assert not d['truncated'];events=d['events'] or [];waits={x['wait']:x for x in events if x['kind']=='wait_registered'}
  for x in events:
   o=x.get('owner')
   if not o:continue
   assert o['begin_ns']<=o['end_ns'] and o['page_matches'],(filename,x)
   assert o['expected_page']==o['page'] and o['expected_space']==o['space']
   if r in natural:scope_counts[x['kind']+':'+o['kind']]+=1
  for wid,start in waits.items():
   if not start.get('owner'):continue
   assert start['mutex']==start['owner']['block']+24
   related=[x for x in events if x.get('wait')==wid];ends=[x for x in related if x['kind']=='wait_return'];assert len(ends)==1
   resumes=[x for x in related if x['kind']=='wait_resume'];before=[x for x in related if x['kind']=='signal_before'];after=[x for x in related if x['kind']=='signal_after'];late=[x for x in related if x['kind']=='owner_still_waiting']
   assert len(late)<=1
   dur=(ends[0]['ns']-start['ns'])/1e6
   row={'run':r['name'],'child':d['child'],'wait':wid,'page':start.get('page',0),'space':start.get('space',0),'registered_to_return_ms':dur,'owner_at_registration':start['owner'],'threshold_sample':late[0].get('owner') if late else None,'threshold_before_first_signal':bool(late and before and late[0]['owner']['end_ns']<=min(x['ns'] for x in before)),'resume_ms':(resumes[0]['ns']-start['ns'])/1e6 if resumes else None,'signal_before_ms':(before[0]['ns']-start['ns'])/1e6 if before else None,'signal_after_ms':(after[0]['ns']-start['ns'])/1e6 if after else None}
   if r in natural:
    rows.append(row);owner_counts[start['owner']['kind']+':'+start['owner']['io_state']]+=1
    if late:threshold_counts[late[0]['owner']['kind']+':'+late[0]['owner']['io_state']]+=1
for r in natural:
 d=read(r['report']);vals=[x['update_ms'] for x in d['samples']];runtime.append({'run':r['name'],'parallel':r['parallel'],'children':len(vals),'max_update_ms':max(vals),'update_gt100':sum(v>100 for v in vals)})
slow=sum(r['update_gt100'] for r in runtime);long=[r for r in rows if r['registered_to_return_ms']>100]
result='NOT_REPRODUCED' if not slow else 'LONG_PAGE_WAIT_OBSERVED' if long else 'LONG_UPDATE_WITHOUT_LONG_PAGE_WAIT'
summary={'result':result,'runtime':runtime,'page_wait_count':len(rows),'page_wait_gt100_count':len(long),'registration_owner_counts':dict(owner_counts),'threshold_owner_counts':dict(threshold_counts),'all_owner_event_counts':dict(scope_counts),'waits':rows,'limits':['Samples are not coherent multi-field snapshots; stable owner reads do not exclude intervening transitions.','Threshold callback observes a registered wait not yet returned; compare it with signal-before to distinguish before-notification from after-close scheduling.','Short waits do not identify the old355ms holder. IO owner alone does not identify pre-submit work versus IO or completion queue delay.','No full ownership history, no new guest symbol map, no product/adoption/performance claim.']}
if check:
 assert summary==read('summary.json'),'summary mismatch'
 print('READ-ONLY REPLAY PASS')
else:(e/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps({k:v for k,v in summary.items() if k!='waits'},indent=2))
