import json,statistics,sys
from pathlib import Path
e=Path(sys.argv[1]);summary={}
def stats(xs):return {'n':len(xs),'median':statistics.median(xs),'min':min(xs),'max':max(xs)}
for stage in ['plain','resources']:
 allcases=[json.loads(p.read_text())|{'label':p.parent.name} for p in sorted((e/stage).glob('n*/result.json'))];stageout={}
 for rows in [100,10000]:
  groups={mode:[r for r in allcases if r['mode']==mode and r['rows']==rows] for mode in ['control','file','heap']};out={}
  for mode,rs in groups.items():
   assert len(rs)==(6 if stage=='plain' else 3) and all(r['status']=='PASS' for r in rs),(stage,rows,mode)
   v={'whole_ms':stats([r['whole_ms'] for r in rs])}
   for k in ['setup/start','setup/migrate-seed','setup/snapshot','baseline/close']:v[k]=stats([r['times_ms'][k] for r in rs])
   for k in ['startup','connect','crud','disconnect','close']:v['per_child/'+k]=stats([r['times_ms'][c+'/'+k] for r in rs for c in ['first','second']])
   if mode=='heap':v['heap_stats']={k:stats([r['heap_stats'][k] for r in rs]) for k in rs[0]['heap_stats']}
   if stage=='resources':
    v['host_peak_maxrss_raw']=stats([max(m['maxrss_raw'] for m in r['host_metrics']) for r in rs])
    v['host_total_alloc_sum']=stats([sum(m['total_alloc'] for m in r['host_metrics']) for r in rs])
    v['host_process_count']=stats([len(r['host_metrics']) for r in rs])
    v['python_maxrss_raw']=stats([r['python_maxrss_raw'] for r in rs])
    v['host_num_gc_sum']=stats([sum(m['num_gc'] for m in r['host_metrics']) for r in rs])
   out[mode]=v
  out['comparisons']={}
  for target,base in [('heap','control'),('heap','file'),('file','control')]:
   pairs=[]
   for r in groups[base]:
    other=next(x for x in groups[target] if x['label'].rsplit('-',1)[0]==r['label'].rsplit('-',1)[0]);pairs.append({'label':r['label'].rsplit('-',1)[0],'baseline_ms':r['whole_ms'],'candidate_ms':other['whole_ms'],'delta_ms':other['whole_ms']-r['whole_ms']})
   out['comparisons'][target+'-vs-'+base]={'pairs':pairs,'faster_pairs':sum(p['delta_ms']<0 for p in pairs),'median_percent_change':100*(out[target]['whole_ms']['median']/out[base]['whole_ms']['median']-1)}
  stageout[str(rows)]=out
 summary[stage]=stageout
(e/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
for rows,r in summary['plain'].items():
 print(rows)
 for mode in ['control','file','heap']:print(mode,{k:round(v['median'],2) for k,v in r[mode].items() if k!='heap_stats'})
 print('changes',{k:round(v['median_percent_change'],2) for k,v in r['comparisons'].items()})
