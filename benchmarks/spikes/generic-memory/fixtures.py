"""Small binary WASM fixtures; instructions come from the pinned lowering tables."""
import json
from pathlib import Path

def u(n):
 b=[]
 while True:
  x=n&127;n>>=7;b.append(x|(128 if n else 0))
  if not n:return b

def sleb(n):
 b=[]
 while True:
  x=n&127;n>>=7;done=(n==0 and not x&64) or (n==-1 and x&64);b.append(x|(0 if done else 128))
  if done:return b

def vec(xs):return u(len(xs))+sum(xs,[])
def string(s):return u(len(s))+list(s.encode())
def section(k,x):return [k]+u(len(x))+x

def build(out):
 out=Path(out);out.mkdir(parents=True,exist_ok=True);ops=[];bodies=[];names=[];types=[]
 def add(name,code,result=0x7e,width=1,offset=0,family='scalar',extra=None):
  names.append(name);types.append(1 if result==0x7f else 0);bodies.append([0]+code+[0x0b]);ops.append(dict(name=name,width=width,offset=offset,family=family,**(extra or {})))
 for offset in [0,4,65536,4294967295]:
  for w,load,store in [(1,0x2d,0x3a),(2,0x2f,0x3b),(4,0x28,0x36),(8,0x29,0x37)]:
   arg=[0x20,0];imm=u((w.bit_length()-1))+u(offset);ext=[] if w==8 else [0xad]
   add(f'l{w*8}o{offset}',arg+[load]+imm+ext,width=w,offset=offset)
   add(f's{w*8}o{offset}',arg+([0x42] if w==8 else [0x41])+sleb(85)+[store]+imm+[0x42,0],width=w,offset=offset)
  for w,l,s in [(1,0x12,0x19),(2,0x13,0x1a),(4,0x10,0x17),(8,0x11,0x18)]:
   imm=u(w.bit_length()-1)+u(offset);ext=[] if w==8 else [0xad]
   add(f'al{w*8}o{offset}',[0x20,0,0xfe]+u(l)+imm+ext,width=w,offset=offset,family='atomic')
   add(f'as{w*8}o{offset}',[0x20,0]+([0x42] if w==8 else [0x41])+sleb(85)+[0xfe]+u(s)+imm+[0x42,0],width=w,offset=offset,family='atomic')
   rmw={1:0x20,2:0x21,4:0x1e,8:0x1f}[w]
   add(f'ar{w*8}o{offset}',[0x20,0]+([0x42] if w==8 else [0x41])+sleb(1)+[0xfe]+u(rmw)+imm+ext,width=w,offset=offset,family='atomic')
  add(f'vl128o{offset}',[0x20,0,0xfd,0]+u(4)+u(offset)+[0xfd,0x1d,0],width=16,offset=offset,family='simd')
  add(f'vs128o{offset}',[0x20,0,0xfd,0x0c]+list(range(1,17))+[0xfd,0x0b]+u(4)+u(offset)+[0x42,0],width=16,offset=offset,family='simd')
  for w,op in [(1,0x07),(2,0x08),(4,0x09),(8,0x0a),(4,0x5c),(8,0x5d),(8,0x02)]:
   add(f'vl{op}o{offset}',[0x20,0,0xfd]+u(op)+u(w.bit_length()-1)+u(offset)+[0xfd,0x1d,0],width=w,offset=offset,family='simd')
  for w,l,s in [(1,0x54,0x58),(2,0x55,0x59),(4,0x56,0x5a),(8,0x57,0x5b)]:
   const=[0xfd,0x0c]+list(range(1,17));imm=u(w.bit_length()-1)+u(offset)+[0]
   add(f'vll{w*8}o{offset}',[0x20,0]+const+[0xfd]+u(l)+imm+[0xfd,0x1d,0],width=w,offset=offset,family='simd')
   add(f'vsl{w*8}o{offset}',[0x20,0]+const+[0xfd]+u(s)+imm+[0x42,0],width=w,offset=offset,family='simd')
 # Distinguish wrapping i32.add from non-wrapping static memory offset.
 add('wrappedadd',[0x20,0,0x41]+sleb(-65536)+[0x6a,0x28,2,0,0xad],width=4,extra={'dynamic_add':-65536})
 add('positiveadd',[0x20,0,0x41]+sleb(65536)+[0x6a,0x28,2,0,0xad],width=4,extra={'dynamic_add':65536})
 add('droppedload',[0x20,0,0x28,2,0,0x1a,0x42,0],width=4)
 add('twoloads',[0x20,0,0xfd,0,4,0,0xfd,0x1d,0,0x20,0,0xfd,0,4,32,0xfd,0x1d,0,0x7c],width=48,family='simd')
 add('grow',[0x20,0,0x40,0],result=0x7f);ops.pop()
 typesec=vec([[0x60,1,0x7f,1,0x7e],[0x60,1,0x7f,1,0x7f]])
 exports=vec([string(n)+[0]+u(i) for i,n in enumerate(names)]+[string('memory')+[2,0]])
 binary=bytes([0,97,115,109,1,0,0,0]+section(1,typesec)+section(3,vec([u(x) for x in types]))+section(5,[1,3,1,3])+section(7,exports)+section(10,vec([u(len(b))+b for b in bodies])))
 (out/'contract.wasm').write_bytes(binary)
 cases=[]
 for grow in [0,1]:
  size=(1+grow)*65536
  for op in ops:
   dynamic=op.get('dynamic_add',0)
   addresses=[32,33,size,size-op['width']+1,(-op['offset'])&0xffffffff,0xffffffff]
   if op['offset']<size-op['width']:addresses+=[size-op['width']-op['offset']]
   if dynamic:addresses+=[(-dynamic)&0xffffffff,65568]
   for addr in dict.fromkeys(addresses):
    ea=((addr+dynamic)&0xffffffff)+op['offset']
    align=op['family']=='atomic' and ea%op['width']!=0
    safe=((addr+dynamic+op['offset'])&0xffffffff)+op['width']<=3*65536 and not align
    cases.append(dict(op=op['name'],addr=addr if addr<2147483648 else addr-4294967296,grow=grow,baseline_safe=safe,expected_trap=ea+op['width']>size or align))
 (out/'matrix.json').write_text(json.dumps(cases,indent=2)+'\n');(out/'operations.json').write_text(json.dumps(ops,indent=2)+'\n')
 return len(cases)
