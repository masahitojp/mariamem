"""Recompute the finite product comparison from retained records, read-only by default."""
from pathlib import Path
import argparse,hashlib,json,math,statistics,tarfile

def reduce(root):
 rows=json.loads((root/'measurement-records.json').read_text());plan=json.loads((root/'measurement-plan.json').read_text())
 if (root/'processes.tar.gz').exists():
  members=json.loads((root/'processes-sha256.json').read_text())
  with tarfile.open(root/'processes.tar.gz') as archive:
   assert set(archive.getnames())==set(members)
   originals={n:archive.extractfile(n).read() for n in archive.getnames()}
  assert all(hashlib.sha256(b).hexdigest()==members[n] for n,b in originals.items())
  for row in rows:
   raw=originals[row['name']+'.json'];assert hashlib.sha256(raw).hexdigest()==row['sha256'];assert json.loads(raw)==row['data']
 assert len(rows)==plan['processes']==44 and len({r['name'] for r in rows})==44
 assert sum(r['data']['Count'] for r in rows)==plan['expected_children']==1572
 assert {k:sum(r['kind']==k for r in rows) for k in ['pilot','negative','warmup','primary']}=={'pilot':8,'negative':4,'warmup':8,'primary':24}
 for row in rows:
  d=row['data'];assert d['Route']==row['route'] and d['Parallel']==row['parallel']
  assert len(d['Samples'])==d['Count'] and [v['index'] for v in d['Samples']]==list(range(d['Count']))
  assert all(d['Cleanup'][k]==0 for k in ['active_mappings','active_reserved_bytes','active_rw_bytes','release_failures','grow_failures'])
  if row['kind']=='negative':assert row['exit_code']==1 and not d['Success'] and 'pristine oracle' in d['error']
  else:assert row['exit_code']==0 and d['Success'] and all(not v.get('error') for v in d['Samples'])
  for sample in d['Samples']:
   assert all(math.isfinite(sample[k]) and sample[k]>=0 for k in ['Startup','Seed','SQL','Cleanup','Total'])
  assert d['Suite']>=d['Setup']+d['Batch'] and d['SuiteCPU']>=d['BatchCPU']>=0
  # Each original process JSON remains included in the archived record set.
  original=root/(row['name']+'.json')
  if original.exists():
   assert hashlib.sha256(original.read_bytes()).hexdigest()==row['sha256']
   assert json.loads(original.read_text())==d
 summary=[]
 for p in [1,4]:
  for route in ['fork','fresh']:
   cohort=[r for r in rows if r['kind']=='primary' and r['route']==route and r['parallel']==p]
   assert [(r['rep'],r['arm']) for r in cohort]==[(i,arm) for i,arms in enumerate(plan['orders']) for arm in arms]
   pairs=[]
   for rep in range(3):
    get=lambda arm:next(v['data'] for v in cohort if v['arm']==arm and v['rep']==rep)
    a,b=get('baseline'),get('candidate');metric=lambda d:{**{k:d[k] for k in ['Batch','BatchCPU','Suite','SuiteCPU']},**{k+'P50':statistics.median(v[k] for v in d['Samples']) for k in ['Startup','Cleanup','SQL','Seed']}}
    av,bv=metric(a),metric(b);pairs.append({'rep':rep,'baseline':av,'candidate':bv,'difference':{k:bv[k]-av[k] for k in av}})
   summary.append({'parallel':p,'route':route,'pairs':pairs,'median_paired_difference':{k:statistics.median(v['difference'][k] for v in pairs) for k in pairs[0]['difference']}})
 return summary
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('directory',type=Path);args=p.parse_args();out=reduce(args.directory);assert out==json.loads((args.directory/'measurement-summary.json').read_text());print('PASS retained-only comparison: 44 processes /1572 children, all pairs and cleanup retained')
