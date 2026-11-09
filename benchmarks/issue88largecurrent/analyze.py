import pathlib,json,statistics,argparse,math
p=argparse.ArgumentParser();p.add_argument('--check',action='store_true');args=p.parse_args();root=pathlib.Path(__file__).resolve().parent
obs=json.loads((root/'observations.json').read_text())
assert len(obs)==20
med=statistics.median
def p95(v):return sorted(v)[math.ceil(.95*len(v))-1]
summary={'scope':'Five alternating pairs, single Mac, validated two-argv experimental overlay, all samples retained. No release/platform acceptance.','fixtures':{}}
for fixture,n in [('large',8)]:
 out={'serial':{},'rss':{}}
 for arm in (16,8):
  records=[r for r in obs if r['fixture']==fixture and r['mode']=='serial' and r['requested_pool_mib']==arm];assert len(records)==5
  assert all(len(r['samples'])==n for r in records)
  data={}
  for key in ('fork_ms','fork_cpu_ms','first_sql_ms','second_scan_ms','update_ms','disconnect_ms','close_ms','lifecycle_ms'):
   v=[s[key] for r in records for s in r['samples']]
   data[key]={'p50':med(v),'p95':p95(v),'max':max(v),'over100ms':sum(x>100 for x in v),'process_p50':[med([s[key] for s in r['samples']]) for r in records]}
  out['serial'][str(arm)]=data
  holds=[r for r in obs if r['fixture']==fixture and r['mode']=='hold' and r['requested_pool_mib']==arm];assert len(holds)==5
  inc={k:[(r['rss_points'][str(k)]['rss_bytes']-r['rss_points']['0']['rss_bytes'])/2**20 for r in holds] for k in (1,4)}
  out['rss'][str(arm)]={str(k):{'median_increment_mib':med(v),'per_process_increment_mib':v} for k,v in inc.items()}
 out['paired']={}
 for key in out['serial']['16']:
  base=out['serial']['16'][key]['process_p50'];cand=out['serial']['8'][key]['process_p50'];pct=[100*(c/b-1) for b,c in zip(base,cand)]
  out['paired'][key]={'percent_deltas':pct,'median_percent':med(pct),'improved_pairs':sum(c<b for b,c in zip(base,cand)),'ms_deltas':[c-b for b,c in zip(base,cand)]}
 out['physical_table_bytes']=sorted(set(r['table_allocated_bytes'] for r in obs if r['fixture']==fixture))
 summary['fixtures'][fixture]=out
for r in obs:
 assert r['success'] and r['mapping_stats']['active_mappings']==0
 assert all(v==r['requested_pool_mib']*2**20 for v in r['settings'].values())
 if r['mode']=='serial':assert r['child_settings']==r['settings']
text=json.dumps(summary,indent=2)+'\n'
if args.check:assert (root/'summary.json').read_text()==text
else:(root/'summary.json').write_text(text)
for f,o in summary['fixtures'].items():
 print(f,'physical',o['physical_table_bytes'])
 for k in o['paired']:
  print(k,round(o['serial']['16'][k]['p50'],3),'->',round(o['serial']['8'][k]['p50'],3),'paired%',round(o['paired'][k]['median_percent'],2),'improved',o['paired'][k]['improved_pairs'])
 print('RSS',o['rss'])
