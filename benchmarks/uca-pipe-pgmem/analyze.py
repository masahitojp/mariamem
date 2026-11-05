from pathlib import Path
import json,statistics,sys,csv,hashlib,copy,io
E=Path(__file__).resolve().parent
read=lambda p:json.loads(p.read_text())
def q(v,p):
 v=sorted(v);i=(len(v)-1)*p;a=int(i);return v[a]+(v[min(a+1,len(v)-1)]-v[a])*(i-a)
def reduce(records):
 ordinary=[r for r in records if not r['negative'] and not r['warmup'] and r['repetition']>=0];assert len(ordinary)==24
 rows=[]
 for r in ordinary:
  d=read(E/r['report']);m=read(E/r['memory']);assert r['returncode']==0 and d['success'] and d['cleanup_complete'] and d['root_closed_before_forks'];assert len(d['samples'])==48 and all(s['oracle'] and s['cleanup_complete'] for s in d['samples']);assert d['route']==('tcp' if r['variant']=='candidate-tcp' else 'pipe')
  assert m['peak_active_children']==r['parallel'];v={'variant':r['variant'],'parallel':r['parallel'],'repetition':r['repetition'],'batch_ms':d['batch_ms'],'cpu_ms':d['cpu_user_ms']+d['cpu_system_ms'],'process_wall_ms':r['process_wall_ms'],'sampled_peak_rss_mib':m['sampled_peak_rss_bytes']/2**20 if m['sampled_peak_rss_bytes'] is not None else None,'root_start_ms':d['root_start_ms'],'snapshot_ms':d['snapshot_ms'],'sql_over100ms':sum(s['sql_ms']>100 for s in d['samples']),'select_over100ms':sum(s['select_ms']>100 for s in d['samples']),'fork_over100ms':sum(s['fork_ms']>100 for s in d['samples'])};v['cpu_per_child_ms']=v['cpu_ms']/48
  for metric in ['fork_ms','connect_ms','select_ms','sql_ms','cleanup_ms','total_ms']:
   values=[s[metric] for s in d['samples']];v[metric+'_p50']=statistics.median(values);v[metric+'_p95']=q(values,.95);v[metric+'_max']=max(values)
  rows.append(v)
 summary=[]
 for p in [4,8]:
  for label in ['release-pipe','candidate-tcp','candidate-pipe','pgmem-pipe']:
   rs=[r for r in rows if r['variant']==label and r['parallel']==p];assert len(rs)==3 and {r['repetition'] for r in rs}=={0,1,2};entry={'variant':label,'parallel':p,'processes':3,'children':144,'batch_ms':{'median':statistics.median(r['batch_ms'] for r in rs),'min':min(r['batch_ms'] for r in rs),'max':max(r['batch_ms'] for r in rs)},'process_values':rs}
   for k in rs[0]:
    if k not in ['variant','parallel','repetition','batch_ms']:
     values=[r[k] for r in rs if r[k] is not None];entry[k+'_median']=statistics.median(values) if values else None
   entry['sql_over100ms_count']=sum(r['sql_over100ms'] for r in rs);entry['select_over100ms_count']=sum(r['select_over100ms'] for r in rs);summary.append(entry)
 ratios=[]
 for p in [4,8]:
  for base,target,comparison in [('release-pipe','candidate-pipe','UCA on same Pipe'),('candidate-tcp','candidate-pipe','Pipe on same candidate'),('pgmem-pipe','candidate-pipe','candidate/pgmem both Pipe')]:
   a=next(r for r in summary if r['variant']==base and r['parallel']==p);b=next(r for r in summary if r['variant']==target and r['parallel']==p);ratios.append({'parallel':p,'comparison':comparison,'batch_ratio':b['batch_ms']['median']/a['batch_ms']['median'],'cpu_ratio':b['cpu_ms_median']/a['cpu_ms_median'],'paired_batch_changes_percent':[(y['batch_ms']/x['batch_ms']-1)*100 for x,y in zip(sorted(a['process_values'],key=lambda r:r['repetition']),sorted(b['process_values'],key=lambda r:r['repetition']))]})
 return {'cells':summary,'comparisons':ratios},rows
records=read(E/'records.json');assert read(E/'measurement-complete.json')['result']=='PASS';summary,rows=reduce(records)
if '--check' in sys.argv:
 assert summary==read(E/'summary.json')
 buf=io.StringIO();writer=csv.DictWriter(buf,fieldnames=list(rows[0]),lineterminator='\n');writer.writeheader();writer.writerows(rows);assert buf.getvalue()==(E/'results.csv').read_text()
 for kind in ['missing_process','route']:
  bad=copy.deepcopy(records)
  if kind=='missing_process':bad=[r for r in bad if not (r['variant']=='candidate-pipe' and r['parallel']==4 and r['repetition']==0)]
  else:
   # Wrong transport label must conflict with the immutable original report.
   r=next(r for r in bad if r['variant']=='candidate-tcp' and r['repetition']==0);r['variant']='candidate-pipe'
  try:reduce(bad)
  except AssertionError:pass
  else:raise AssertionError('mutation admitted '+kind)
 print('PASS readonly24-process reduction and two rejection controls')
else:
 (E/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
 with (E/'results.csv').open('w',newline='') as f:
  writer=csv.DictWriter(f,fieldnames=list(rows[0]),lineterminator='\n');writer.writeheader();writer.writerows(rows)
 for r in summary['cells']:print(r['variant'],r['parallel'],'batch',round(r['batch_ms']['median'],1),'CPU',round(r['cpu_ms_median'],1),'Fork',round(r['fork_ms_p50_median'],1),'close',round(r['cleanup_ms_p50_median'],1),'slow SQL',r['sql_over100ms_count'])
 for r in summary['comparisons']:print(r)
