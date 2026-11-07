from pathlib import Path
import json,gzip,hashlib,tarfile
p=Path(__file__).parent;h=lambda b:hashlib.sha256(b).hexdigest();rs=json.loads((p/'records.json').read_text());assert len(rs)==32
obs={r['report']:json.loads((p/r['report']).read_text()) for r in rs};timings={};owners=[];originals=[]
for r in rs:
 for n in [r['report'],r['name']+'.log']:originals.append({'file':n,'sha256':h((p/n).read_bytes())})
 if r['observer']=='on':
  n=r['name']+'-timing.json';timings[r['name']]=json.loads((p/n).read_text());originals.append({'file':n,'sha256':h((p/n).read_bytes())});a=r['owner_archive'];assert h((p/a['file']).read_bytes())==a['sha256']
  ids=[];events=0;maximum=0
  with tarfile.open(p/a['file']) as z:
   assert len(z.getmembers())==r['count']
   for m in a['members']:
    raw=z.extractfile(m['file']).read();assert h(raw)==m['sha256'];v=json.loads(raw);assert not v['truncated'];ids.append(v['child']);events+=len(v['events']);maximum=max(maximum,len(v['events']))
  assert sorted(ids)==list(range(r['count']));owners.append(dict(name=r['name'],child_indices=sorted(ids),events=events,max_events_per_child=maximum,truncated=0,archive_sha256=a['sha256']))
timing_index={name:{f:{'operation':v['operation'],'epoch_ns':v['epoch_ns'],'canonical_sha256':h(json.dumps(v,sort_keys=True,separators=(',',':')).encode())} for f,v in rs.items()} for name,rs in timings.items()}
for n,obj in [('observations.json.gz',obs),('timing-index.json.gz',timing_index)]:
 with (p/n).open('wb') as f:
  with gzip.GzipFile(fileobj=f,filename='',mtime=0,mode='wb') as z:z.write(json.dumps(obj,separators=(',',':')).encode())
with tarfile.open(p/'original-process-reports.tar.gz','w:gz') as z:
 for m in originals:z.add(p/m['file'],arcname=m['file'])
for n,obj in [('owner-summary.json',owners),('original-report-sha256.json',originals),('archive-digests.json',{f.name:h(f.read_bytes()) for f in p.glob('*.tar.gz')})]:(p/n).write_text(json.dumps(obj,indent=2)+'\n')
print('COLLECTED 32 processes; raw reports and all observer-on owner logs archived')
