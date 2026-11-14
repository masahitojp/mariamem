from pathlib import Path
import re,json,collections,gzip
E=Path(__file__).resolve().parent;out={}
for label in ['baseline','direct','shared']:
 p=E/(label+'-raw.txt');text=p.read_text() if p.exists() else gzip.decompress(p.with_suffix('.txt.gz').read_bytes()).decode();samples,locpart=text.split('Locations\n',1);locpart=locpart.split('Mappings',1)[0];locs={};current=None
 for line in locpart.splitlines():
  m=re.match(r'\s*(\d+): 0x[0-9a-f]+ M=\d+ (.*)',line)
  if m:current=int(m[1]);locs[current]=[m[2].split()[0]]
  elif current is not None and line.strip():locs[current].append(line.strip().split()[0])
 totals=collections.Counter();callers=collections.Counter();physical=collections.Counter();flat=collections.Counter()
 for line in samples.splitlines():
  m=re.match(r'\s*(\d+)\s+(\d+): ([\d ]+)$',line)
  if not m:continue
  ns=int(m[2]);ids=list(map(int,m[3].split()));frames=[f for i in ids for f in locs[i]];totals['total_ns']+=ns;flat[locs[ids[0]][-1]]+=ns
  if any(f.endswith('base.MemoryEA')for f in frames):
   totals['ea_cumulative_ns']+=ns
   i=next(i for i,f in enumerate(frames)if f.endswith('base.MemoryEA'))
   callers[frames[i+1]if i+1<len(frames)else '<root>']+=ns
   physical[locs[ids[0]][-1]]+=ns
   if locs[ids[0]][-1].endswith('base.MemoryEA'):totals['ea_physical_flat_ns']+=ns
  if any('gopanic' in f for f in frames):totals['panic_stack_ns']+=ns
 out[label]={'totals':dict(totals),'ea_callers_ns':dict(callers.most_common()),'ea_leaf_physical_ns':dict(physical.most_common()),'physical_flat_ns':dict(flat.most_common())}
(E/'profile-summary.json').write_text(json.dumps(out,indent=2))
for label,d in out.items():
 print(label,d['totals']);print([(k.rsplit('/',1)[-1],v/1e9)for k,v in list(d['ea_callers_ns'].items())[:8]])
 for fn in ['Fn13460','Fn15594']:print(fn,sum(v for k,v in d['ea_callers_ns'].items()if k.endswith('.'+fn))/1e9)
