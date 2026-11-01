"""Publish path-normalized evidence; preserve original/published hashes.
Only top-level Profile.string_table (protobuf field 6) is modified in pprof.
All other field bytes are retained exactly; samples and stack IDs are untouched.
"""
import gzip,hashlib,io,json,tarfile
from pathlib import Path

def vint(b,i):
 n=0;shift=0;start=i
 while True:
  assert i<len(b) and shift<70
  v=b[i];i+=1;n|=(v&127)<<shift
  if not v&128:return n,i
  shift+=7

def enc(n):
 b=bytearray()
 while n>=128:b.append((n&127)|128);n>>=7
 b.append(n);return bytes(b)

def normalize_profile(data,root):
 source=gzip.decompress(data);out=bytearray();i=0
 while i<len(source):
  start=i;tag,i=vint(source,i);field,wire=tag>>3,tag&7
  if wire==0:_,i=vint(source,i)
  elif wire==1:i+=8
  elif wire==5:i+=4
  elif wire==2:
   n,body=vint(source,i);i=body+n;assert i<=len(source)
   if field==6:
    text=source[body:i].replace(root,b'<WORKSPACE>');out+=enc(tag)+enc(len(text))+text;continue
  else:raise ValueError(wire)
  out+=source[start:i]
 assert root not in out
 return gzip.compress(bytes(out),mtime=0)

def main():
 import argparse
 p=argparse.ArgumentParser();p.add_argument('evidence',type=Path);a=p.parse_args();e=a.evidence.resolve();root=str(e.parent).encode()
 names=['inputs.json','pilot.json','completion.json','pilot-records.json','measure-records.json','run.py','build-profile.txt','build-diagnostic.txt','build-pprof.txt']+[str(p.relative_to(e)) for directory in ['pilot','measure'] for p in sorted((e/directory).rglob('*')) if p.is_file()]
 receipts={};members={}
 for n in names:
  original=(e/n).read_bytes()
  if n.endswith('.pprof'):published=normalize_profile(original,root)
  else:published=original.replace(root,b'<WORKSPACE>')
  receipts[n]={'original_sha256':hashlib.sha256(original).hexdigest(),'published_sha256':hashlib.sha256(published).hexdigest()};members[n]=published
 members['normalization.json']=(json.dumps(receipts,indent=2)+'\n').encode()
 members['SHA256SUMS.json']=(json.dumps({n:hashlib.sha256(b).hexdigest() for n,b in members.items()},indent=2)+'\n').encode()
 raw=io.BytesIO()
 with tarfile.open(fileobj=raw,mode='w') as t:
  for name,data in sorted(members.items()):
   i=tarfile.TarInfo(name);i.size=len(data);i.mode=0o644;t.addfile(i,io.BytesIO(data))
 archive=gzip.compress(raw.getvalue(),mtime=0);(e/'raw.tar.gz').write_bytes(archive)
 # Export normalized merged profiles for verification with the stock Go parser.
 out=e/'normalized';out.mkdir(exist_ok=True)
 for n,b in members.items():
  if n.startswith('measure/') and n.endswith('.pprof') and '/0' not in n[len('measure/'):]:
   (out/Path(n).name).write_bytes(b)
 print(json.dumps({'members':len(members),'bytes':len(archive),'sha256':hashlib.sha256(archive).hexdigest()}))
if __name__=='__main__':main()
