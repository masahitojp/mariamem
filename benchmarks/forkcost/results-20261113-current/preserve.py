from pathlib import Path
import json,shutil,hashlib,gzip,base64
E=Path(__file__).resolve().parent;W=E.parent;D=W/'worktree/benchmarks/forkcost/results-20261113-current';D.mkdir(parents=True,exist_ok=True)
for n in ['analyze.py','measure.py','build.py','overlay.py','profile.py','plan.json','source-identity.json','tree-identity.json','binary-hashes.json','overlay-hashes.json','summary.json','children.csv','buildinfo.txt']:
 text=(E/n).read_text().replace(str(W),'<workspace>');(D/n).write_text(text)
shutil.copytree(W/'temp/harness',D/'harness',dirs_exist_ok=True)
(D/'runs').mkdir(exist_ok=True)
for f in (E/'runs').glob('*.json'):(D/'runs'/f.name).write_text(f.read_text().replace(str(W),'<workspace>'))
for f in E.glob('profile-*.txt'):shutil.copy2(f,D/f.name)
def varint(b,i):
 v=0;s=0
 while True:
  c=b[i];i+=1;v|=(c&127)<<s
  if c<128:return v,i
  s+=7
def enc(v):
 b=bytearray()
 while v>127:b.append((v&127)|128);v>>=7
 b.append(v);return bytes(b)
def normalize(data):
 b=gzip.decompress(data);out=bytearray();i=0
 while i<len(b):
  start=i;key,i=varint(b,i);wire=key&7
  if wire==2:
   size,i=varint(b,i);value=b[i:i+size];i+=size
   if key>>3==6:
    value=value.replace(str(W).encode(),b'<workspace>').replace(b'/Users/masahito/',b'<home>/')
    out+=enc(key)+enc(len(value))+value
   else:out+=b[start:i]
  elif wire==0:_,i=varint(b,i);out+=b[start:i]
  elif wire in (1,5):i+=8 if wire==1 else 4;out+=b[start:i]
  else:raise ValueError(wire)
 return gzip.compress(bytes(out),mtime=0)
for p in (1,8):
 for f in sorted((E/'runs').glob(f'profile-p{p}.json-wave*.pprof')):(D/'runs'/(f.name+'.b64')).write_bytes(base64.b64encode(normalize(f.read_bytes()))+b'\n')
(D/'preserve.py').write_text(Path(__file__).read_text())
print(D)
