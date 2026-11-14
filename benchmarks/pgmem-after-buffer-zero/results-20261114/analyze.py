from pathlib import Path
import json,statistics as st,csv,collections
E=Path(__file__).resolve().parent;R=E/'runs'
records=json.loads((E/'records.json').read_text());assert len(records)==50
assert len({r['name'] for r in records})==50
matrix=json.loads((E/'matrix.json').read_text());assert len(matrix)==48
for b in ('mariamem','pgmem'):
 assert len({r['binary_sha256'] for r in records if r['name'].startswith(b+'-suite-')})==1
 assert len({r['binary_sha256'] for r in records if r['name'].startswith(b+'-lifecycle-') or r['name']==b+'-negative'})==1
summary={'conditions':json.loads((E/'plan.json').read_text()),'cells':{}};rows=[];children=[];spanrows=[]
for p in (1,4,8):
 counts={}
 for backend in ('mariamem','pgmem'):
  cell={'suite':{},'lifecycle':{}};suites=[];lives=[];groups=collections.defaultdict(list);group_sums=collections.defaultdict(list);lanes=collections.defaultdict(list);scenarios=collections.defaultdict(list)
  for rep in (0,1,2):
   s=json.loads((R/f'{backend}-suite-p{p}-r{rep}.json').read_text());suites.append(s['elapsed_ms'])
   signature=collections.Counter((q['name'],q['kind'],q['lane']) for q in s['spans']);assert counts.setdefault(rep,signature)==signature,(p,backend,rep)
   sums=collections.defaultdict(float)
   for q in s['spans']:
    duration=q['end_ms']-q['start_ms'];assert duration>=0
    groups[q['name']].append(duration);sums[q['name']]+=duration;lanes[q['lane']].append(duration)
    if q['name']=='test':scenarios[q['lane'].split('/')[0]].append(duration)
    spanrows.append({'backend':backend,'parallel':p,'repetition':rep,**q,'duration_ms':duration})
   for k,v in sums.items():group_sums[k].append(v)
   d=json.loads((R/f'{backend}-lifecycle-p{p}-r{rep}.json').read_text());assert d['success'] and d['cleanup_complete'] and d['root_closed_before_forks'] and len(d['samples'])==48;lives.append(d)
   for child in d['samples']:
    assert child['oracle'] and child['cleanup_complete']
    children.append({'backend':backend,'parallel':p,'repetition':rep,**child})
  cell['suite']={'median_elapsed_ms':st.median(suites),'process_elapsed_ms':suites,'span_p50_ms':{k:st.median(v) for k,v in groups.items()},'span_sum_process_median_ms':{k:st.median(v) for k,v in group_sums.items()},'samples_per_run':dict(collections.Counter(q['name'] for q in s['spans'])),'lane_p50_ms':{k:st.median(v) for k,v in lanes.items()},'scenario_p50_ms':{k:st.median(v) for k,v in scenarios.items()}}
  childset=[s for d in lives for s in d['samples']]
  fields=('fork_ms','connect_ms','select_ms','ready_ms','sql_ms','cleanup_ms','database_close_ms','disconnect_ms','total_ms')
  cell['lifecycle']={'children':len(childset),'child_p50_ms':{k:st.median(s[k] for s in childset) for k in fields},'child_p95_ms':{k:sorted(s[k] for s in childset)[int(.95*(len(childset)-1))] for k in fields},'batch_median_ms':st.median(d['batch_ms'] for d in lives),'process_batch_ms':[d['batch_ms'] for d in lives],'root_start_median_ms':st.median(d['root_start_ms'] for d in lives),'snapshot_median_ms':st.median(d['snapshot_ms'] for d in lives)}
  summary['cells'][f'{backend}-p{p}']=cell
  rows.append({'backend':backend,'parallel':p,'suite_ms':cell['suite']['median_elapsed_ms'],'fork_ms':cell['lifecycle']['child_p50_ms']['fork_ms'],'ready_ms':cell['lifecycle']['child_p50_ms']['ready_ms'],'cleanup_ms':cell['lifecycle']['child_p50_ms']['cleanup_ms'],'batch_ms':cell['lifecycle']['batch_median_ms']})
(E/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
for name,data in [('summary.csv',rows),('children.csv',children),('spans.csv',spanrows)]:
 with (E/name).open('w',newline='') as f:
  keys=list(dict.fromkeys(k for r in data for k in r));w=csv.DictWriter(f,fieldnames=keys,lineterminator="\n");w.writeheader();w.writerows(data)
print('PASS complete fixed matrix, identical scenario/span counts,864 child oracles and cleanup')
for row in rows:print(row)
