"""Read-only byte comparison; never edits or normalizes an artifact."""
import hashlib,json,sys
from pathlib import Path

def digest(b):return hashlib.sha256(b).hexdigest()
def sections(data):
 assert data[:8]==b'\0asm\1\0\0\0';i=8;out={}
 def leb(at):
  n=0;shift=0
  while True:
   v=data[at];at+=1;n|=(v&127)<<shift;shift+=7
   if v<128:return n,at
 while i<len(data):
  kind=data[i];i+=1;size,i=leb(i);end=i+size;payload=data[i:end]
  key=str(kind)
  if kind==0:
   n,j=leb(i);key='custom:'+data[j:j+n].decode()
  assert key not in out;out[key]=payload;i=end
 return out
old,new=(Path(x).read_bytes() for x in sys.argv[1:3]);a,b=sections(old),sections(new)
rows={k:{'bytes_a':len(a.get(k,b'')),'bytes_b':len(b.get(k,b'')),'sha256_a':digest(a.get(k,b'')),'sha256_b':digest(b.get(k,b'')),'equal':a.get(k)==b.get(k)} for k in a.keys()|b.keys()}
changes=[]
if len(a['11'])==len(b['11']):changes=[{'offset':i,'old':x,'new':y} for i,(x,y) in enumerate(zip(a['11'],b['11'])) if x!=y]
r={'guest_sha256_a':digest(old),'guest_sha256_b':digest(new),'sections':rows,'same_code':a['10']==b['10'],'same_core_except_data':all(v['equal'] for k,v in rows.items() if not k.startswith('custom:') and k!='11'),'data_byte_changes':changes}
Path(sys.argv[3]).write_text(json.dumps(r,indent=2)+'\n');print(json.dumps({k:v for k,v in r.items() if k!='sections'},indent=2))
