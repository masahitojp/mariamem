"""Deterministic reduction of old child distributions and new fixed evidence trial."""
import argparse,collections,hashlib,importlib.util,json,math,re,statistics,subprocess,tarfile
from pathlib import Path

def enc(d):return (json.dumps(d,indent=2,sort_keys=True)+'\n').encode()
def compact_enc(d):return (json.dumps(d,sort_keys=True,separators=(',',':'))+'\n').encode()
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def dist(xs):
 xs=sorted(xs);assert xs
 return dict(n=len(xs),p50=statistics.median(xs),p95=xs[int(.95*(len(xs)-1))],p99=xs[int(.99*(len(xs)-1))],max=max(xs),min=min(xs))
def phases(trace):
 assert trace and trace.get('guest'),'missing existing guest phase file'
 g=trace['guest'];assert g['clock']=='guest_monotonic'
 e={x['name']:x['offset_ns'] for x in g['events']};names=['open_begin','server_init_complete','routine_schema_complete']
 assert all(n in e for n in names) and e[names[0]]<=e[names[1]]<=e[names[2]],e
 return dict(server_init_ms=(e[names[1]]-e[names[0]])/1e6,post_init_to_routine_ms=(e[names[2]]-e[names[1]])/1e6,open_to_routine_ms=(e[names[2]]-e[names[0]])/1e6)
def distribution(rs):
 samples=[s for r in rs for s in r['samples']]
 metrics={k:dist([s[k] for s in samples]) for k in ['fork_ms','ready_ms','count_ms','total_ms']}
 counts={k:{str(v):sum(s[k]>v for s in samples) for v in [50,100,250,500]} for k in metrics}
 stage={k:dist([phases(s['startup_trace'])[k] for s in samples]) for k in ['server_init_ms','post_init_to_routine_ms','open_to_routine_ms']} if all(s.get('startup_trace') for s in samples) else None
 return dict(children=len(samples),metrics=metrics,threshold_exceedances=counts,guest_phases=stage,slow_children=[dict(run=s.get('run'),index=s['index'],fork_ms=s['fork_ms'],ready_ms=s['ready_ms'],count_ms=s['count_ms'],total_ms=s['total_ms'],guest_phases=phases(s['startup_trace']) if s.get('startup_trace') else None) for s in samples if s['count_ms']>100 or s['fork_ms']>250])
def legacy(archive):
 out={};groups=collections.defaultdict(list)
 with tarfile.open(archive) as t:
  hs=json.load(t.extractfile('SHA256SUMS.json'))
  for name in hs:
   if name.startswith('measure-v2/') and name.endswith('-p8.json'):
    raw=t.extractfile(name).read();assert hashlib.sha256(raw).hexdigest()==hs[name]['published_sha256']
    r=json.loads(raw);assert r['success'] and r['cleanup_complete']
    for sample in r['samples']:sample['run']=name
    groups[r['io_profile']['read']].append(r)
 for io,rs in groups.items():assert len(rs)==3;out[str(io)]=distribution(rs)
 return dict(raw_archive_sha256=sha(archive),source_commit='b3b3b46a8807482ad3f96725af86e031fe369b01',platform='macOS27.2 arm64 M1',order=[[1,4],[4,1],[1,4]],distributions=out)
def reduce(E):
 inp=json.loads((E/'inputs.json').read_text());records=json.loads((E/'measure-records.json').read_text());smoke=json.loads((E/'smoke-records.json').read_text())
 assert len(smoke)==2 and len(records)==46
 compact=dict(inputs=inp,runs={});original_hashes=set();effective=collections.defaultdict(set);offsets=set()
 for x in smoke+records:
  p=E/x['report'];r=json.loads(p.read_text());io=x['read_io'];n=x['children'];expected=dict(read=io,write=2,purge=1,native_aio=0)
  assert r['success'] and r['cleanup_complete'] and r['root_closed_before_forks'] and r['parallel']==x['parallel']
  assert len(r['samples'])==n and {s['index'] for s in r['samples']}==set(range(n)) and r['io_profile']==expected
  phases(r['startup_trace'])
  for s in r['samples']:assert s['oracle'] and s['cleanup_complete'] and s['io_profile']==expected;phases(s['startup_trace'])
  data=json.loads((E/x['data_identity']).read_text());assert data['read_io']==str(io) and data['changed_bytes']==int(io==4)
  assert data['original_byte']==49 and data['effective_byte']==ord(str(io)) and data['data_bytes']==6856219
  original_hashes.add(data['before_sha256']);effective[io].add(data['effective_sha256']);offsets.add(data['argv_byte_offset'])
  assert x['binary_sha256']==inp['binary_sha256']
  memory=json.loads((E/x['memory']).read_text());assert memory['baseline_rss_bytes']>0 and memory['sampled_peak_rss_bytes']>0
  if x['kind']=='memory':assert n==1 and x['parallel']==1 and len(memory['held_rss_bytes'])==3
  assert not (E/x['report'].replace('.json','.stderr.txt')).read_bytes()
  r['samples']=sorted(r['samples'],key=lambda s:s['index'])
  for sample in r['samples']:sample['run']=x['report']
  # Preserve all named phases, not unrelated internal bootstrap counters.
  for s in r['samples']:
   s['startup_trace']={k:s['startup_trace'][k] for k in ['operation','events','guest']}
   s['startup_trace']['guest']={k:s['startup_trace']['guest'][k] for k in ['version','clock','events']}
   s['startup_trace']['guest']['events']=[e for e in s['startup_trace']['guest']['events'] if e['name'] in ['open_begin','server_init_complete','routine_schema_complete']]
   s['startup_trace']['events']=[e for e in s['startup_trace']['events'] if e['name'] in ['begin','guest_ready','wire_listener_ready','end']]
  r['startup_trace']={k:r['startup_trace'][k] for k in ['operation','events','guest']};r['startup_trace']['guest']={k:r['startup_trace']['guest'][k] for k in ['version','clock','events']}
  r['startup_trace']['guest']['events']=[e for e in r['startup_trace']['guest']['events'] if e['name'] in ['open_begin','server_init_complete','routine_schema_complete']]
  r['startup_trace']['events']=[e for e in r['startup_trace']['events'] if e['name'] in ['begin','guest_ready','wire_listener_ready','end']]
  r['samples']=[{k:s[k] for k in ['run','index','oracle','cleanup_complete','io_profile','fork_ms','ready_ms','count_ms','total_ms','startup_trace']} for s in r['samples']]
  compact['runs'][x['report']]=dict(record=x,report=r,memory={k:memory[k] for k in ['baseline_rss_bytes','held_rss_bytes','held_rss_median_bytes','sampled_peak_rss_bytes']},data_identity=data,raw_report_sha256=sha(p))
 assert len(original_hashes)==1 and len(offsets)==1 and all(len(v)==1 for v in effective.values())
 assert effective[1]==original_hashes and effective[4]!=original_hashes
 return compact

def summarize(d):
 groups=collections.defaultdict(list);mem=collections.defaultdict(list);mem_pairs=collections.defaultdict(dict)
 for name,x in sorted(d['runs'].items()):
  rec=x['record'];io=rec['read_io']
  if rec['kind']=='phase':groups[io].append(x['report'])
  if rec['kind']=='memory':
   m=x['memory'];v=(m['held_rss_median_bytes']-m['baseline_rss_bytes'])/2**20;p=(m['sampled_peak_rss_bytes']-m['baseline_rss_bytes'])/2**20
   mem[io].append(dict(repetition=rec['repetition'],held_increment_mib=v,peak_increment_mib=p,baseline_rss_mib=m['baseline_rss_bytes']/2**20,held_rss_mib=m['held_rss_median_bytes']/2**20));mem_pairs[rec['repetition']][io]=v
 assert set(groups)=={1,4} and all(len(v)==3 for v in groups.values())
 assert set(mem)=={1,4} and all(len(v)==20 for v in mem.values()) and len(mem_pairs)==20
 out=dict(phase={},memory={})
 for io,rs in groups.items():
  out['phase'][str(io)]=distribution(rs)
  out['phase'][str(io)]['batch_ms']=[r['batch_ms'] for r in rs]
 for io,rs in mem.items():
  out['memory'][str(io)]={k:dist([r[k] for r in rs]) for k in ['held_increment_mib','peak_increment_mib','baseline_rss_mib','held_rss_mib']};out['memory'][str(io)]['trials']=rs
 out['memory']['paired_read4_minus_read1_increment_mib']=dist([v[4]-v[1] for _,v in sorted(mem_pairs.items())])
 return out

def data_source_check(d):
 commit=d['inputs']['products']['mariamem']['source_commit']
 raw=subprocess.check_output(['git','show',commit+':internal/generatedgo/code/generated.go'])
 pattern=rb'var wasm2goData_data_bin = \[\]byte\("([^"\n]*)"\)'
 hits=re.findall(pattern,raw);assert len(hits)==1
 original=bytes.fromhex(hits[0].replace(b'\\x',b'').decode());assert len(original)==6856219
 argv=b'--loose-innodb-read-io-threads=1\x00';assert original.count(argv)==1
 off=original.index(argv)+len(argv)-2;changed=bytearray(original);changed[off]=ord('4')
 assert sum(a!=b for a,b in zip(original,changed))==1
 before=hashlib.sha256(original).hexdigest();after=hashlib.sha256(changed).hexdigest()
 for x in d['runs'].values():
  identity=x['data_identity'];io=x['record']['read_io']
  assert identity['before_sha256']==before and identity['effective_sha256']==(before if io==1 else after)
  assert identity['argv_byte_offset']==off and identity['changed_bytes']==int(io==4)
 return dict(result='PASS',source_commit=commit,generated_go_sha256=hashlib.sha256(raw).hexdigest(),data_bytes=len(original),argv_byte_offset=off,before_sha256=before,after_sha256=after,changed_bytes=1,common_binary_sha256=d['inputs']['binary_sha256'],observations=len(d['runs']))

def main():
 p=argparse.ArgumentParser();p.add_argument('--evidence',type=Path);p.add_argument('--legacy-archive',type=Path);p.add_argument('--results',type=Path,required=True);p.add_argument('--check',action='store_true');p.add_argument('--verify-data-source',action='store_true');a=p.parse_args();R=a.results
 if a.evidence:
  d=reduce(a.evidence)
  if a.check:assert (R/'compact.json').read_bytes()==compact_enc(d)
  else:R.mkdir(parents=True,exist_ok=True);(R/'compact.json').write_bytes(compact_enc(d))
 else:d=json.loads((R/'compact.json').read_text())
 s=summarize(d)
 if a.check:assert (R/'summary.json').read_bytes()==enc(s)
 else:(R/'summary.json').write_bytes(enc(s))
 if a.legacy_archive:
  l=legacy(a.legacy_archive)
  if a.check:assert (R/'legacy-distribution.json').read_bytes()==enc(l)
  else:(R/'legacy-distribution.json').write_bytes(enc(l))
 if a.verify_data_source:
  identity=data_source_check(d)
  if a.check:assert (R/'data-source-check.json').read_bytes()==enc(identity)
  else:(R/'data-source-check.json').write_bytes(enc(identity))
 if a.check:
  for n,h in json.loads((R/'SHA256SUMS.json').read_text()).items():assert sha(R/n)==h,n
  print('CHECK PASS: fixed same-binary trial, phases, one-DB RSS and retained hashes'+('; raw reduction' if a.evidence else ''))
if __name__=='__main__':main()
