"""Aggregate instrumented fill observations; overlapping writes are not redundancy proof."""
import argparse,collections,hashlib,json,statistics
from pathlib import Path

def union_bytes(intervals):
 end=total=0
 for a,b in sorted(intervals):
  assert 0<=a<b<=2**31
  total+=max(0,b-max(a,end));end=max(end,b)
 return total

def summarize(records,results):
 assert len(records)==6
 rows=[]
 for i in range(3):
  pair=records[2*i:2*i+2];assert [r['observed'] for r in pair]==([False,True] if i%2==0 else [True,False])
  for r in pair:
   assert r['repetition']==i and not r['negative'] and r['returncode']==0
   d=results[r['report']];assert d['success'] and d['cleanup'] and not d['overflow'];assert d['final']['active_mappings']==0 and d['final']['active_rw_bytes']==0
   assert d['final']['grow_failures']==d['final']['release_failures']==0 and d['final']['creates']==3
   assert len(d['phases'])==6
   assert d['observed']==r['observed']
   for child,phase in enumerate([1,4]):
    p=next(x for x in d['phases'] if x['id']==phase);assert p['name']=='fork'
    row=dict(repetition=i,child=child,observed=d['observed'],wall_ms=p['wall_ms'],cpu_ms=p['cpu_ms'],minor_faults=p['minor_faults'],major_faults=p['major_faults'])
    if d['observed']:
     t=d['totals'][str(phase)];events=[x for x in d['large_zero_events'] if x['phase']==phase];assert events
     total=sum(x['bytes'] for x in events);assert total<=t['zero_bytes']<=t['bytes']
     union=union_bytes([(x['dst'],x['dst']+x['bytes']) for x in events]);callers={}
     for x in events:
      assert x['bytes']>=65536
      frames=[f for f in x['stack'] if '/code/p' in f['function']]
      key=' <- '.join(f['function'].split('/code/')[-1]+':'+str(f['line']) for f in frames[:3])
      c=callers.setdefault(key,dict(calls=0,bytes=0,ns=0,sizes=[]));c['calls']+=1;c['bytes']+=x['bytes'];c['ns']+=x['ns'];c['sizes'].append(x['bytes'])
     row.update(totals=t,large_zero_bytes=total,unique_large_range_bytes=union,repeated_large_range_bytes=total-union,small_zero_bytes=t['zero_bytes']-total,large_callers=sorted([dict(caller=k,**v) for k,v in callers.items()],key=lambda x:x['bytes'],reverse=True))
    else:assert not d['totals'] and not d['large_zero_events']
    rows.append(row)
 summaries={}
 for observed in [False,True]:
  items=[r for r in rows if r['observed']==observed];keys=['wall_ms','cpu_ms','minor_faults','major_faults']+(['large_zero_bytes','unique_large_range_bytes','repeated_large_range_bytes','small_zero_bytes'] if observed else [])
  summaries['observed' if observed else 'control']={k:dict(median=statistics.median(r[k] for r in items),min=min(r[k] for r in items),max=max(r[k] for r in items)) for k in keys}
  if observed:
   for k in ['zero_calls','zero_bytes','zero_ns','bytes','calls']:
    summaries['observed'][k]=dict(median=statistics.median(r['totals'][k] for r in items),min=min(r['totals'][k] for r in items),max=max(r['totals'][k] for r in items))
 return dict(scope='3 process pairs, 6 children per mode; descriptive child medians, not 6 independent process replications',warning='Observed nanoseconds include clock overhead and scheduling; not CPU or avoidable cost. Range overlap does not prove redundant writes. Faults are whole-Fork process counters, not assigned to fill.',summary=summaries,rows=rows)
def same_range(results):
 out=[]
 for name,d in results.items():
  if not d['observed']:continue
  for phase in [1,4]:
   events=[x for x in d['large_zero_events'] if x['phase']==phase and x['bytes'] in [16777216,18567168] and any('Fn18568' in f['function'] for f in x['stack'])]
   assert len(events)==2 and events[0]['bytes']==16777216 and events[0]['dst']==events[1]['dst']
   out.append(dict(report=Path(name).name,phase=phase,dst=events[0]['dst'],first_ns=events[0]['ns'],second_ns=events[1]['ns']))
 return out
def render(d):return json.dumps(d,indent=2)+'\n'
def main():
 p=argparse.ArgumentParser();p.add_argument('--results',type=Path,required=True);p.add_argument('--collect',type=Path);p.add_argument('--check',action='store_true');a=p.parse_args()
 if a.check:
  assert a.collect is None
  for name,h in json.loads((a.results/'SHA256SUMS.json').read_text()).items():assert hashlib.sha256((a.results/name).read_bytes()).hexdigest()==h
  obs=json.loads((a.results/'observations.json').read_text());assert same_range(obs['results'])==json.loads((a.results/'same-range.json').read_text());assert (a.results/'summary.json').read_text()==render(summarize(obs['records'],obs['results']));print('PASS: hashes and summary recomputation; read-only');return
 assert a.collect
 records=json.loads((a.collect/'measure-records.json').read_text());results={r['report']:json.loads((a.collect/r['report']).read_text()) for r in records}
 for d in results.values():
  d['large_zero_events']=[dict(x,stack=[dict(function=f['function'],line=f['line']) for f in x['stack'] if '/code/p' in f['function']][:3]) for x in (d['large_zero_events'] or []) if x['phase'] in [1,4]]
 out=summarize(records,results)
 a.results.mkdir(parents=True,exist_ok=True);(a.results/'observations.json').write_text(json.dumps(dict(records=records,results=results),separators=(',',':'))+'\n');(a.results/'summary.json').write_text(render(out));(a.results/'same-range.json').write_text(render(same_range(results)));print(render(out['summary']))
if __name__=='__main__':main()
