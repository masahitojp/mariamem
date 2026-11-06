from pathlib import Path
import json,statistics,collections,sys,tarfile
E=Path(__file__).resolve().parent

def read(n):
 p=E/n
 if p.exists():return json.loads(p.read_text())
 with tarfile.open(E/'raw-evidence.tar.gz') as a:return json.load(a.extractfile(n))
def stats(xs):
 vals=sorted(xs);n=len(vals)
 def q(f):
  pos=(n-1)*f;lo=int(pos);hi=min(lo+1,n-1);return vals[lo]+(vals[hi]-vals[lo])*(pos-lo)
 return {'n':n,'p50_ms':q(.5),'p95_ms':q(.95),'max_ms':max(vals),'gt100':sum(x>100 for x in vals),'gt300':sum(x>300 for x in vals)}
records=read('records.json');plan=read('plan.json');primary=[r for r in records if r['repetition']>=0];assert len(records)==16 and len(primary)==10
expected=[(arm,i) for i,pair in enumerate(plan['protocol']['pairs']) for arm in pair];assert [(r['arm'],r['repetition']) for r in primary]==expected
process=[];auxiliary=[];auxslow=[];slow=[];ownerwaits=[];captures=[];aggregate={arm:[] for arm in plan['arms']}
for r in records:
 d=read(r['report']);assert d['cleanup_complete'] and d['root_closed_before_forks'];assert d['parallel']==r['parallel']
 if not r['negative']:assert d['success'] and len(d['samples'])==r['count'] and all(x['oracle'] and x['cleanup_complete'] for x in d['samples'])
 else:assert not d['success'] and 'pristine oracle' in d['error']
 if r not in primary and not r['negative']:
  auxiliary.append({'arm':r['arm'],'warmup':r['warmup'],'preflight':r['preflight'],'update':stats([x['update_ms'] for x in d['samples']])})
  for x in d['samples']:
   if x['update_ms']>100:auxslow.append({'arm':r['arm'],'warmup':r['warmup'],'preflight':r['preflight'],'sample':x})
 if r in primary:
  vals=[x['update_ms'] for x in d['samples']];aggregate[r['arm']]+=vals;process.append({'arm':r['arm'],'pair':r['repetition'],'batch_ms':d['batch_ms'],'update':stats(vals)})
  for x in d['samples']:
   if x['update_ms']>100:slow.append({'arm':r['arm'],'pair':r['repetition'],'sample':x})
 for n in r['capture_files']:
  if n.endswith('.json'):
   m=read(n);assert not m['artificial'];m=dict(m,primary=r in primary,arm=r['arm'],pair=r['repetition'],file=n);captures.append(m)
 for n in r['trace_reports']:
  tr=read(n);assert not tr['truncated'];events=tr['events'] or []
  for x in events:
   if x.get('owner'):assert x['owner']['page_matches'],(n,x)
   if x['kind']!='wait_registered' or not x.get('owner'):continue
   rel=[v for v in events if v.get('wait')==x['wait']];end=[v for v in rel if v['kind']=='wait_return'];assert len(end)==1
   late=[v for v in rel if v['kind']=='owner_still_waiting'];signals=[v for v in rel if v['kind']=='signal_before']
   ownerwaits.append({'primary':r in primary,'pair':r['repetition'],'child':tr['child'],'wait':x['wait'],'registered_to_return_ms':(end[0]['ns']-x['ns'])/1e6,'owner_at_registration':x['owner'],'threshold_owner':late[0]['owner'] if late else None,'threshold_before_signal':bool(late and signals and late[0]['owner']['end_ns']<=signals[0]['ns'])})
arms={a:stats(xs) for a,xs in aggregate.items()};s={a:arms[a]['gt100'] for a in arms}
result='NEITHER_REPRODUCED' if not any(s.values()) else 'BOTH_REPRODUCED' if all(s.values()) else 'ORIGINAL_ONLY' if s['original'] else 'OWNER_ONLY'
summary={'result':('AUXILIARY_LONG_UPDATE_ONLY' if result=='NEITHER_REPRODUCED' and auxslow else result),'primary_result':result,'primary_processes':10,'primary_children':480,'arms':arms,'processes':process,'auxiliary_processes':auxiliary,'auxiliary_slow_updates':auxslow,'slow_updates':slow,'owner_page_waits':ownerwaits,'captures':captures,'controls':{'preflight':2,'wrong_seed':2,'warmups':2},'limits':plan['limits'],'stop':'Fixed protocol completed; no extra repetition or automatic follow-up'}
if '--check' in sys.argv:assert summary==read('summary.json');print('READ-ONLY REPLAY PASS')
else:(E/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps({k:summary[k] for k in ['result','primary_result','arms','processes','auxiliary_processes','slow_updates','stop']},indent=2))
