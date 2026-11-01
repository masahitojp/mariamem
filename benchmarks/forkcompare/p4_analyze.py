"""Read-only P4 variability analysis. A process, not each child, is the repeat unit."""
import argparse,csv,hashlib,importlib.util,io,json,math,statistics
from pathlib import Path
CELLS=[('mariamem','tcp'),('pgmem','pipe'),('pgmem','tcp')]
STAGES=['fork_ms','connect_ms','select_ms','ready_ms','cleanup_ms']
def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load_base():
 p=Path(__file__).resolve().with_name('analyze.py')
 if not p.exists():
  # Experiment evidence/ holds a copy of the maintained base analysis.
  raise ValueError('base analyze.py is required alongside p4_analyze.py')
 spec=importlib.util.spec_from_file_location('forkcompare_base',p);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m,p
def stats(vals):
 assert len(vals)==10 and all(math.isfinite(v) and v>0 for v in vals),'expected10 finite positive durations'
 avg=statistics.mean(vals);sd=statistics.stdev(vals)
 return dict(values_ms=vals,median_ms=round(statistics.median(vals),6),min_ms=round(min(vals),6),max_ms=round(max(vals),6),mean_ms=round(avg,6),sample_sd_ms=round(sd,6),cv_percent=round(sd/avg*100,6))
def summarize(obs):
 assert len(obs)==66,'expected66 P4 observations'
 expected={(kind,b,r) for kind in ['micro','macro'] for b,r in CELLS}
 assert {(x['kind'],x['backend'],x['route']) for x in obs}==expected,'unexpected or missing P4 cell'
 rows=[]
 for kind in ['micro','macro']:
  for backend,route in CELLS:
   cell=[r for r in obs if r['kind']==kind and r['backend']==backend and r['route']==route]
   warm=[r for r in cell if r['warmup']];runs=sorted([r for r in cell if not r['warmup']],key=lambda r:r['repetition'])
   assert len(cell)==11 and len(warm)==1 and warm[0]['repetition']==-1 and [r['repetition'] for r in runs]==list(range(10))
   for r in cell:
    assert r['parallelism']==4 and not r['negative'] and r['returncode']==0 and r['scratch_empty']
    assert r['count']==(20 if kind=='micro' else 70)
    if kind=='micro':
     assert len(r['samples'])==20 and {s['index'] for s in r['samples']}==set(range(20))
     assert all(s['oracle'] and s['cleanup_complete'] and not s.get('error') and all(math.isfinite(s[k]) and s[k]>=0 for k in STAGES) for s in r['samples'])
   row=dict(kind=kind,backend=backend,route=route,parallelism=4,processes=10,wall=stats([r['wall_ms'] for r in runs]))
   if kind=='micro':
    row['stages']={stage:stats([statistics.median(s[stage] for s in r['samples']) for r in runs]) for stage in STAGES}
   rows.append(row)
 result=dict(rows=rows,scope='Separate P4 cohort;10 fresh processes per cell, one excluded warmup. CV uses sample SD/mean. Micro stages use one20-child median per process. Finite samples do not prove absence of rare tails.')
 out=io.StringIO(newline='');keys=['kind','backend','route','parallelism','processes','median_ms','min_ms','max_ms','mean_ms','sample_sd_ms','cv_percent']
 w=csv.DictWriter(out,fieldnames=keys,lineterminator='\n');w.writeheader()
 for r in rows:w.writerow({k:r[k] if k in r else r['wall'][k] for k in keys})
 return {'summary.json':json.dumps(result,indent=2)+'\n','summary.csv':out.getvalue()}
def main():
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--collect',type=Path);p.add_argument('--evidence-dir',type=Path,default=Path(__file__).resolve().parent/'p4-results');p.add_argument('--output-dir',type=Path);p.add_argument('--check',action='store_true');a=p.parse_args()
 if a.check and (a.collect or a.output_dir):p.error('--check cannot write output')
 try:
  base,bp=load_base();root=a.evidence_dir
  obs=base.collect(a.collect) if a.collect else json.loads((root/'observations.json').read_text());results=summarize(obs)
  if a.check:
   archive=json.loads((root/'archive.json').read_text())
   if digest(Path(__file__).resolve())!=archive['analysis_sha256'] or digest(bp)!=archive['base_analysis_sha256']:raise ValueError('analysis identity mismatch')
   base.hashes(root)
   for n,s in results.items():
    if (root/n).read_bytes()!=s.encode():raise ValueError('recomputed '+n+' differs')
   print('PASS: read-only P4 summaries and hashes')
  else:
   target=a.output_dir or root;target.mkdir(parents=True,exist_ok=True)
   if a.collect:(target/'observations.json').write_text(json.dumps(obs,separators=(',',':'))+'\n')
   for n,s in results.items():(target/n).write_text(s)
   print(results['summary.csv'])
 except (AssertionError,KeyError,ValueError,OSError,TypeError) as e:p.exit(1,'FAIL: '+str(e)+'\n')
if __name__=='__main__':main()
