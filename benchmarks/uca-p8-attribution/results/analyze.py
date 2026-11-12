"""Read-only recomputation from compact UCA P8 observations."""
from pathlib import Path
import csv,json,statistics as st,math,argparse
P=Path(__file__).resolve().parent

def stats(v):
 s=sorted(v);return {'n':len(s),'p50':st.median(s),'p95':s[math.ceil(.95*len(s))-1],'max':max(s)}
def analyze():
 batches=list(csv.DictReader((P/'batches.csv').open()));children=list(csv.DictReader((P/'children.csv').open()));phases=list(csv.DictReader((P/'phases.csv').open()));captures=json.loads((P/'captures.json').read_text())
 assert len(batches)==32 and all(b['accepted']=='True' and b['exit_code']=='0' and b['scratch_empty']=='True' and b['active_mappings_after']=='0' for b in batches)
 out={'result':'COMPLETE','observer_off':{},'diagnostic':{},'paired':[]}
 for arm in ['baseline','candidate']:
  bb=[b for b in batches if b['arm']==arm and b['mode']=='off' and int(b['repeat'])>=0];assert len(bb)==10
  cc=[c for c in children if c['name'] in {b['name'] for b in bb}];assert len(cc)==210
  out['observer_off'][arm]={k:stats([float(b[k]) for b in bb]) for k in ['suite_ms','cpu_ms','rss_bytes']}
  for k in ['fork_ms','sample_ms','cleanup_ms']:
   v=[float(c[k]) for c in cc if c[k]];out['observer_off'][arm][k]=stats(v);out['observer_off'][arm][k+'_gt100']=sum(x>100 for x in v)
  out['observer_off'][arm]['batches_with_sample_gt100']=sum(any(float(c['sample_ms'])>100 for c in cc if c['name']==b['name']) for b in bb)
  bb=[b for b in batches if b['arm']==arm and b['mode']=='diagnostic'];assert len(bb)==4
  pp=[p for p in phases if p['name'] in {b['name'] for b in bb}]
  out['diagnostic'][arm]={k:{'count':sum(int(p['count']) for p in pp if p['phase']==k),'gt100':sum(int(p['gt100']) for p in pp if p['phase']==k),'max_ms':max(float(p['max_ms']) for p in pp if p['phase']==k)} for k in sorted({p['phase'] for p in pp})}
 for repeat in range(10):
  bb={b['arm']:b for b in batches if b['mode']=='off' and int(b['repeat'])==repeat};a=float(bb['baseline']['suite_ms']);b=float(bb['candidate']['suite_ms']);out['paired'].append({'repeat':repeat,'baseline':a,'candidate':b,'delta_ms':b-a,'pct':(b/a-1)*100})
 out['paired_median_pct']=st.median(p['pct'] for p in out['paired']);out['candidate_faster_pairs']=sum(p['delta_ms']<0 for p in out['paired'])
 out['captures']=[{k:c[k] for k in ['name','mode','arm','phase','operation_ordinal','usable','matching_db_blocks']} for c in captures]
 return out
if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--check',action='store_true');a=ap.parse_args();r=analyze()
 if a.check:assert r==json.loads((P/'summary.json').read_text());print('compact replay PASS')
 else:(P/'summary.json').write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r,indent=2))
