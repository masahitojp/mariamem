"""Summarize nested observations without requiring the removed build tree."""
from pathlib import Path
import argparse,collections,gzip,hashlib,json,statistics
P=Path(__file__).resolve().parent
ap=argparse.ArgumentParser();ap.add_argument('--check',action='store_true');a=ap.parse_args()
source=P/'observations.json.gz'
records=json.loads(gzip.decompress(source.read_bytes())) if source.exists() else json.loads((P/'observations.json').read_text())
def stats(values):
 values=sorted(values);assert values
 return dict(n=len(values),p50=statistics.median(values),p95=values[max(0,__import__('math').ceil(len(values)*.95)-1)],mean=statistics.mean(values),maximum=max(values),over100ms=sum(v>100 for v in values))
report={}
for par in [4,8]:
 modes={}
 for mode in ['off','on']:
  group=[r for r in records if r['repeat']>=0 and r['parallel']==par and r['mode']==mode]
  assert len(group)==3 and all(r['accepted'] for r in group)
  forks=[s['end_ms']-s['start_ms'] for r in group for s in r['trace']['spans'] if s['kind']=='fork']
  cell=dict(suite_ms=stats([r['trace']['elapsed_ms'] for r in group]),fork_ms=stats(forks))
  if mode=='on':
   bins=collections.defaultdict(list);counts=collections.defaultdict(list)
   for r in group:
    for lane,data in r['stages'].items():
     if lane=='root':continue
     trace=data['startup'];ev={e['name']:e['offset_ns']/1e6 for e in trace['events']}
     assert len(ev)==len(trace['events'])
     # Event schema is validated by the inherited primary analysis first.
     for name in ['timer','charset']:
      start,end=[ev['common_'+name+'_'+suffix] for suffix in ['begin','end']]
      assert start<=end;bins[name].append(end-start)
     available=trace['common_timer'][12]!=0
     counts['millisecond_probe_skipped'].append(int(not available))
     if available:
      assert ev['common_timer_begin']<=ev['common_timer_ms_begin']<=ev['common_timer_ms_end']<=ev['common_timer_end']
      ms=ev['common_timer_ms_end']-ev['common_timer_ms_begin']
      bins['timer_ms_executed'].append(ms)
     else:
      assert trace['common_timer'][12:16]==[0,0,0,0]
      assert 'common_timer_ms_begin' not in ev and 'common_timer_ms_end' not in ev
      ms=0
     bins['timer_ms'].append(ms)
     bins['timer_other'].append(bins['timer'][-1]-bins['timer_ms'][-1])
     bins['after_charset'].append(ev['common_end']-ev['common_charset_end'])
     assert {'uca_deep','selected_charset','collation_hash_grow'}<=set(trace['common_details'])
     for key,(count,ns) in trace['common_details'].items():
      assert count>=1 and ns>=0
      bins[key].append(ns/1e6);counts[key].append(count)
     assert len(trace['common_counts'])==5
     for key,value in zip(['charset_insert_attempts','collation_insert_attempts','charset_growths','collation_growths','registered_descriptors'],trace['common_counts']):counts[key].append(value)
   cell['regions_ms']={k:stats(v) for k,v in bins.items()}
   cell['counts']={k:dict(n=len(v),minimum=min(v),maximum=max(v),total=sum(v),values=sorted(set(v))) for k,v in counts.items()}
  modes[mode]=cell
 report[str(par)]=modes
text=json.dumps(dict(result='OBSERVATION_COMPLETE',parallel=report,processes=len(records),new_optimization=False),indent=2)+'\n'
target=P/'detail-summary.json'
if a.check:assert target.read_text()==text
else:target.write_text(text)
print('Detail summary '+('matches' if a.check else 'saved'))
