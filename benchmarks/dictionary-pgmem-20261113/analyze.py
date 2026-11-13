from pathlib import Path
import copy,csv,io,json,statistics,sys
E=Path(__file__).resolve().parent
def read(name):return json.loads((E/name).read_text())
def q(v,p):
 v=sorted(v);i=(len(v)-1)*p;a=int(i);return v[a]+(v[min(a+1,len(v)-1)]-v[a])*(i-a)
def stats(v):return {'median':statistics.median(v),'p95':q(v,.95),'min':min(v),'max':max(v)}
def reduce(data):
 plan=data['plan'];inputs=data['inputs'];records=data['records'];assert data['completion']['result']=='PASS'
 assert len(records)==42
 variants={'baseline-pipe':'baseline','candidate-pipe':'candidate','pgmem-pipe':'pgmem'}
 expected={(v,p,r) for v in variants for p in (4,8) for r in range(5)}
 actual=[(r['variant'],r['parallel'],r['repetition']) for r in records if not r['negative'] and not r['warmup'] and r['repetition']>=0]
 assert len(actual)==30 and set(actual)==expected
 assert sum(r['negative'] for r in records)==3 and sum(r['warmup'] for r in records)==6
 assert inputs['harness_source_commit']==plan['harness_source_commit']
 for product,pin in plan['products'].items():assert inputs['products'][product]['source_commit']==pin['source_commit']
 rows=[]
 for r in records:
  d=data['reports'][r['report']];m=data['memory'][r['memory']];label=variants[r['variant']]
  assert r['binary_sha256']==inputs['binaries'][label]['sha256']
  assert d['backend']==('pgmem' if label=='pgmem' else 'mariamem') and d['route']=='pipe' and d['go']=='go1.27.4' and d['gomaxprocs']==8 and d['parallel']==r['parallel']
  assert d['cleanup_complete'] and d['root_closed_before_forks'] and d['corrupt_seed']==r['negative']
  assert m['peak_active_children']<=r['parallel']
  if r['negative']:
   assert not d['success'] and r['returncode']!=0 and 'pristine oracle' in d['error'];continue
  assert d['success'] and r['returncode']==0 and len(d['samples'])==r['count'] and {s['index'] for s in d['samples']}==set(range(r['count']))
  assert m['peak_active_children']==r['parallel'] and m['sampled_peak_rss_bytes']>0
  assert all(s['oracle'] and s['cleanup_complete'] for s in d['samples'])
  assert d['cpu_user_ms']>=0 and d['cpu_system_ms']>=0 and d['batch_ms']>0
  if r['warmup'] or r['repetition']<0:continue
  assert r['count']==48
  row={k:r[k] for k in ['variant','parallel','repetition']}
  row.update(batch_ms=d['batch_ms'],cpu_ms=d['cpu_user_ms']+d['cpu_system_ms'],peak_rss_mib=m['sampled_peak_rss_bytes']/2**20,root_start_ms=d['root_start_ms'],snapshot_ms=d['snapshot_ms'],external_process_wall_ms=r['process_wall_ms'])
  for metric in ['fork_ms','connect_ms','select_ms','sql_ms','cleanup_ms','total_ms']:
   values=[s[metric] for s in d['samples']];assert all(v>=0 for v in values)
   row.update({metric+'_p50':statistics.median(values),metric+'_p95':q(values,.95),metric+'_max':max(values),metric+'_over100':sum(v>100 for v in values)})
  rows.append(row)
 cells=[]
 for p in (4,8):
  for variant in variants:
   rs=sorted([r for r in rows if r['parallel']==p and r['variant']==variant],key=lambda r:r['repetition']);assert len(rs)==5
   cell={'variant':variant,'parallel':p,'processes':5,'children':240,'metrics':{k:stats([r[k] for r in rs]) for k in rs[0] if k not in ['variant','parallel','repetition']},'process_values':rs}
   cell['threshold_counts']={k:sum(r[k] for r in rs) for k in rs[0] if k.endswith('_over100')}
   cells.append(cell)
 comparisons=[]
 for p in (4,8):
  for base in ['baseline-pipe','pgmem-pipe']:
   a=next(c for c in cells if c['variant']==base and c['parallel']==p);b=next(c for c in cells if c['variant']=='candidate-pipe' and c['parallel']==p)
   deltas=[(y['batch_ms']/x['batch_ms']-1)*100 for x,y in zip(a['process_values'],b['process_values'])]
   comparisons.append({'parallel':p,'base':base,'target':'candidate-pipe','ratios_of_medians':{k:b['metrics'][k]['median']/a['metrics'][k]['median'] for k in ['batch_ms','cpu_ms','peak_rss_mib']},'paired_wall_percent':deltas,'paired_wall_percent_median':statistics.median(deltas),'candidate_faster_pairs':sum(d<0 for d in deltas)})
 return {'cells':cells,'comparisons':comparisons,'validation':{'ordinary_processes':30,'ordinary_children':1440,'warmups':6,'positive_pilots':3,'negative_controls':3,'all_observations_retained':True}},rows
def csv_text(rows):
 buf=io.StringIO();writer=csv.DictWriter(buf,fieldnames=list(rows[0]),lineterminator='\n');writer.writeheader();writer.writerows(rows);return buf.getvalue()
records=read('records.json')
data={'plan':read('plan.json'),'inputs':read('inputs.json'),'completion':read('measurement-complete.json'),'records':records,'reports':{r['report']:read(r['report']) for r in records},'memory':{r['memory']:read(r['memory']) for r in records}}
summary,rows=reduce(data)
if '--check' in sys.argv:
 assert read('summary.json')==summary and (E/'results.csv').read_text()==csv_text(rows)
 for kind in ['missing_process','duplicate_process','wrong_oracle','wrong_binary']:
  bad=copy.deepcopy(data);r=next(r for r in bad['records'] if r['repetition']==0)
  if kind=='missing_process':bad['records'].remove(r)
  if kind=='duplicate_process':r['repetition']=1
  if kind=='wrong_oracle':bad['reports'][r['report']]['samples'][0]['oracle']=False
  if kind=='wrong_binary':r['binary_sha256']='0'*64
  try:reduce(bad)
  except AssertionError:pass
  else:raise AssertionError('mutation admitted '+kind)
 print('PASS: readonly 42-process validation, exact summary/CSV, four rejection controls')
else:
 (E/'summary.json').write_text(json.dumps(summary,indent=2)+'\n');(E/'results.csv').write_text(csv_text(rows))
 for c in summary['cells']:print(c['variant'],c['parallel'],{k:round(c['metrics'][k]['median'],3) for k in ['batch_ms','cpu_ms','peak_rss_mib','fork_ms_p50','cleanup_ms_p50']},c['threshold_counts'])
 for c in summary['comparisons']:print(c)
