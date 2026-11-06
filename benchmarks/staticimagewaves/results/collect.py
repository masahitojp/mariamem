from pathlib import Path
import json,gzip,tarfile,hashlib
p=Path(__file__).parent
h=lambda data:hashlib.sha256(data).hexdigest()
records=json.loads((p/'records.json').read_text());assert len(records)==18
obs={r['report']:json.loads((p/r['report']).read_text()) for r in records}
with (p/'observations.json.gz').open('wb') as f:
 with gzip.GzipFile(fileobj=f,mode='wb',filename='',mtime=0) as z:z.write(json.dumps(obs,separators=(',',':')).encode())
originals=[];owners=[];timings={}
for r in records:
 for name in [r['report'],r['name']+'.log']:
  f=p/name;originals.append({'file':name,'sha256':h(f.read_bytes())})
 if r['kind']=='diagnostic':
  name=r['name']+'-timing.json';f=p/name;originals.append({'file':name,'sha256':h(f.read_bytes())});timings[r['name']]=json.loads(f.read_text())
  arc=r['owner_archive'];assert h((p/arc['file']).read_bytes())==arc['sha256'];ids=[];events=0;maximum=0
  with tarfile.open(p/arc['file']) as z:
   assert len(z.getmembers())==48
   for m in arc['members']:
    raw=z.extractfile(m['file']).read();assert h(raw)==m['sha256'];o=json.loads(raw);assert not o['truncated'];ids.append(o['child']);events+=len(o['events']);maximum=max(maximum,len(o['events']))
  assert sorted(ids)==list(range(48))
  owners.append({'name':r['name'],'child_indices':sorted(ids),'events':events,'max_events_per_child':maximum,'truncated':0,'archive_sha256':arc['sha256']})
with (p/'timings.json.gz').open('wb') as f:
 with gzip.GzipFile(fileobj=f,mode='wb',filename='',mtime=0) as z:z.write(json.dumps(timings,separators=(',',':')).encode())
with tarfile.open(p/'original-process-reports.tar.gz','w:gz') as z:
 for m in originals:z.add(p/m['file'],arcname=m['file'])
(p/'original-report-sha256.json').write_text(json.dumps(originals,indent=2)+'\n')
(p/'owner-summary.json').write_text(json.dumps(owners,indent=2)+'\n')
(p/'archive-digests.json').write_text(json.dumps({f.name:h(f.read_bytes()) for f in p.glob('*.tar.gz')},indent=2)+'\n')
print('COLLECTED 18 processes; compact observations, all original reports and 96 owner logs retained')
