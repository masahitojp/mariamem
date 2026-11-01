"""Bounded configuration trace reduction; --check is read-only."""
import argparse,collections,hashlib,json
from pathlib import Path

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def enc(d):return (json.dumps(d,indent=2,sort_keys=True)+'\n').encode()
def summarize(d):
 result=[]
 for name,run in sorted(d['runs'].items()):
  groups=collections.defaultdict(list)
  for e in run['configuration_events']:
   if e['kind']=='concurrency_store':groups[e['instance']].append(e)
  seqs={str(k):[[e['a'],e['b']] for e in es] for k,es in groups.items()}
  assert seqs['1']==[[0,16]]
  assert all(v==[[0,16],[1,1],[0,16],[1,1],[0,16]] for k,v in seqs.items() if k!='1')
  assert len(seqs)==run['children']+1
  cpu=[e['a'] for e in run['configuration_events'] if e['kind']=='host_cpu_count'];assert cpu and set(cpu)=={8}
  conf=[e['b'] for e in run['configuration_events'] if e['kind']=='sysconf' and e['a']==84];assert conf and set(conf)=={8}
  hw=[e['b'] for e in run['configuration_events'] if e['kind']=='hardware_concurrency'];assert hw and set(hw)=={8}
  caller_sequences=[]
  for k,es in groups.items():
   if k==1:continue
   stacks=[run['stacks'][str(e['stack'])] for e in es]
   assert any('Fn16609' in f for f in stacks[0])
   assert all(any('Fn18568' in f for f in s) and not any('Fn16609' in f for f in s) for s in stacks[1:3])
   assert all(any('Fn17498' in f for f in s) for s in stacks[3:])
   caller_sequences.append(dict(instance=k,background_restriction_ms=(es[4]['ns']-es[3]['ns'])/1e6))
  result.append(dict(run=name,children=run['children'],cpu_count=8,default_concurrency=16,child_sequence=seqs,background_spans=caller_sequences,max_count_ms=max(run['count_ms']),slow_count_over_100ms=sum(x>100 for x in run['count_ms']),dropped=run['dropped']))
 return result

def main():
 p=argparse.ArgumentParser();p.add_argument('--evidence',type=Path);p.add_argument('--results',type=Path,required=True);p.add_argument('--check',action='store_true');a=p.parse_args();R=a.results
 if a.evidence:
  E=a.evidence;d={'inputs':json.loads((E/'inputs.json').read_text()),'runs':{}}
  records=json.loads((E/'pilot-records.json').read_text());assert len(records)==2
  for rec in records:
   path=E/rec['report'];r=json.loads(path.read_text());tpath=Path(str(path)+'.trace.json');t=json.loads(tpath.read_text())
   assert r['success'] and r['cleanup_complete'] and all(x['oracle'] and x['cleanup_complete'] for x in r['samples'])
   assert t['dropped']==0
   kinds={'host_cpu_count','sysconf','hardware_concurrency','concurrency_store','concurrency_inputs'}
   events=[e for e in t['events'] if e['kind'] in kinds]
   ids={e['stack'] for e in events if e['stack']}
   d['runs'][rec['report']]=dict(children=len(r['samples']),count_ms=[s['count_ms'] for s in r['samples']],report_sha256=sha(path),trace_sha256=sha(tpath),event_count=len(t['events']),dropped=t['dropped'],configuration_events=events,stacks={str(i):t['stacks'][i-1] for i in ids})
  blob=enc(d)
  if a.check:assert (R/'compact.json').read_bytes()==blob
  else:R.mkdir(parents=True,exist_ok=True);(R/'compact.json').write_bytes(blob)
 else:d=json.loads((R/'compact.json').read_text())
 blob=enc(summarize(d))
 if a.check:
  assert (R/'summary.json').read_bytes()==blob
  for name,digest in json.loads((R/'SHA256SUMS.json').read_text()).items():assert sha(R/name)==digest,name
  print('CHECK PASS: sequence/caller/CPU assertions, summary and checksums'+('; full raw reduction' if a.evidence else ''))
 else:(R/'summary.json').write_bytes(blob)
if __name__=='__main__':main()
