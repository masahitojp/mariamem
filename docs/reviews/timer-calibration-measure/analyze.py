"""Read-only replay of retained paired observations; --check never writes."""
from pathlib import Path
import argparse,json,math,statistics
P=Path(__file__).resolve().parent

def stats(values):
 s=sorted(values);assert s and all(math.isfinite(v) and v>=0 for v in s)
 return {'n':len(s),'p50':statistics.median(s),'p95':s[math.ceil(.95*len(s))-1],'min':s[0],'max':s[-1]}

def analyze():
 rows=json.loads((P/'observations.json').read_text());assert len(rows)==38
 assert all(r['accepted'] and r['exit_code']==0 and r['scratch_empty'] for r in rows)
 for r in rows:
  if r['kind']=='shop':
   m=r['data']['meta'];assert m['read_cases']=='50' and m['write_cases']=='20' and m['test_exit']=='0' and m['active_mappings_after']=='0'
   assert m['parallel']==str(r['parallel']) and m['fork_cap']==str(r['parallel']+1)
   for kind,n in [('fork',21),('sample',21),('read',50),('write',20)]:assert sum(s['kind']==kind for s in r['data']['spans'])==n
  else:assert r['data']['result']=='PASS' and r['data']['active_mappings_after']==0
 out={'result':'COMPLETE','warmup_processes':6,'measured_processes':32,'lifecycle':{},'shop':{},'paired':{}}
 for arm in ('baseline','candidate'):
  life=[r for r in rows if r['arm']==arm and r['kind']=='lifecycle' and r['repeat']>=0];assert len(life)==6
  out['lifecycle'][arm]={}
  for kind,n in [('fresh',8),('fork',16)]:
   entry={}
   for metric in ('wall_ms','cpu_ms'):
    batches=[[o[metric] for o in r['data']['observations'] if o['kind']==kind] for r in life]
    assert all(len(b)==n for b in batches)
    entry[metric]={'batch_p50':stats([statistics.median(b) for b in batches]),'children':stats(sum(batches,[]))}
   out['lifecycle'][arm][kind]=entry
  out['shop'][arm]={}
  for par in (4,8):
   rr=[r for r in rows if r['arm']==arm and r['kind']=='shop' and r['parallel']==par and r['repeat']>=0];assert len(rr)==5
   e={'suite_wall_ms':stats([r['data']['elapsed_ms'] for r in rr]),'suite_cpu_ms':stats([float(r['data']['meta']['cpu_ms']) for r in rr])}
   for kind in ('fork','sample','cleanup','boot'):
    durations=[v['end_ms']-v['start_ms'] for r in rr for v in r['data']['spans'] if v['kind']==kind]
    e[kind+'_ms']=stats(durations);e[kind+'_gt100ms']=sum(v>100 for v in durations)
   out['shop'][arm][str(par)]=e
 # Pair by repeat, never sort arms independently to attribute an improvement.
 for kind in ('fresh','fork'):
  for metric in ('wall_ms','cpu_ms'):
   pairs=[]
   for repeat in range(6):
    values=[]
    for arm in ('baseline','candidate'):
     r=next(r for r in rows if r['arm']==arm and r['kind']=='lifecycle' and r['repeat']==repeat)
     values.append(statistics.median([v[metric] for v in r['data']['observations'] if v['kind']==kind]))
    b,c=values;pairs.append({'repeat':repeat,'baseline':b,'candidate':c,'delta':c-b,'pct':(c/b-1)*100})
   out['paired'][kind+'_'+metric]=pairs
 for par in (4,8):
  pairs=[]
  for repeat in range(5):
   values=[]
   for arm in ('baseline','candidate'):
    r=next(r for r in rows if r['arm']==arm and r['kind']=='shop' and r['repeat']==repeat and r['parallel']==par)
    values.append(r['data']['elapsed_ms'])
   b,c=values;pairs.append({'repeat':repeat,'baseline':b,'candidate':c,'delta':c-b,'pct':(c/b-1)*100})
  out['paired']['shop_p'+str(par)]=pairs
 return out

if __name__=='__main__':
 ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--check',action='store_true');a=ap.parse_args();r=analyze()
 if a.check:
  assert json.loads((P/'summary.json').read_text())==r;print('retained-data summary PASS')
 else:
  (P/'summary.json').write_text(json.dumps(r,indent=2)+'\n')
  for arm in ('baseline','candidate'):
   print(arm,'Fresh/Fork wall/CPU:',[(k,*[round(r['lifecycle'][arm][k][m]['batch_p50']['p50'],3) for m in ('wall_ms','cpu_ms')]) for k in ('fresh','fork')])
   print(arm,'shop:',[(p,round(v['suite_wall_ms']['p50'],3),round(v['suite_cpu_ms']['p50'],3)) for p,v in r['shop'][arm].items()])
  for key,pairs in r['paired'].items():print(key,'paired deltas:',[round(p['delta'],3) for p in pairs])
