"""Read-only replay of compact controls; --reduce consumes the original bounded events."""
import argparse,copy,csv,hashlib,io,json,pathlib,statistics
P=pathlib.Path(__file__).resolve().parent
PLAN=json.loads((P/'plan.json').read_text())
HOLDS={x for x in PLAN['controls'] if x.startswith('pending_unreported_')}
def require(v,m):
 if not v: raise ValueError(m)
def validate(rows):
 expected={(a,str(c),str(r)) for a in PLAN['controls'] for c in PLAN['concurrency'] for r in range(1,PLAN['repetitions']+1)}
 require(len(rows)==len(expected),'case count')
 require({(x['arm'],str(x['concurrency_requested']),str(x['repetition'])) for x in rows}==expected,'case identities')
 for x in rows:
  arm=x['arm'];n=lambda k:int(x[k]);f=lambda k:float(x[k])
  require(x['result']=='PASS','result')
  require(n('pending_refusals')==(0 if arm in ('late_submit_unreported','fixed_pool') else 1),'pending refusal')
  require(n('workers_created')==n('workers_retired')==n('spawn_calls')==n('pending_clears')==(1 if arm=='pending_unreported_release' else 2),'worker balance')
  require(n('task_refs_after')==n('queue_after')==0,'cleanup')
  require(n('task_begins')==n('task_ends')==(3 if arm=='pending_unreported_submit' else 2),'task balance')
  require(n('maintenance_calls')==(2 if arm=='pending_unreported_maintenance' else 1),'maintenance count')
  require(n('wait_begin_calls')==(1 if arm=='pending_reported' else 0),'wait declaration')
  require(n('explicit_triggers')==(1 if arm in HOLDS else 0),'trigger count')
  if arm in HOLDS:
   require([n(k) for k in ('queued_before','active_before','waiting_before','long_before','dequeued_before')]==[1,1,0,0,1],'stalled queue state')
   require(50<=f('synthetic_hold_ms')<250,'synthetic hold')
   require(f('trigger_to_next_task_ms')>=0,'progress after trigger')
 return {'result':'PASS_CONTROLLED_NATIVE_MECHANISM','cases':len(rows),'controls':{a:{'passed':sum(x['arm']==a for x in rows)} for a in PLAN['controls']},'natural_sql_cases':0,'guest_runs':0,'causal_attribution_to_previous_prepare':'UNPROVEN'}
def reduce(raw,out):
 rows=[]
 for x in raw:
  events=x['events']; count=lambda k:sum(e['kind']==k for e in events)
  require(len(events)<128 and events==sorted(events,key=lambda e:e['ms']),'bounded monotonic events')
  for kind in ('maintenance','spawn_call','pending_clear','task_begin','task_end'):require(count(kind)>0,'nonempty events')
  r={k:x[k] for k in ('arm','concurrency_requested','repetition','result','pending_refusals','synthetic_hold_ms','workers_created','task_refs_after','queue_after')}
  # Upstream detaches std::threads; its destructor waits for worker_end.
  # The original harness label "workers_joined" counts destroy callbacks, not OS join.
  r['workers_retired']=x['workers_joined']
  for k,v in x['before_trigger'].items():r[k+'_before']=v
  for key,kind in [('spawn_calls','spawn_call'),('pending_clears','pending_clear'),('task_begins','task_begin'),('task_ends','task_end'),('maintenance_calls','maintenance'),('wait_begin_calls','wait_begin'),('explicit_triggers','explicit_trigger')]:r[key]=count(kind)
  r['trigger_to_next_task_ms']=''
  if x['arm'] in HOLDS:
   triggers=[e['ms'] for e in events if e['kind']=='explicit_trigger'];require(len(triggers)==1,'unique trigger');at=triggers[0]
   begins=[e['ms'] for e in events if e['kind']=='task_begin'];require(sum(t<at for t in begins)==1,'one blocked predecessor')
   require(count('pending_refusal')==1,'observed refusal')
   refused=next(e['ms'] for e in events if e['kind']=='pending_refusal');clear=next(e['ms'] for e in events if e['kind']=='pending_clear')
   require(refused<clear<begins[0]<at,'forced interleaving')
   r['trigger_to_next_task_ms']=min(t for t in begins if t>=at)-at
  rows.append(r)
 summary=validate(rows)
 with (out/'cases.csv').open('w') as f:
  w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
 (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
 examples=[x for x in raw if x['repetition']==1 and x['concurrency_requested']==16]
 (out/'examples.json').write_text(json.dumps(examples,indent=2)+'\n')
 return summary
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--reduce',type=pathlib.Path);p.add_argument('--check',action='store_true');p.add_argument('--output',type=pathlib.Path);a=p.parse_args();out=a.output or P/'results'
 if a.reduce and a.output is None:p.error('--reduce requires an explicit --output; saved evidence is not overwritten implicitly')
 if a.reduce:out.mkdir(parents=True,exist_ok=True)
 if a.reduce:
  b=a.reduce.read_bytes();print(json.dumps(reduce(json.loads(b),out)))
  (out/'reduction.json').write_text(json.dumps({'original_results_sha256':hashlib.sha256(b).hexdigest(),'original_results_bytes':len(b),'original_cases':36,'retained':'all 36 case summaries and the six predefined repetition1/concurrency16 event traces','normalization':'workers_joined relabeled workers_retired; original field counted destroy callbacks before worker_end, not std::thread::join','raw_disposition':'discarded after checks; native source/harness regenerates the controlled sequence, not exact timing'},indent=2)+'\n')
  (out/'SHA256SUMS.json').write_text(json.dumps({p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.iterdir()) if p.is_file() and p.name!='SHA256SUMS.json'},indent=2)+'\n')
 else:
  with (out/'cases.csv').open() as f:rows=list(csv.DictReader(f))
  require(validate(rows)==json.loads((out/'summary.json').read_text()),'summary mismatch')
  for n,h in json.loads((out/'SHA256SUMS.json').read_text()).items():require(hashlib.sha256((out/n).read_bytes()).hexdigest()==h,'checksum '+n)
  mutations=[lambda xs:xs.pop(),lambda xs:xs[0].update(pending_refusals='0'),lambda xs:xs[0].update(queued_before='0'),lambda xs:xs[0].update(workers_retired='0'),lambda xs:xs[0].update(explicit_triggers='0')]
  for mutate in mutations:
   xs=copy.deepcopy(rows);mutate(xs)
   try:validate(xs)
   except ValueError:pass
   else:raise ValueError('negative mutation accepted')
  print('PASS: compact matrix, checksums and five invalid-evidence controls')
