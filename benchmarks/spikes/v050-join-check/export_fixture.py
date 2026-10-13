"""Add observation exports and remove automatic start; keep every body unchanged."""
import argparse,hashlib,json
from pathlib import Path

def u(n):
 out=[]
 while n>=128:out.append((n&127)|128);n>>=7
 return bytes(out+[n])
def read(raw,p):
 n=0;shift=0
 while True:
  b=raw[p];p+=1;n|=(b&127)<<shift
  if b<128:return n,p
  shift+=7;assert shift<=35

def main():
 p=argparse.ArgumentParser();p.add_argument('--wasm',type=Path,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 raw=a.wasm.read_bytes();assert hashlib.sha256(raw).hexdigest()=='7c7b6ce5168a1a0d98019751b4c36c25f2e9948dbae0124ec3f434efb0b8642c'
 data=bytearray(raw[:8]);cursor=8;kept=[]
 entries=[('auditInit',0,67),('auditMalloc',0,152),('auditJoin',0,221),('auditUnlock',0,217),('auditStack',3,0),('auditTLS',3,1)]
 while cursor<len(raw):
  kind=raw[cursor];size,pos=read(raw,cursor+1);end=pos+size;payload=raw[pos:end]
  if kind==7:
   count,q=read(payload,0);extra=b''.join(u(len(n))+n.encode()+bytes([k])+u(i) for n,k,i in entries);payload=u(count+len(entries))+payload[q:]+extra
  if kind!=8:data.extend(bytes([kind])+u(len(payload))+payload)
  if kind not in (7,8):kept.append({'section':kind,'sha256':hashlib.sha256(raw[pos:end]).hexdigest()})
  cursor=end
 a.output.write_bytes(data)
 a.output.with_suffix('.json').write_text(json.dumps({'original_sha256':hashlib.sha256(raw).hexdigest(),'fixture_sha256':hashlib.sha256(data).hexdigest(),'change':'exports plus removal of automatic start only; all function bodies unchanged','unchanged_sections':kept},indent=2)+'\n')
if __name__=='__main__':main()
