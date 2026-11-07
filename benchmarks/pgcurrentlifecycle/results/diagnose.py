from pathlib import Path
import json,sys,tarfile,hashlib
from undo_analysis import analyze_trace
root=Path(__file__).resolve().parent
records=json.loads((root/'records.json').read_text())
observations=json.loads((root/'observations.json').read_text())
archive=Path(sys.argv[sys.argv.index('--archive')+1]) if '--archive' in sys.argv else root/'undo-traces.tar.gz';expected=json.loads((root/'archive-digests.json').read_text())['archives']['undo-traces.tar.gz']
assert hashlib.sha256(archive.read_bytes()).hexdigest()==expected
out={'scope':'mariamem-only diagnostic, excluded from primary timing','processes':[],'children':0,'purge_scopes':0,'purge_aborts':0,'query_rseg_waits':[],'background_page_waits':[],'links':[],'max_events_per_child':0}
with tarfile.open(archive) as tar:
 for rec in records:
  if rec['kind']!='diagnostic':continue
  r=observations[rec['report']];updates=[z['end_ms']-z['begin_ms'] for x in r['samples'] for z in x['spans'] if z['name']=='update']
  out['processes'].append({'mode':rec['mode'],'suite_ms':r['suite_ms'],'update_gt100ms':sum(v>100 for v in updates),'max_update_ms':max(updates),'traces':len(rec['trace_reports'])})
  for name in rec['trace_reports']:
   tr=json.load(tar.extractfile(name));assert not tr['truncated'];events=tr['events'] or []
   out['max_events_per_child']=max(out['max_events_per_child'],len(events));a=analyze_trace(name,tr['child'],events);out['children']+=1;out['purge_scopes']+=a['purge_scopes'];out['purge_aborts']+=a['purge_aborts']
   for k in ['query_rseg_waits','background_page_waits','links']:
    for x in a[k]:out[k].append(dict(x,trace=name,mode=rec['mode']))
assert out['children']==96
if '--check' in sys.argv:
 assert out==json.loads((root/'diagnostics.json').read_text());print('Diagnostic archive replay PASS:96 child traces')
else:(root/'diagnostics.json').write_text(json.dumps(out,indent=2)+'\n')
