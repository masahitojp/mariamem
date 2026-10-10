import json,math,statistics,csv,random
from pathlib import Path
r=Path.cwd();e=r.parent/'evidence';groups={};suites={}
def add(key,v,version,trial):groups.setdefault(key,{}).setdefault(version,{}).setdefault(trial,[]).append(v)
for p in sorted((e/'performance').glob('*.json')):
 case,mode,trial,version=p.stem.split('-');trial=int(trial)
 if trial==99:continue
 d=json.loads(p.read_text());k=(case,mode)
 for metric in ['suite_product_seconds','suite_cpu_seconds']:
  add((case,mode,metric),d[metric],version,trial)
 for metric,v in d['go_memory'].items():add((case,mode,metric),v,version,trial)
 for op in d['operations']:
  n=op['name'];n=n.rsplit('_',1)[0] if n[-2:].isdigit() else n
  add((case,mode,n),op['seconds'],version,trial)
 for op in d['sql_details']:add((case,mode,'sql_'+op['name']),op['seconds'],version,trial)
def pct(vals,p):
 vals=sorted(vals);x=(len(vals)-1)*p;i=int(x);return vals[i]+(vals[min(i+1,len(vals)-1)]-vals[i])*(x-i)
rng=random.Random(460127);output=[]
for key,versions in sorted(groups.items()):
 if set(versions)!={'1268','1272'}:continue
 result={'case':key[0],'mode':key[1],'metric':key[2]}
 for v,trials in versions.items():
  vals=[x for xs in trials.values() for x in xs];result[v]={'trials':len(trials),'samples':len(vals),'p50':statistics.median(vals),'p95':pct(vals,.95),'min':min(vals),'max':max(vals)}
 base=result['1268']['p50'];result['delta_percent']=100*(result['1272']['p50']/base-1) if base else None
 ids=sorted(set(versions['1268'])&set(versions['1272']))
 # Paired process-trial medians: repeated SQL/DB observations are not independent trials.
 pairs=[(statistics.median(versions['1268'][i]),statistics.median(versions['1272'][i])) for i in ids]
 ratios=[b/a-1 for a,b in pairs if a>0]
 if ratios:
  draws=[statistics.median([rng.choice(ratios) for _ in ratios])*100 for _ in range(2000)]
  result['paired_median_percent']=statistics.median(ratios)*100
  result['paired_bootstrap_95_percent']=[pct(draws,.025),pct(draws,.975)]
 output.append(result)
(e/'statistics.json').write_text(json.dumps(output,indent=2))
with (e/'statistics.csv').open('w') as f:
 fields=['case','mode','metric','trials','samples','go126_p50','go126_p95','go126_min','go126_max','go127_p50','go127_p95','go127_min','go127_max','delta_percent','paired_ci_low','paired_ci_high'];w=csv.DictWriter(f,fieldnames=fields);w.writeheader()
 for x in output:
  row={k:x[k] for k in ['case','mode','metric','delta_percent']};row.update(trials=x['1268']['trials'],samples=x['1268']['samples'])
  for v,label in [('1268','go126'),('1272','go127')]:
   for m in ['p50','p95','min','max']:row[label+'_'+m]=x[v][m]
  ci=x.get('paired_bootstrap_95_percent',[None,None]);row.update(paired_ci_low=ci[0],paired_ci_high=ci[1]);w.writerow(row)
for x in output:
 if x['metric'] in ['suite_product_seconds','suite_cpu_seconds','load_snapshot']:
  print(x['case'],x['mode'],x['metric'],round(x['1268']['p50'],4),round(x['1272']['p50'],4),x['delta_percent'],x.get('paired_bootstrap_95_percent'))
