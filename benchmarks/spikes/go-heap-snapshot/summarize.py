"""Derive paired timing and separate resource evidence from complete cases."""
import json,statistics,sys
from pathlib import Path
e=Path(sys.argv[1])
def stats(xs):return {'n':len(xs),'median':statistics.median(xs),'min':min(xs),'max':max(xs)}
summary={}
for stage in ['plain','resources']:
 cases=[json.loads(p.read_text())|{'label':p.stem} for p in sorted((e/stage).glob('n*.json'))]
 out={}
 for rows in [100,10000]:
  grouped={mode:[d for d in cases if d['mode']==mode and d['rows']==rows] for mode in ['control','heap']};item={}
  for mode,ds in grouped.items():
   assert len(ds)==(5 if stage=='plain' else 3),(stage,rows,mode)
   assert all(d['status']=='PASS' for d in ds)
   values={'whole_ms':stats([d['whole_ms'] for d in ds])}
   for key in ['setup/start','setup/migrate-seed','setup/snapshot','baseline/close']:values[key]=stats([d['times_ms'][key] for d in ds])
   for key in ['startup','crud','close','disconnect']:values['per_child/'+key]=stats([d['times_ms'][name+'/'+key] for d in ds for name in ['first','second']])
   values['two_children_ms']=stats([sum(v for k,v in d['times_ms'].items() if k.startswith(('first/','second/'))) for d in ds])
   if mode=='heap':values['heap_stats']={k:stats([d['heap_stats'][k] for d in ds]) for k in ds[0]['heap_stats']}
   if stage=='resources':
    values['resources']={phase:{k:stats([d['resources'][phase][k] for d in ds]) for k in ds[0]['resources'][phase]} for phase in ds[0]['resources']}
    values['post_close_forced_gc_ms']=stats([d['post_close_forced_gc_ms'] for d in ds])
   item[mode]=values
  pairs=[]
  for control in grouped['control']:
   heap=next(d for d in grouped['heap'] if d['label'].replace('heap','control')==control['label'])
   pairs.append({'label':control['label'],'control_ms':control['whole_ms'],'heap_ms':heap['whole_ms'],'delta_ms':heap['whole_ms']-control['whole_ms']})
  item['pairs']=pairs;item['heap_faster_pairs']=sum(d['delta_ms']<0 for d in pairs);item['median_delta_percent']=100*(item['heap']['whole_ms']['median']/item['control']['whole_ms']['median']-1)
  out[str(rows)]=item
 summary[stage]=out
(e/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
print(json.dumps(summary,indent=2))
