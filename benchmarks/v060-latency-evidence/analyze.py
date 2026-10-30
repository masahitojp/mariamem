import csv,hashlib,json,re,statistics
from pathlib import Path
E=Path(__file__).resolve().parent
rows=[];phases={}
for case in ['light','fixture','parallel']:
 for mode in ['fresh','fork']:
  ds={label:[json.loads(p.read_text()) for p in sorted((E/'go').glob(f'plain-{case}-{mode}-*-{label}.json'))] for label in ['baseline','candidate']}
  vals={k:[d['suite_product_seconds']*1000 for d in v] for k,v in ds.items()}
  a,b=[statistics.median(vals[k]) for k in vals]
  pairs=[(y/x-1)*100 for x,y in zip(vals['baseline'],vals['candidate'])]
  rows.append(dict(language='Go',case=case,mode=mode,baseline_ms=a,candidate_ms=b,change_percent=(b/a-1)*100,slower_pairs=sum(x>0 for x in pairs),pairs=6,baseline_min_ms=min(vals['baseline']),baseline_max_ms=max(vals['baseline']),candidate_min_ms=min(vals['candidate']),candidate_max_ms=max(vals['candidate'])))
  phases[case+'-'+mode]={}
  for label,docs in ds.items():
   groups={}
   for d in docs:
    phase={}
    for op in d['operations']:
     key=re.sub(r'_\d+$','',op['name']);phase[key]=phase.get(key,0)+op['seconds']*1000
    for k,v in phase.items():groups.setdefault(k,[]).append(v)
   phases[case+'-'+mode][label]={k:statistics.median(v) for k,v in groups.items()}
for scale in ['small','medium']:
 ds={label:[json.loads(p.read_text()) for p in sorted((E/'python').glob(f'plain-{scale}-*-{label}.json'))] for label in ['baseline','candidate']}
 vals={k:[d['whole_ms'] for d in v] for k,v in ds.items()};a,b=[statistics.median(vals[k]) for k in vals]
 rows.append(dict(language='Python',case=scale,mode='prepared',baseline_ms=a,candidate_ms=b,change_percent=(b/a-1)*100,slower_pairs=sum(y>x for x,y in zip(vals['baseline'],vals['candidate'])),pairs=6,baseline_min_ms=min(vals['baseline']),baseline_max_ms=max(vals['baseline']),candidate_min_ms=min(vals['candidate']),candidate_max_ms=max(vals['candidate'])))
 phases['python-'+scale]={label:{k:statistics.median(d['times_ms'][k] for d in docs) for k in docs[0]['times_ms']} for label,docs in ds.items()}
 if scale=='small':
  a,b=[statistics.median(v[1:]) for v in vals.values()]
  phases['python-small']['excluding_first_pair_sensitivity']=dict(baseline_ms=a,candidate_ms=b,change_percent=(b/a-1)*100)
(E/'summary.json').write_text(json.dumps(dict(rows=rows,phases=phases),indent=2)+'\n')
with (E/'summary.csv').open('w') as f:
 w=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');w.writeheader();w.writerows(rows)
inputs=json.loads((E/'inputs.json').read_text());inputs['orchestrator_sha256']=hashlib.sha256((E/'run.py').read_bytes()).hexdigest();inputs['analysis_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest();inputs['cgo_enabled']='0'
inputs['guest_sha256']={label:json.loads((E.parent/'temp'/label/'release/generated-go-inputs.json').read_text())['guest_sha256'] for label in ['baseline','candidate']}
inputs['binary_bytes']={p.name:p.stat().st_size for p in (E.parent/'temp/bin').iterdir()}
(E/'inputs.json').write_text(json.dumps(inputs,indent=2)+'\n')
print(json.dumps(rows,indent=2))
