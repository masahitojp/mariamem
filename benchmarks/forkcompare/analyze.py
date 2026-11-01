"""Recalculate compact same-host fork statistics, without scratch/build metadata."""
import argparse,csv,hashlib,io,json,math,statistics
from pathlib import Path
CELLS=[('mariamem','tcp'),('pgmem','pipe'),('pgmem','tcp')]
STAGES=['fork_ms','connect_ms','select_ms','ready_ms','cleanup_ms']
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def collect(raw):
 out=[]
 for r in json.loads((raw/'records.json').read_text()):
  assert not r['negative'] and r['returncode']==0 and r['scratch_empty']
  d=json.loads((raw/r['report']).read_text());row=dict(r)
  row['raw_sha256']=digest(raw/r['report'])
  if r['kind']=='micro':
   assert d['success'] and d['cleanup_complete'] and d['root_closed_before_forks'] and len(d['samples'])==20
   assert {s['index'] for s in d['samples']}==set(range(20))
   assert all(s['oracle'] and s['cleanup_complete'] and not s.get('error') for s in d['samples'])
   row.update(samples=sorted(d['samples'],key=lambda s:s['index']),root_start_ms=d['root_start_ms'],snapshot_ms=d['snapshot_ms'],batch_ms=d['batch_ms'],server_version=d['server_version'])
  else:
   sums={}
   for s in d['spans']:
    k=s.get('stage',s.get('kind'));duration=s.get('duration_ms',s.get('end_ms',0)-s['start_ms'])
    assert s['start_ms']>=0 and duration>=0
    sums[k]=sums.get(k,0)+duration
   row.update(phase_sum_ms=sums,suite_ms=d.get('suite_ms',d.get('elapsed_ms')),server_version=d.get('server_version',d.get('meta',{}).get('server_version')))
  out.append(row)
 return out
def summarize(obs):
 assert len(obs)==72
 rows=[]
 for kind in ['micro','macro']:
  for p in [1,8]:
   for backend,route in CELLS:
    cell=[r for r in obs if r['kind']==kind and r['parallelism']==p and r['backend']==backend and r['route']==route]
    warmup=[r for r in cell if r['warmup']];runs=sorted([r for r in cell if not r['warmup']],key=lambda r:r['repetition'])
    assert len(warmup)==1 and len(runs)==5 and [r['repetition'] for r in runs]==list(range(5))
    for r in cell:
     assert r['returncode']==0 and r['scratch_empty'] and r['count']==(20 if kind=='micro' else 70)
     assert math.isfinite(r['wall_ms']) and r['wall_ms']>0
     if kind=='micro':
      assert len(r['samples'])==20 and {x['index'] for x in r['samples']}==set(range(20))
      assert all(x['oracle'] and x['cleanup_complete'] and not x.get('error') and all(math.isfinite(x[k]) and x[k]>=0 for k in STAGES) for x in r['samples'])
    vals=[r['wall_ms'] for r in runs]
    row=dict(kind=kind,parallelism=p,backend=backend,route=route,processes=5,median_wall_ms=statistics.median(vals),min_wall_ms=min(vals),max_wall_ms=max(vals))
    if kind=='micro':
     for stage in STAGES:
      medians=[]
      for r in runs:
       assert len(r['samples'])==20 and {s['index'] for s in r['samples']}==set(range(20))
       for s in r['samples']:
        assert s['oracle'] and s['cleanup_complete'] and not s.get('error')
        assert all(math.isfinite(s[k]) and s[k]>=0 for k in STAGES)
       medians.append(statistics.median(s[stage] for s in r['samples']))
      row[stage]=dict(median_of_process_medians=statistics.median(medians),min_process_median=min(medians),max_process_median=max(medians))
     row['median_batch_ms']=statistics.median(r['batch_ms'] for r in runs)
    rows.append(row)
 output=io.StringIO(newline='');keys=['kind','parallelism','backend','route','processes','median_wall_ms','min_wall_ms','max_wall_ms']+[s for s in STAGES]
 w=csv.DictWriter(output,fieldnames=keys,lineterminator='\n');w.writeheader()
 for r in rows:w.writerow({k:(r[k]['median_of_process_medians'] if k in STAGES and k in r else r.get(k,'')) for k in keys})
 return {'summary.json':json.dumps(dict(rows=rows,scope='Five fresh-process repetitions per cell; micro values are medians of 20-child process medians; ranges are not confidence intervals. Macro workloads differ across engines; only the pgmem transport variant changes one fixture line.'),indent=2)+'\n','summary.csv':output.getvalue()}
def hashes(root):
 for name,h in json.loads((root/'SHA256SUMS.json').read_text()).items():
  if digest(root/name)!=h:raise ValueError('checksum mismatch: '+name)
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--collect',type=Path);p.add_argument('--evidence-dir',type=Path,default=Path(__file__).resolve().parent);p.add_argument('--output-dir',type=Path);p.add_argument('--check',action='store_true');a=p.parse_args()
 if a.check and (a.collect or a.output_dir):p.error('--check is read-only')
 root=a.evidence_dir
 try:
  obs=collect(a.collect) if a.collect else json.loads((root/'observations.json').read_text());result=summarize(obs)
  if a.check:
   hashes(root)
   for n,s in result.items():
    if (root/n).read_bytes()!=s.encode():raise ValueError('recomputed '+n+' differs')
   print('PASS: read-only statistics and checksums')
  else:
   out=a.output_dir or root;out.mkdir(exist_ok=True,parents=True)
   if a.collect:(out/'observations.json').write_text(json.dumps(obs,separators=(',',':'))+'\n')
   for n,s in result.items():(out/n).write_text(s)
   print(result['summary.csv'])
 except (AssertionError,ValueError,KeyError,OSError,TypeError) as e:p.exit(1,'FAIL: '+str(e)+'\n')
if __name__=='__main__':main()
