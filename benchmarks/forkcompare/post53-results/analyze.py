"""Reduce raw reports; --check works read-only after scratch cleanup."""
import argparse,copy,csv,hashlib,io,json,math,statistics
from pathlib import Path

def dump(d):return json.dumps(d,indent=2,sort_keys=True)+'\n'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def collect(e):
 read=lambda p:json.loads((e/p).read_text())
 runs=[]
 for rec in read('measure-records.json'):
  if rec['warmup']:continue
  d=read(rec['report']);m=read(rec['memory']);samples=d.pop('samples')
  assert len(samples)==48 and {s['index'] for s in samples}==set(range(48))
  assert all(s['oracle'] and s['cleanup_complete'] and not s.get('error') for s in samples)
  assert all(s['total_ms']>=s['ready_ms'] and abs(s['total_ms']-(s['ready_ms']+s['sql_ms']+s['cleanup_ms']))<2 for s in samples)
  phases={k:dict(median=statistics.median(s[k] for s in samples),maximum=max(s[k] for s in samples),sum=math.fsum(s[k] for s in samples),over_100ms=sum(s[k]>100 for s in samples)) for k in ['fork_ms','connect_ms','select_ms','ready_ms','sql_ms','cleanup_ms','total_ms']}
  memory={k:v for k,v in m.items() if k!='samples'}
  memory['sample_count']=len(m['samples'])
  memory['sample_max_gap_ms']=max(b['offset_ms']-a['offset_ms'] for a,b in zip(m['samples'],m['samples'][1:]))
  runs.append(dict(record=rec,result=d,phases=phases,memory=memory,raw_sha256={p:sha(e/p) for p in [rec['report'],rec['memory']]}))
 return dict(inputs=read('inputs.json'),pilot=read('pilot.json'),completion=read('completion.json'),runs=runs)

def summarize(d):
 assert d['pilot']['result']=='PASS' and d['completion']['result']=='PASS'
 assert len(d['runs'])==12
 assert {(r['record']['backend'],r['record']['parallel'],r['record']['repetition']) for r in d['runs']}=={(b,p,i) for b in ['mariamem','pgmem'] for p in [4,8] for i in range(3)}
 rows=[]
 for r in d['runs']:
  t=r['result'];m=r['memory'];rec=r['record'];assert t['success'] and t['cleanup_complete'] and t['root_closed_before_forks'] and rec['returncode']==0
  assert t['count']==48 and t['route']=='tcp' and t['gomaxprocs']==8 and t['parallel']==rec['parallel'] and m['observed_peak_active_children']==rec['parallel']
  cpu=t['cpu_user_ms']+t['cpu_system_ms'];assert cpu>0 and t['batch_ms']>0
  row=dict(backend=rec['backend'],parallel=rec['parallel'],repetition=rec['repetition'],wall_ms=t['batch_ms'],cpu_ms=cpu,cpu_per_child_ms=cpu/48,effective_cores=cpu/t['batch_ms'],system_cpu_ms=t['cpu_system_ms'],baseline_rss_mib=m['baseline_rss_bytes']/2**20,peak_rss_mib=m['sampled_peak_rss_bytes']/2**20,rss_growth_mib=(m['sampled_peak_rss_bytes']-m['baseline_rss_bytes'])/2**20,minor_faults=t['minor_faults'],major_faults=t['major_faults'],involuntary_switches=t['involuntary_switches'])
  row.update({k:r['phases'][k]['median'] for k in sorted(r['phases'])});rows.append(row)
 cells=[]
 for b in ['mariamem','pgmem']:
  for p in [4,8]:
   group=[r for r in rows if r['backend']==b and r['parallel']==p]
   cell=dict(backend=b,parallel=p)
   for k in rows[0]:
    if k not in ['backend','parallel','repetition']:
     vals=[r[k] for r in group];cell[k]=dict(median=statistics.median(vals),min=min(vals),max=max(vals))
   cells.append(cell)
 pairs=[]
 for b in ['mariamem','pgmem']:
  for i in range(3):
   a=next(r for r in rows if (r['backend'],r['parallel'],r['repetition'])==(b,4,i));z=next(r for r in rows if (r['backend'],r['parallel'],r['repetition'])==(b,8,i))
   pairs.append(dict(backend=b,repetition=i,wall_ratio=z['wall_ms']/a['wall_ms'],cpu_ratio=z['cpu_ms']/a['cpu_ms'],peak_rss_ratio=z['peak_rss_mib']/a['peak_rss_mib']))
 return dict(cells=cells,pairs=pairs,runs=rows,limits='Three fresh processes per cell on one M1; RSS sampled at 20 ms, not allocations or exact peak; CPU is process-wide batch CPU, not per-phase CPU.')

def main():
 p=argparse.ArgumentParser();p.add_argument('--evidence',type=Path);p.add_argument('--results',type=Path,required=True);p.add_argument('--check',action='store_true');a=p.parse_args()
 if a.check:d=json.loads((a.results/'compact.json').read_text())
 else:d=collect(a.evidence);a.results.mkdir(parents=True,exist_ok=True);(a.results/'compact.json').write_text(dump(d))
 s=summarize(d);buf=io.StringIO();writer=csv.DictWriter(buf,fieldnames=list(s['runs'][0]),lineterminator="\n");writer.writeheader();writer.writerows(s['runs'])
 outputs={'summary.json':dump(s),'summary.csv':buf.getvalue()}
 if a.check:
  for n,v in outputs.items():assert (a.results/n).read_bytes()==v.encode(),n
  hashes=json.loads((a.results/'SHA256SUMS.json').read_text());assert all(sha(a.results/n)==h for n,h in hashes.items())
  bad=copy.deepcopy(d);bad['runs'][0]['result']['success']=False
  try:summarize(bad)
  except AssertionError:pass
  else:raise AssertionError('failed run accepted')
  print('CHECK PASS (read-only regeneration, checksums, failed-run rejection)')
 else:
  for n,v in outputs.items():(a.results/n).write_bytes(v.encode())
  (a.results/'SHA256SUMS.json').write_text(dump({n:sha(a.results/n) for n in ['compact.json',*outputs]}))
  print(dump(s['cells']))
if __name__=='__main__':main()
