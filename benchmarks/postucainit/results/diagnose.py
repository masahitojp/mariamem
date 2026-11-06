from pathlib import Path
import json,sys,tarfile,hashlib
from undo_analysis import analyze_trace
root=Path(__file__).resolve().parent
manifest=json.loads((root/'archive-digests.json').read_text())
out={'children':0,'purge_scopes':0,'purge_aborts':0,'query_rseg_waits':0,'background_page_waits':0,'links':0,'max_events_per_child':0,'scope':'all observer-on processes, including pilots and warmups; not primary performance or #68 investigation'}
for name,sha in sorted(manifest['undo_archives'].items()):
 p=root.parent/name;assert hashlib.sha256(p.read_bytes()).hexdigest()==sha
 with tarfile.open(p) as tar:
  for m in tar.getmembers():
   tr=json.load(tar.extractfile(m));assert not tr['truncated'];events=tr['events'] or []
   a=analyze_trace(name+'/'+m.name,tr['child'],events);out['children']+=1;out['max_events_per_child']=max(out['max_events_per_child'],len(events))
   for k in ['purge_scopes','purge_aborts']:out[k]+=a[k]
   for k in ['query_rseg_waits','background_page_waits','links']:out[k]+=len(a[k])
assert out['children']==389
if '--check' in sys.argv:assert out==json.loads((root/'diagnostics.json').read_text());print('Owner archive replay PASS:389 child traces')
else:(root/'diagnostics.json').write_text(json.dumps(out,indent=2)+'\n');print(out)
