"""Reduce retained product JSON; never run a benchmark or discard slow samples."""
import argparse,csv,json,statistics
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__);p.add_argument('directory',type=Path);a=p.parse_args()
rows=[]
for f in sorted(a.directory.glob('*.json')):
 if f.name=='inputs.json' or f.name.startswith('pilot-'):continue
 d=json.loads(f.read_text());parts=f.stem.split('-');state,language=parts[:2]
 if 'native-fixture' in f.stem:case='native-fixture';trial=parts[4];mode='-'.join(parts[5:])
 else:case,trial=parts[2:4];mode='-'.join(parts[4:])
 r={'file':f.name,'state':state,'language':language,'case':case,'trial':int(trial),'mode':mode,
    'wall_seconds':d.get('suite_product_seconds',d.get('suite_wall_seconds')),
    'cpu_seconds':d.get('suite_cpu_seconds',d.get('runner_and_reaped_host_cpu_seconds',d.get('runner_cpu_seconds')))}
 obs=d.get('go_resource_observation',{});res=d.get('resources',{});end=obs.get('after',{});start=obs.get('before',{})
 for key in ['process_peak_rss_bytes','sampled_peak_go_heap_objects_bytes','cumulative_alloc_bytes']:r[key]=obs.get(key)
 for key in ['heap_alloc_bytes','heap_inuse_bytes','heap_released_bytes','goroutines']:r['after_'+key]=end.get(key)
 for key in ['rss_bytes','primary_bytes']:r['after_'+key]=res.get('after',{}).get(key)
 r['file_mapping_delta_bytes']=res['after']['file_mapping_bytes']-res['before']['file_mapping_bytes'] if 'after' in res else None
 r['fd_delta']=d['fds_after']-d['fds_before'] if 'fds_after' in d else None
 r['goroutine_delta']=end['goroutines']-start['goroutines'] if end else None
 mapping=end.get('linear_memory_virtual',{})
 r['active_mappings_after']=mapping.get('active_mappings')
 r['mapping_creates']=mapping.get('creates');r['mapping_releases']=mapping.get('releases')
 r['release_failures']=mapping.get('release_failures')
 r['sampled_host_rss_bytes']=max([s.get('after_sql_resources',{}).get('rss_bytes',0) for s in d.get('samples',[])],default=0) or None
 rows.append(r)
with (a.directory.parent/'cells.csv').open('w') as out:
 w=csv.DictWriter(out,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def q(values,p):
 v=sorted(values);i=(len(v)-1)*p;j=int(i);return v[j]+(v[min(j+1,len(v)-1)]-v[j])*(i-j)
groups={}
for r in rows:groups.setdefault((r['state'],r['language'],r['case'],r['mode']),[]).append(r)
summary=[]
for key,rs in sorted(groups.items()):
 for metric in list(rows[0])[6:]:
  values=[r[metric] for r in rs if r[metric] is not None]
  if not values:continue
  summary.append(dict(zip(['state','language','case','mode'],key),metric=metric,n=len(values),p50=statistics.median(values),p95=q(values,.95),minimum=min(values),maximum=max(values)))
with (a.directory.parent/'summary.csv').open('w') as out:
 w=csv.DictWriter(out,fieldnames=list(summary[0]));w.writeheader();w.writerows(summary)
paired=[]
for s in summary:
 if s['state']!='v047':continue
 b=next((v for v in summary if v['state']=='v046' and all(v[k]==s[k] for k in ['language','case','mode','metric'])),None)
 if b:paired.append({**{k:s[k] for k in ['language','case','mode','metric','n']},'v046_p50':b['p50'],'v047_p50':s['p50'],'absolute_delta':s['p50']-b['p50'],'relative_percent':100*(s['p50']/b['p50']-1) if b['p50'] else None,'v046_p95':b['p95'],'v047_p95':s['p95']})
with (a.directory.parent/'comparison.csv').open('w') as out:
 w=csv.DictWriter(out,fieldnames=list(paired[0]));w.writeheader();w.writerows(paired)
print(json.dumps({'cells':len(rows),'groups':len(groups),'mapping_release_all_balanced':all(r['active_mappings_after']==0 and r['mapping_creates']==r['mapping_releases'] and r['release_failures']==0 for r in rows if r['active_mappings_after'] is not None)},indent=2))
