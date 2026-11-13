exec((__import__('pathlib').Path(__file__).parent/'map.py').read_text().split('text=(T/')[0])
i=8;segments=[]
while i<len(b):
 sid=b[i];n,j=v(i+1);end=j+n
 if sid==11:
  count,k=v(j)
  for segid in range(count):
   flags,k=v(k)
   if flags==2:_,k=v(k)
   if flags!=1:
    assert b[k]==0x41;k+=1;off,k=v(k);assert b[k]==0xb;k+=1
   else:off={0:8388608,1:18119936}.get(segid)
   size,k=v(k)
   if off is not None:segments.append((off,b[k:k+size]))
   k+=size
 i=end
def string(a):
 for off,data in segments:
  if off<=a<off+len(data):
   z=data[a-off:].split(b'\0',1)[0]
   if 4<len(z)<240 and all(x in (9,10,13) or 32<=x<127 for x in z):return z.decode()
for idx in [18569,4245,961,5424,4800,7109]:
 f=Path(f'/private/tmp/fn{idx}.txt')
 if not f.exists():continue
 vals=set(map(int,re.findall(r'(?:int32\(|MemoryEA\(m, )(\d+)',f.read_text())))
 ss={str(a):string(a) for a in sorted(vals) if string(a)};(E/f'strings-{idx}.json').write_text(json.dumps(ss,indent=2));print(idx,json.dumps(ss)[:2400])
