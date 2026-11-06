"""Reduce the twelve completed reports; preserve originals and owner logs separately."""
from pathlib import Path
import hashlib, json, gzip, tarfile
p=Path(__file__).parent
h=lambda x:hashlib.sha256(x.read_bytes()).hexdigest()
records=json.loads((p/'records.json').read_text());assert len(records)==12
observations=[];owners=[];originals=[]
for rec in records:
 archive=p/rec['owner_archive']['file'];assert h(archive)==rec['owner_archive']['sha256']
 ids=[];truncated=0;events=0;maxevents=0
 with tarfile.open(archive) as z:
  assert len(z.getmembers())==48
  for member in rec['owner_archive']['members']:
   raw=z.extractfile(member['file']).read();assert hashlib.sha256(raw).hexdigest()==member['sha256']
   v=json.loads(raw);ids.append(v['child']);truncated+=v['truncated'];events+=len(v['events']);maxevents=max(maxevents,len(v['events']))
 assert sorted(ids)==list(range(48)) and truncated==0
 owner=dict(child_indices=sorted(ids),truncated=truncated,events=events,max_events_per_child=maxevents)
 report=p/rec['report'];timing=p/(rec['name']+'-timing.json')
 observations.append(dict(name=rec['name'],parallel=rec['parallel'],rep=rec['rep'],arm=rec['arm'],report=json.loads(report.read_text()),timing=json.loads(timing.read_text()),owner=owner))
 owners.append(dict(name=rec['name'],archive=archive.name,sha256=h(archive),**owner))
 for src in [report,timing,p/(rec['name']+'.log')]:originals.append(dict(file=src.name,sha256=h(src)))
raw=json.dumps(observations,separators=(',',':')).encode()
with (p/'observations.json.gz').open('wb') as f:
 with gzip.GzipFile(fileobj=f,mode='wb',mtime=0,filename='') as z:z.write(raw)
with tarfile.open(p/'original-process-reports.tar.gz','w:gz') as z:
 for src in originals:z.add(p/src['file'],arcname=src['file'])
(p/'owner-summary.json').write_text(json.dumps(owners,indent=2)+'\n')
(p/'original-report-sha256.json').write_text(json.dumps(originals,indent=2)+'\n')
(p/'archive-digests.json').write_text(json.dumps({src.name:h(src) for src in p.glob('*.tar.gz')},indent=2)+'\n')
print('COLLECTED',len(observations),'processes; observations compressed bytes', (p/'observations.json.gz').stat().st_size)
