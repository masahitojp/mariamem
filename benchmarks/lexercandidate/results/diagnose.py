from pathlib import Path
import json,sys,tarfile,hashlib
from codec import read
from undo_analysis import analyze_trace
E=Path(__file__).resolve().parent
records=read(E/'observations.json')
archive=Path(sys.argv[sys.argv.index('--archive')+1]) if '--archive' in sys.argv else E/'undo-traces.tar.gz'
assert hashlib.sha256(archive.read_bytes()).hexdigest()==json.loads((E/'archive-digests.json').read_text())['archives']['undo-traces.tar.gz']
out={'scope':'576 primary diagnostic children, with owner attribution; elapsed diagnostics only','children':0,'purge_scopes':0,'purge_aborts':0,'query_rseg_waits':[],'background_page_waits':[],'links':[],'max_events_per_child':0,'sql_over100ms':[]}
with tarfile.open(archive) as tar:
 for rec in records:
  if rec['kind']!='primary' or rec['observer']!='on':continue
  for sample in rec['report']['samples']:
   for z in sample['spans']:
    if z['name'] in ['update','count_sum'] and z['end_ms']-z['begin_ms']>100:out['sql_over100ms'].append({'arm':rec['arm'],'parallel':rec['parallel'],'rep':rec['rep'],'index':sample['index'],'phase':z['name'],'ms':z['end_ms']-z['begin_ms']})
  for name in rec['undo_files']:
   tr=json.load(tar.extractfile(name));assert not tr['truncated'];events=tr['events'] or [];a=analyze_trace(name,tr['child'],events)
   out['children']+=1;out['purge_scopes']+=a['purge_scopes'];out['purge_aborts']+=a['purge_aborts'];out['max_events_per_child']=max(out['max_events_per_child'],len(events))
   for k in ['query_rseg_waits','background_page_waits','links']:
    out[k].extend(dict(x,trace=name,arm=rec['arm'],parallel=rec['parallel'],rep=rec['rep']) for x in a[k])
assert out['children']==576
if '--check' in sys.argv:assert out==json.loads((E/'diagnostics.json').read_text());print('UNDO owner replay PASS:576 primary children')
else:(E/'diagnostics.json').write_text(json.dumps(out,indent=2)+'\n');print({k:(len(v) if isinstance(v,list) else v) for k,v in out.items()})
