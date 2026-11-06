import json,statistics,math,hashlib,gzip
from pathlib import Path
import sys
import argparse
parser=argparse.ArgumentParser();parser.add_argument("root",type=Path);parser.add_argument("--check",action="store_true");args=parser.parse_args();root=args.root
records=json.loads((root/'records.json').read_text())
obs=json.loads(gzip.decompress((root/'observations.json.gz').read_bytes()))

assert len(records)==52 and len({r['name'] for r in records})==52
expected={'pilot':2,'negative':2,'warmup':4,'primary':20,'memory':20,'diagnostic':4}
assert {k:sum(r['kind']==k for r in records) for k in expected}==expected
for rec in records:
 r=obs[rec['report']];assert r['cleanup'] and r['image_after_close']['owned_fds']==0 and r['image_after_close']['closed']
 assert all(r['cleanup_stats'][k]==0 for k in ['active_mappings','active_reserved_bytes','active_rw_bytes','release_failures'])
 candidate=rec['arm']=='pages';assert r['image_before_close']['page_only']==candidate and r['image_before_close']['enabled']==candidate
 assert r['image_before_close']['builds']==int(candidate)
 assert r['resolved_max_forks']==rec['parallel']
 if candidate:
  ranges=r['image_before_close']['image_ranges'];page=r['image_before_close']['page_size'];end=0;total=0
  for q in ranges:
   assert q['offset']>=end and q['offset']%page==q['length']%page==0 and q['length']>0
   end=q['offset']+q['length'];assert end<=256*2**20;total+=q['length']
  assert 0<total==r['image_before_close']['initialized_page_bytes']<256*2**20
  assert any(q['offset']<=26981552<q['offset']+q['length'] for q in ranges),'missing init-flag page'
 if rec['kind']=='negative':assert rec['exit_code']==1 and not r['success'] and 'pristine oracle' in r['error']
 else:
  assert rec['exit_code']==0 and r['success']
  if rec['kind']!='memory':
   assert len(r['samples'])==rec['count'] and sorted(s['index'] for s in r['samples'])==list(range(rec['count']))
   assert all(s['oracle'] and s['cleanup'] and not s.get('error') for s in r['samples'])
def median(a):return statistics.median(a)
def percentile(a,q):
 a=sorted(a);idx=(len(a)-1)*q;lo=int(idx);hi=math.ceil(idx);return a[lo]+(a[hi]-a[lo])*(idx-lo)
def spans(s):return {v['name']:v for v in s['spans']}
def metrics(rec):
 r=obs[rec['report']]
 if rec['kind']=='memory':
  m={x['stage']:x for x in r['memory']};d={}
  for stage in ['baseline','held_ready','held_after_sql','after_children_close']:
   d[stage+'_rss_mib']=m[stage]['rss_bytes']/2**20
   d[stage+'_rss_delta_mib']=(m[stage]['rss_bytes']-m['before_root']['rss_bytes'])/2**20
   d[stage+'_fds']=m[stage]['fds']
  for stage in ['held_ready','held_after_sql']:d[stage+'_child_increment_mib']=(m[stage]['rss_bytes']-m['baseline']['rss_bytes'])/2**20/rec['parallel']
  return d
 assert r['success'] and len(r['samples'])==rec['count']
 fork=[];ready=[];cleanup=[];cp=[]
 for s in r['samples']:
  v=spans(s);assert len(v)==len(s['spans'])
  assert all(s['begin_ms']<=z['begin_ms']<=z['end_ms']<=s['end_ms'] for z in v.values())
  fork.append(v['start_or_fork']['end_ms']-v['start_or_fork']['begin_ms'])
  ready.append(v['select1']['end_ms']-v['start_or_fork']['begin_ms'])
  cleanup.append(v['close']['end_ms']-v['retire']['begin_ms'])
  if 'fork_cpu_ms' in s:cp.append(s['fork_cpu_ms'])
 rootspan={x['name']:x for x in r['root_spans']}
 d={'fork_p50_ms':median(fork),'fork_p95_ms':percentile(fork,.95),'first_select_p50_ms':median(ready),'cleanup_p50_ms':median(cleanup),'suite_ms':r['suite_ms'],'batch_ms':r['batch_ms'],'suite_cpu_ms':r['suite_cpu_ms'],'batch_cpu_ms':r['batch_cpu_ms'],'process_cpu_ms':rec['process_cpu_ms'],'root_start_ms':rootspan['root_start']['end_ms']-rootspan['root_start']['begin_ms'],'image_build_ms':r['image_before_close']['build_ms']}
 if cp:d['fork_cpu_p50_ms']=median(cp)
 return d
summary={'cells':{},'criteria':json.loads((root/'plan.json').read_text())['criteria'],'source_commit':json.loads((root/'inputs.json').read_text())['source_commit']}
for kind in ['primary','memory']:
 for p in [1,4]:
  rows=[r for r in records if r['kind']==kind and r['parallel']==p];assert len(rows)==10
  cells={a:sorted([r for r in rows if r['arm']==a],key=lambda r:r['rep']) for a in ['anonymous','pages']}
  assert all([r['rep'] for r in v]==list(range(5)) for v in cells.values())
  data={a:[metrics(r) for r in v] for a,v in cells.items()}
  metrics_out={}
  for name in data['anonymous'][0]:
   aa=[x[name] for x in data['anonymous']];bb=[x[name] for x in data['pages']]
   changes=[100*(b/a-1) if a else None for a,b in zip(aa,bb)]
   metrics_out[name]={'anonymous':median(aa),'pages':median(bb),'anonymous_all':aa,'pages_all':bb,'paired_pct':changes,'paired_median_pct':median(changes) if all(x is not None for x in changes) else None,'pairs_improve':sum(b<a for a,b in zip(aa,bb))}
  summary['cells'][f'{kind}-p{p}']=metrics_out
summary['tails']=[]
for r in records:
 if r['kind'] not in ['primary','warmup','diagnostic']:continue
 for s in obs[r['report']]['samples']:
  for v in s['spans']:
   elapsed=v['end_ms']-v['begin_ms']
   if elapsed>100:summary['tails'].append({'run':r['name'],'kind':r['kind'],'child':s['index'],'stage':v['name'],'ms':elapsed})
gates={}
for p in [1,4]:
 m=summary['cells'][f'primary-p{p}'];f=m['fork_p50_ms']
 gates[f'p{p}_fork']=f['paired_median_pct']<=-3 and f['pairs_improve']>=4
 for k in ['suite_ms','suite_cpu_ms','first_select_p50_ms']:
  v=m[k];gates[f'p{p}_{k}_guard']=v['paired_median_pct']<=5 and sum(x>5 for x in v['paired_pct'])<4
 mem=summary['cells'][f'memory-p{p}']
 for k in ['held_ready_rss_mib','held_after_sql_rss_mib']:gates[f'p{p}_{k}_guard']=mem[k]['paired_median_pct']<=10
summary['gates']=gates;summary['next_stage_screen_pass']=all(gates.values())
if args.check:
 assert summary==json.loads((root/'summary.json').read_text()),'summary differs'
 print('PASS: read-only summary replay')
else:print(json.dumps(summary,indent=2))
