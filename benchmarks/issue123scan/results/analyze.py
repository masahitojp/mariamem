"""Read-only replay of the fixed same-binary scan comparison; compact observations only."""
import argparse,json,math,statistics,hashlib,pathlib,gzip
p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');a=p.parse_args();root=pathlib.Path(__file__).resolve().parent
rows=json.loads(gzip.decompress((root/'observations.json.gz').read_bytes()));med=statistics.median
assert len(rows)==56
expected={(a,m,p,rep,'primary') for a in ['full','bounded'] for m in ['fresh','fork'] for p in [1,4] for rep in range(5)}
expected|={(a,m,p,-1,'warmup') for a in ['full','bounded'] for m in ['fresh','fork'] for p in [1,4]}
expected|={(a,m,1,-2,k) for a in ['full','bounded'] for m in ['fresh','fork'] for k in ['pilot','negative']}
assert {(v['variant'],v['mode'],v['parallel'],v['rep'],v['kind']) for v in rows}==expected
for v in rows:
 assert v['negative']==(v['kind']=='negative')
 assert v['count']==(1 if v['negative'] else 2 if v['kind']=='pilot' else 48)
 assert v['report']['image_stats']['scanned_bytes']==(268435456 if v['variant']=='full' else 18612224)
primary=[r for r in rows if r['kind']=='primary'];assert len(primary)==40
q95=lambda v:sorted(v)[math.ceil(.95*len(v))-1]
summary={'scope':'Single-Mac same-binary two-arm ordinary mixed lifecycle,48 independent cases,5 rounds; all tails retained. Cold image build and final disposal included. No Ubuntu/product adoption claim.','cells':{},'comparisons':{}}
for x in rows:
 r=x['report'];assert r['cleanup'] and r['resolved_max_forks']==(x['parallel'] if x['mode']=='fork' else 0)
 assert 0<r['max_active']<=x['parallel'];assert all(r['cleanup_stats'][k]==0 for k in ['active_mappings','active_reserved_bytes','active_rw_bytes','release_failures'])
 if x['negative']:assert x['exit_code']==1 and not r['success'] and 'pristine oracle' in r['error']
 else:
  assert x['exit_code']==0 and r['success'] and len(r['samples'])==x['count']
  assert {v['index'] for v in r['samples']}==set(range(x['count']))
  assert all(v['oracle'] and v['cleanup'] and not v.get('error') for v in r['samples'])
 if x['variant'] in ['full','bounded'] and not x['negative']:assert r['image_stats']['acquires']==x['count']+(x['mode']=='fork')
 im=r['image_stats']; assert im['initialized_page_bytes']==8929280 and len(im['image_ranges'])==22 and im['full_scan']==(x['variant']=='full')
 if x['variant'] in ['full','bounded']:assert r['image_stats']['builds']==1 and r['image_stats']['closed'] and r['image_stats']['owned_fds']==0 and r['image_stats']['page_only']
for mode in ['fresh','fork']:
 for n in [1,4]:
  key=f'{mode}-p{n}';cell={};per={}
  for arm in ['full','bounded']:
   cohort=sorted([x for x in primary if x['mode']==mode and x['parallel']==n and x['variant']==arm],key=lambda x:x['rep']);assert [x['rep'] for x in cohort]==list(range(5))
   stats=[]
   for x in cohort:
    r=x['report'];phases={}
    for sample in r['samples']:
     for span in sample['spans']:phases.setdefault(span['name'],[]).append(span['end_ms']-span['begin_ms'])
    out={k:r[k] for k in ['suite_ms','suite_cpu_ms','batch_ms','batch_cpu_ms','lifetime_max_rss_bytes']}
    for name,values in phases.items():
     out[name+'_p50_ms']=med(values);out[name+'_p95_ms']=q95(values);out[name+'_gt100_count']=sum(v>100 for v in values)
    out['image_build_ms']=r.get('image_stats',{}).get('build_ms',0)
    out['constructor_ms']=r['image_stats']['constructor_ms']
    out['scan_ms']=r['image_stats']['scan_ms']
    out['scanned_bytes']=r['image_stats']['scanned_bytes']
    out['image_page_bytes']=r.get('image_stats',{}).get('initialized_page_bytes',0)
    out['root_start_ms']=sum(z['end_ms']-z['begin_ms'] for z in r['root_spans'] if z['name']=='root_start')
    out['image_close_ms']=sum(z['end_ms']-z['begin_ms'] for z in r['root_spans'] if z['name']=='image_close')
    out['sql_gt100_count']=sum(out[k+'_gt100_count'] for k in ['select1','count_sum','update','verify_update'])
    stats.append(out)
   per[arm]=stats
   cell[arm]={'processes':stats,'medians':{k:med([v[k] for v in stats]) for k in stats[0]},'suite_range_ms':[min(v['suite_ms'] for v in stats),max(v['suite_ms'] for v in stats)],'total_sql_gt100':sum(v['sql_gt100_count'] for v in stats)}
  summary['cells'][key]=cell
  summary['comparisons'][key]={}
  for base,cand in [('full','bounded')]:
   comparison={}
   for k in ['suite_ms','suite_cpu_ms','batch_ms','batch_cpu_ms','start_or_fork_p50_ms','start_or_fork_p95_ms','lifetime_max_rss_bytes','image_build_ms','scan_ms','constructor_ms']:
    bv=[v[k] for v in per[base]];cv=[v[k] for v in per[cand]];pct=[100*(y/x-1) for x,y in zip(bv,cv)]
    comparison[k]={'paired_percent':pct,'paired_ms_or_bytes':[y-x for x,y in zip(bv,cv)],'median_paired_percent':med(pct),'improved_pairs':sum(y<x for x,y in zip(bv,cv))}
   summary['comparisons'][key][base+'->'+cand]=comparison
text=json.dumps(summary,indent=2)+'\n'
if a.check:
 assert (root/'summary.json').read_text()==text
 for name,digest in json.loads((root/'SHA256SUMS.json').read_text()).items():assert hashlib.sha256((root/name).read_bytes()).hexdigest()==digest,name
else:(root/'summary.json').write_text(text)
for key,cell in summary['cells'].items():
 print(key,[(arm,round(v['medians']['suite_ms'],1),round(v['medians']['start_or_fork_p50_ms'],2),v['total_sql_gt100']) for arm,v in cell.items()])
 for name,c in summary['comparisons'][key].items():print(' ',name,[(k,round(c[k]['median_paired_percent'],2),c[k]['improved_pairs']) for k in ['suite_ms','suite_cpu_ms','start_or_fork_p50_ms']])
