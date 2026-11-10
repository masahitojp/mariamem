"""Replay retained observations, including every child and all timing tails."""
from pathlib import Path
import gzip,hashlib,json,math,statistics as st,sys
sys.dont_write_bytecode=True
from decompose import decompose,events
P=Path(__file__).resolve().parent
p=P/'observations.json.gz';records=json.loads(gzip.decompress(p.read_bytes())) if p.exists() else json.loads((P/'observations.json').read_text())
def stats(v):
 assert v
 return dict(n=len(v),p50=st.median(v),p95=sorted(v)[math.ceil(len(v)*.95)-1],mean=st.mean(v),min=min(v),max=max(v),over100ms=sum(x>100 for x in v))
assert len(records)==16
seen=set();children=[];runs=[]
for r in records:
 key=(r['parallel'],r['mode'],r['repeat']);assert key not in seen;seen.add(key)
 assert r['accepted'] and r['exit_code']==0 and r['scratch_empty'];t=r['trace'];m=t['meta'];sp=t['spans']
 assert m['parallel']==str(r['parallel']) and m['fork_cap']==str(r['parallel']+1) and m['active_mappings_after']=='0' and m['test_exit']=='0'
 assert m['read_cases']=='50' and m['write_cases']=='20'
 for k,n in [('read',50),('write',20),('fork',21),('sample',21)]:assert sum(x['kind']==k for x in sp)==n
 assert all(0<=x['start_ms']<=x['end_ms']<=t['elapsed_ms'] for x in sp)
 forks={x['lane']:x for x in sp if x['kind']=='fork'};assert len(forks)==21
 if r['mode']=='on':decompose(r['stages']['root'])
 cr=[]
 for lane,span in forks.items():
  outer=span['end_ms']-span['start_ms'];c=dict(run=r['name'],parallel=r['parallel'],mode=r['mode'],repeat=r['repeat'],lane=lane,fork_ms=outer)
  if r['mode']=='on':
   assert set(r['stages'])==set(forks)|{'root'};tr=r['stages'][lane];g=decompose(tr);se=events(tr['startup']['events']);fe=events(tr['fork']['events']);ae=events(tr['api_startup']['events'])
   assert abs(fe['begin'])<1 and fe['end']<=outer+.02
   def interval(a,b):v=se[b]-se[a];assert v>=0;return v
   h={'filesystem_prepared':interval('filesystem_begin','filesystem_ready'),'memory_construct':interval('memory_begin','memory_ready'),'execute_to_ready':interval('execute_begin','ready_response_observed'),'ready_to_startup_end':interval('ready_response_observed','end')}
   h['api_host_other']=outer-sum(h.values());assert h['api_host_other']>=-.01
   assert abs(sum(h.values())-outer)<.001
   gm=events(tr['startup']['guest']['events']);g['routine_schema']=gm['routine_schema_complete']-gm['routine_schema_begin'];g['guest_main_to_ready']=gm['ready_prepared']-gm['guest_main'];g['guest_bootstrap']=gm['bootstrap_complete']-gm['server_init_complete']
   assert g['server_init']<=h['execute_to_ready']+.01
   h['diagnostic_read_nested']=interval('diagnostic_read_begin','diagnostic_read_end')
   c.update(host_ms=h,guest_ms=g,admission_to_handle_ms=fe['snapshot_handle_ready']-fe['begin'])
  else:assert r['stages'] is None
  children.append(c);cr.append(c)
 runs.append(dict(name=r['name'],parallel=r['parallel'],mode=r['mode'],repeat=r['repeat'],suite_ms=t['elapsed_ms'],cpu_ms=float(m['cpu_ms']),fork=stats([c['fork_ms'] for c in cr]),sample=stats([x['end_ms']-x['start_ms'] for x in sp if x['kind']=='sample'])))
assert seen=={(p,m,r) for p in [4,8] for m in ['off','on'] for r in [-1,0,1,2]}
summary={'runs':runs,'cells':{},'paired_observer_change':{},'scope':'Current b1218737 shop70/Pipe/P4,P8; three off/on pairs; warmups separate. Nested stages are elapsed, not exclusive CPU.'}
for par in [4,8]:
 for mode in ['off','on']:
  cs=[c for c in children if c['parallel']==par and c['mode']==mode and c['repeat']>=0];rs=[r for r in runs if r['parallel']==par and r['mode']==mode and r['repeat']>=0]
  cell=dict(suite_ms=stats([r['suite_ms'] for r in rs]),fork_ms=stats([c['fork_ms'] for c in cs]),process_median_fork_ms=stats([r['fork']['p50'] for r in rs]),cpu_ms=stats([r['cpu_ms'] for r in rs]))
  if mode=='on':
   for field in ['host_ms','guest_ms']:
    keys=sorted(cs[0][field]);assert all(sorted(c[field])==keys for c in cs)
    cell[field]={k:stats([c[field][k] for c in cs]) for k in keys}
   cell['admission_to_handle_ms']=stats([c['admission_to_handle_ms'] for c in cs])
   cell['server_init_share_of_total_fork_percent']=100*sum(c['guest_ms']['server_init'] for c in cs)/sum(c['fork_ms'] for c in cs)
  summary['cells'][f'p{par}-{mode}']=cell
 pairs=[]
 for n in range(3):
  off=next(r for r in runs if (r['parallel'],r['mode'],r['repeat'])==(par,'off',n));on=next(r for r in runs if (r['parallel'],r['mode'],r['repeat'])==(par,'on',n));pairs.append(dict(round=n,fork_p50_delta_ms=on['fork']['p50']-off['fork']['p50'],suite_delta_ms=on['suite_ms']-off['suite_ms'],suite_percent=100*(on['suite_ms']/off['suite_ms']-1)))
 summary['paired_observer_change'][str(par)]=pairs
text=json.dumps(summary,indent=2,sort_keys=True)+'\n'
if '--check' in sys.argv:
 assert (P/'summary.json').read_text()==text
 for n,h in json.loads((P/'SHA256SUMS.json').read_text()).items():assert hashlib.sha256((P/n).read_bytes()).hexdigest()==h,n
 print('PASS:16 processes,70 cases each,126 primary diagnostic children,nested stage/counter scopes,partitions,checksums')
else:
 (P/'summary.json').write_text(text)
 for key,c in summary['cells'].items():
  print(key,'fork',c['fork_ms'],'suite',c['suite_ms'])
  if 'host_ms' in c:
   print('HOST',{k:round(v['p50'],3) for k,v in c['host_ms'].items()});print('GUEST',{k:round(v['p50'],3) for k,v in c['guest_ms'].items() if not k.startswith('plugin.') or k in ['plugin.InnoDB','plugin.Aria']})
 print('OBSERVER',summary['paired_observer_change'])
