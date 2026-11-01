"""Read-only reproducibility check and compact reduction for the fixed IO 1/4 trial."""
import argparse,collections,hashlib,json,statistics
from pathlib import Path

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def encode(d):return (json.dumps(d,indent=2,sort_keys=True)+'\n').encode()
def validate_report(r,read_io,count):
 assert r['success'] and r['cleanup_complete'] and r['root_closed_before_forks']
 assert r['parallel']==8 and r['count']==count and r['gomaxprocs']==8
 expected=dict(read=read_io,write=2,purge=1,native_aio=0)
 assert r['io_profile']==expected
 assert len(r['samples'])==count and {x['index'] for x in r['samples']}==set(range(count))
 assert all(x['oracle'] and x['cleanup_complete'] and x['io_profile']==expected for x in r['samples'])
def summary(d):
 groups=collections.defaultdict(list)
 for name,r in sorted(d['runs'].items()):
  io=r['io_profile']['read'];validate_report(r,io,48);groups[io].append(r)
 assert set(groups)=={1,4} and all(len(v)==3 for v in groups.values())
 out={}
 for io,rs in groups.items():
  samples=[s for r in rs for s in r['samples']];counts=sorted(s['count_ms'] for s in samples)
  metrics={}
  for key in ['batch_ms','cpu_ms','sampled_peak_rss_bytes','baseline_rss_bytes','lifetime_max_rss_bytes']:
   values=[r[key] for r in rs];metrics[key]=dict(values=values,median=statistics.median(values))
  out[str(io)]=dict(processes=len(rs),children=len(samples),metrics=metrics,count_ms=dict(median=statistics.median(counts),p95=counts[int(.95*(len(counts)-1))],max=max(counts)),slow_count_over_100ms=sum(x>100 for x in counts),slow_samples=[dict(run=name,index=s['index'],count_ms=s['count_ms']) for name,r in sorted(d['runs'].items()) if r['io_profile']['read']==io for s in r['samples'] if s['count_ms']>100])
 return out

def reduce(E):
 inputs=json.loads((E/'inputs.json').read_text());out=dict(inputs=inputs,pilots={},runs={})
 for phase in ['pilot','measure']:
  records=json.loads((E/(phase+'-records.json')).read_text());assert len(records)==(2 if phase=='pilot' else 6)
  for record in records:
   name=record['report'];p=E/name;r=json.loads(p.read_text());io=int(record['backend'][2]);validate_report(r,io,record['count'])
   assert not (E/name.replace('.json','.stderr.txt')).read_bytes()
   if phase=='pilot':
    tp=Path(str(p)+'.trace.json');t=json.loads(tp.read_text());assert t['dropped']==0
    events=[e for e in t['events'] if e['kind']=='concurrency_store'];groups=collections.defaultdict(list)
    for e in events:groups[e['instance']].append([e['a'],e['b']])
    assert groups[1]==[[0,16]] and len(groups)==9
    assert all(v==[[0,16],[io,io],[0,16],[io,io],[0,16]] for k,v in groups.items() if k!=1)
    out['pilots'][name]=dict(report_sha256=digest(p),trace_sha256=digest(tp),event_count=len(t['events']),dropped=t['dropped'],configuration_events=events,stacks={str(i):t['stacks'][i-1] for i in sorted({e['stack'] for e in events if e['stack']})},io_profile=r['io_profile'],sequence={str(k):v for k,v in groups.items()})
   else:
    assert json.loads(Path(str(p)+'.trace.json').read_text())=={}
    m=json.loads((E/record['memory']).read_text());assert m['observed_peak_active_children']==8
    r['samples']=[{k:s[k] for k in ['index','oracle','cleanup_complete','io_profile','count_ms','fork_ms','total_ms']} for s in sorted(r['samples'],key=lambda s:s['index'])]
    r.update(cpu_ms=r['cpu_user_ms']+r['cpu_system_ms'],sampled_peak_rss_bytes=m['sampled_peak_rss_bytes'],baseline_rss_bytes=m['baseline_rss_bytes'],report_sha256=digest(p),memory_sha256=digest(E/record['memory']))
    out['runs'][name]=r
 return out

def main():
 p=argparse.ArgumentParser();p.add_argument('--evidence',type=Path);p.add_argument('--results',type=Path,required=True);p.add_argument('--check',action='store_true');a=p.parse_args();R=a.results
 if a.evidence:
  d=reduce(a.evidence)
  if a.check:assert (R/'compact.json').read_bytes()==encode(d)
  else:R.mkdir(parents=True,exist_ok=True);(R/'compact.json').write_bytes(encode(d))
 else:d=json.loads((R/'compact.json').read_text())
 s=summary(d)
 if a.check:
  assert (R/'summary.json').read_bytes()==encode(s)
  for n,h in json.loads((R/'SHA256SUMS.json').read_text()).items():assert digest(R/n)==h,n
  print('CHECK PASS: fixed trial/profile/oracles, summary, checksums'+('; raw reduction' if a.evidence else ''))
 else:(R/'summary.json').write_bytes(encode(s))
if __name__=='__main__':main()
