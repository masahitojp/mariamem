"""Read-only verification of compact results; collection never changes input receipts."""
import argparse, hashlib, json, statistics
from pathlib import Path

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(d):return json.dumps(d,indent=2,sort_keys=True)+'\n'
def summarize(d):
 assert d['pilot']['result']=='PASS' and d['completion']['result']=='PASS'
 trials=d['trials'];assert len(trials)==10
 assert {(t['mode'],t['repetition']) for t in trials}=={(m,r) for m in ['baseline','fresh'] for r in range(5)}
 for t in trials:
  assert t['success'] and t['cleanup'] and len(t['children'])==4
  assert t['returncode']==0
  assert all(t['final'][k]==0 for k in ['active_mappings','active_rw_bytes','active_reserved_bytes'])
 assert d['pilot']['constructor_selftests']==2
 for mode,p in d['traces'].items():
  assert p['success'] and p['cleanup'] and len(p['stages'])==12
  assert {s['name'] for s in p['stages']}=={f'child{i}_{stage}' for i in range(1,5) for stage in ['reserve','construct','ready']}
  assert all(s['resident_bytes']==0 for s in p['stages'] if s['name'].endswith('_reserve'))
 modes={}
 for mode in ['baseline','fresh']:
  ts=[t for t in trials if t['mode']==mode]
  modes[mode]={}
  for metric in ['wall_ms','cpu_ms']:
   means=[statistics.mean(c[metric] for c in t['children']) for t in ts]
   modes[mode][metric]={'process_means':means,'median_process_mean':statistics.median(means),'child_median':statistics.median(c[metric] for t in ts for c in t['children'])}
  modes[mode]['rss_mib']={stage:statistics.median(t['rss'][stage]/2**20 for t in ts) for stage in ts[0]['rss']}
  modes[mode]['rss_four_child_delta_mib']=statistics.median((t['rss']['child-4']-t['rss']['baseline'])/2**20 for t in ts)
  stages=d['traces'][mode]['stages']
  modes[mode]['diagnostic']={stage:{'resident_mib':statistics.median(s['resident_bytes']/2**20 for s in stages if s['name'].endswith('_'+stage)), 'wall_ms':None if stage=='ready' else statistics.median(s['wall_ms'] for s in stages if s['name'].endswith('_'+stage)), 'cpu_ms':None if stage=='ready' else statistics.median(s['cpu_ms'] for s in stages if s['name'].endswith('_'+stage))} for stage in ['reserve','construct','ready']}
 pairs=[]
 for r in range(5):
  a=next(t for t in trials if t['repetition']==r and t['mode']=='baseline');b=next(t for t in trials if t['repetition']==r and t['mode']=='fresh')
  pair={'repetition':r}
  for key in ['wall_ms','cpu_ms']:
   av=statistics.mean(c[key] for c in a['children']);bv=statistics.mean(c[key] for c in b['children'])
   pair[key+'_delta']=bv-av;pair[key+'_percent']=(bv/av-1)*100
  pair['rss_delta_mib']=((b['rss']['child-4']-b['rss']['baseline'])-(a['rss']['child-4']-a['rss']['baseline']))/2**20
  pairs.append(pair)
 return dict(modes=modes,pairs=pairs,median_paired_wall_percent=statistics.median(p['wall_ms_percent'] for p in pairs),median_paired_cpu_percent=statistics.median(p['cpu_ms_percent'] for p in pairs))

def collect(e):
 read=lambda name:json.loads((e/name).read_text())
 records=read('measure-records.json')
 trials=[dict(r,**{k:v for k,v in read(r['report']).items() if k in ['success','cleanup','children','final']}) for r in records]
 traces={}
 for mode in ['baseline','fresh']:
  r=read('pilot/0-'+mode+'.json')
  traces[mode]={k:r[k] for k in ['success','cleanup','stages']}
  traces[mode]['rss']=next(p['rss'] for p in read('pilot-records.json') if p['mode']==mode and not p['negative'])
 return dict(pilot=read('pilot.json'),completion=read('completion.json'),trials=trials,traces=traces)

def main():
 p=argparse.ArgumentParser();p.add_argument('--collect',type=Path);p.add_argument('--check',action='store_true');p.add_argument('--results',type=Path,default=Path(__file__).parent/'results');a=p.parse_args()
 if a.collect:
  assert not a.check
  d=collect(a.collect);s=summarize(d);a.results.mkdir(parents=True,exist_ok=True)
  (a.results/'observations.json').write_text(dump(d));(a.results/'summary.json').write_text(dump(s));(a.results/'inputs.json').write_bytes((a.collect/'inputs.json').read_bytes())
 else:
  assert a.check
  checks=json.loads((a.results/'SHA256SUMS.json').read_text())
  for name,h in checks.items():assert sha(a.results/name)==h,name
  d=json.loads((a.results/'observations.json').read_text());assert dump(summarize(d))==(a.results/'summary.json').read_text()
  print('CHECK PASS: checksums, complete paired set, stage completeness, SQL/cleanup and summary')
if __name__=='__main__':main()
