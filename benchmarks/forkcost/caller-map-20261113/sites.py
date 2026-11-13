from pathlib import Path
import gzip,collections,json
E=Path(__file__).resolve().parent;P=E.parents[1]/'fork-current-audit/evidence/runs'
def vi(b,i):
 x=s=0
 while True:
  a=b[i];i+=1;x|=(a&127)<<s
  if a<128:return x,i
  s+=7
def fields(b):
 d=collections.defaultdict(list);i=0
 while i<len(b):
  key,i=vi(b,i);w=key&7
  if w==0:x,i=vi(b,i)
  elif w==2:n,i=vi(b,i);x=b[i:i+n];i+=n
  elif w in (1,5):n=8 if w==1 else 4;x=b[i:i+n];i+=n
  else:raise ValueError(w)
  d[key>>3].append(x)
 return d
def numbers(values):
 for b in values:
  if isinstance(b,int):yield b;continue
  i=0
  while i<len(b):x,i=vi(b,i);yield x
out={}
for p in (1,8):
 counts=collections.Counter();total=0;memclr=0
 for f in sorted(P.glob(f'profile-p{p}.json-wave*.pprof')):
  d=fields(gzip.decompress(f.read_bytes()));ss=[x.decode() for x in d[6]];fs={}
  for b in d[5]:
   q=fields(b);fs[q[1][0]]=(ss[q[2][0]],ss[q[4][0]])
  locs={}
  for b in d[4]:
   q=fields(b);frames=[]
   for line in q[4]:
    l=fields(line);name,file=fs[l[1][0]];frames.append((name,file,l[2][0] if l[2] else 0))
   locs[q[1][0]]=frames
  for b in d[2]:
   q=fields(b);values=list(numbers(q[2]));ns=values[1];total+=ns;stack=[frame for lid in numbers(q[1]) for frame in locs[lid]]
   if not any(name=='runtime.memclrNoHeapPointers' for name,_,_ in stack):continue
   memclr+=ns;calls=[(name,file,line) for name,file,line in stack if 'MemoryFill' in name or '/p' in name and '.Fn' in name]
   key='\n'.join(f'{name} {file}:{line}:'.replace(str(E.parents[1]/'fork-current-audit'),'<workspace>') for name,file,line in calls)
   counts[key]+=ns
 out[str(p)]={'total_cpu_ns':total,'memclr_cpu_ns':memclr,'memclr_sites':[{'stack':k,'cpu_ns':v} for k,v in counts.most_common()]}
 assert memclr=={1:260000000,8:350000000}[p],memclr
(E/'sites.json').write_text(json.dumps(out,indent=2)+'\n');print('PASS direct protobuf sample totals: P1 2.47s/0.26s memclr; P8 2.22s/0.35s memclr')
