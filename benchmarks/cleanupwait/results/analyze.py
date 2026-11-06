from pathlib import Path
import json,sys,math,statistics,csv,io
E=Path(__file__).resolve().parent

def quant(xs,p):
 s=sorted(xs);return s[min(len(s)-1,max(0,math.ceil(len(s)*p)-1))]
def stats(xs):return {'n':len(xs),'p50':statistics.median(xs),'p95':quant(xs,.95),'max':max(xs)}
def analyze(e):
 records=json.loads((e/'records.json').read_text());rows=[];processes=[]
 assert len(records)==9 and sum(x['negative'] for x in records)==1 and sum(x['warmup'] for x in records)==2
 for rec in records:
  d=json.loads((e/rec['report']).read_text());assert d['cleanup_complete']
  if rec['negative']:
   assert not d['success'] and 'pristine oracle' in d['error'];continue
  assert d['success'] and len(d['samples'])==48 and {s['index'] for s in d['samples']}==set(range(48))
  local=[]
  for s in d['samples']:
   assert s['oracle'] and s['cleanup_complete']
   assert s['retire_ms']+s['wait_ms']+s['close_ms']<=s['cleanup_ms']+.05
   row={'process':rec['report'],'mode':rec['mode'],'warmup':rec['warmup'],'child':s['index'],**{k:s[k] for k in ['fork_ms','sql_ms','retire_ms','wait_ms','close_ms','cleanup_ms']}}
   if rec['mode']=='diagnostic':
    q=s['wait_trace'];checks=q['checks'];assert q['success'] and q['idle_observed'] and checks[-1]['active']==0
    assert q['sleep_requests']==len(checks)-1
    # The successful Active observation precedes diagnostic callback/serialization.
    row.update(sleep_requests=q['sleep_requests'],initial_active=checks[0]['active'],idle_offset_ms=q['idle_offset_ms'],idle_to_observe_ms=max(0,checks[-1]['offset_ms']-q['idle_offset_ms']),confirmation_within_wait_ms=max(0,checks[-1]['offset_ms']-max(0,q['idle_offset_ms'])))
    assert row['confirmation_within_wait_ms']<=s['wait_ms']+.05
   rows.append(row);local.append(row)
  process={'report':rec['report'],'mode':rec['mode'],'warmup':rec['warmup'],'batch_ms':d['batch_ms'],'cpu_per_child_ms':(d['cpu_user_ms']+d['cpu_system_ms'])/48,'lifetime_max_rss_bytes':d['lifetime_max_rss_bytes'],'sql_gt100':sum(x['sql_ms']>100 for x in local),'phases':{k:stats([x[k] for x in local]) for k in ['fork_ms','retire_ms','wait_ms','close_ms','cleanup_ms']}}
  if rec['mode']=='diagnostic':
   process.update(confirmation=stats([x['confirmation_within_wait_ms'] for x in local]),sleeping_children=sum(x['sleep_requests']>0 for x in local),median_wait_fraction=statistics.median(x['wait_ms']/x['cleanup_ms'] for x in local))
  processes.append(process)
 groups={}
 for mode in ['ordinary','diagnostic']:
  pp=[p for p in processes if p['mode']==mode and not p['warmup']];rr=[r for r in rows if r['mode']==mode and not r['warmup']];assert len(pp)==3 and len(rr)==144
  groups[mode]={'children':len(rr),'batch_ms':[p['batch_ms'] for p in pp],'cpu_per_child_ms':[p['cpu_per_child_ms'] for p in pp],'sql_gt100':sum(p['sql_gt100'] for p in pp),'phases':{k:stats([r[k] for r in rr]) for k in ['fork_ms','retire_ms','wait_ms','close_ms','cleanup_ms']},'process_medians':{k:[p['phases'][k]['p50'] for p in pp] for k in ['retire_ms','wait_ms','close_ms','cleanup_ms']}}
  if mode=='diagnostic':
   groups[mode].update(confirmation=stats([r['confirmation_within_wait_ms'] for r in rr]),idle_to_observe=stats([r['idle_to_observe_ms'] for r in rr]),sleep_counts={str(n):sum(r['sleep_requests']==n for r in rr) for n in sorted(set(r['sleep_requests'] for r in rr))},material_processes=sum(p['confirmation']['p50']>=1 and p['median_wait_fraction']>=.2 for p in pp))
 result={'result':'MATERIAL_POLLING_LEAD' if groups['diagnostic']['material_processes']>=2 else 'SMALL_OR_INCONCLUSIVE','groups':groups,'processes':processes,'limits':['Diagnostic observer overhead not calibrated away','No event-notification implementation or speedup claim','Session deletion is eligible Active=0, not full guest disposal','Lifetime peak RSS is not retained-child RSS','No prior cohort merged; all SQL tails retained']}
 return result,rows
if __name__=='__main__':
 result,rows=analyze(E);raw=json.dumps(result,indent=2)+'\n';keys=sorted(set().union(*(r.keys() for r in rows)));buf=io.StringIO(newline='');writer=csv.DictWriter(buf,fieldnames=keys,lineterminator='\n');writer.writeheader();writer.writerows(rows)
 if '--check' in sys.argv:
  assert (E/'summary.json').read_text()==raw;assert (E/'children.csv').read_text()==buf.getvalue();print('READ-ONLY REPLAY PASS')
 else:(E/'summary.json').write_text(raw);(E/'children.csv').write_text(buf.getvalue());print(raw)
