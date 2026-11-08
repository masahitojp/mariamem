"""Recompute selected current-Go/C correspondences; not a full C symbol map."""
import pathlib,re,json,hashlib,sys
source=pathlib.Path(sys.argv[1]).resolve();out=pathlib.Path(sys.argv[2]);code=source/'internal/generatedgo/code'
layout={'Fn16624':'p6','Fn16787':'p8','Fn18164':'p3','Fn18162':'p4','Fn17217':'p4'};record={'product_source_commit':'a3b2b6457147e2b8edbd31fec77ab6ec04f11b22','kind':'selected structural correspondence, no full C symbol map','functions':{}}
for fn,part in layout.items():
 path=code/part/(part+'_pure.go');text=path.read_text();m=re.search(r'^func '+fn+r'\(.*?(?=\nfunc |\Z)',text,re.M|re.S);assert m;body=m.group();record['functions'][fn]={'path':str(path.relative_to(source)),'line':text.count('\n',0,m.start())+1,'sha256':hashlib.sha256(body.encode()).hexdigest()}
 if fn=='Fn16624':assert 'v13 = l0 + int32(28)' in body and 'Fn216(m, v13, v15, int32(0))' in body
 if fn=='Fn16787':assert 'if l1 != 0 {' in body and body.count('Fn16624(m, l0+int32(24))')==2 and 'Fn16583(m)' in body and 'Fn16584(m)' in body
 if fn=='Fn18164':assert 'Fn16787(m, v580, v108)' in body
 if fn=='Fn17217':assert 'int32(8705264), int32(886)' in body and 'int32(8705264), int32(887)' in body
text=(code/'generated.go').read_text();prefix='var wasm2goData_data_bin = []byte("';i=text.index(prefix)+len(prefix);j=text.index('")',i);encoded=text[i:j];assert re.fullmatch(r'(?:\\x[0-9a-f]{2})+',encoded);blob=bytes.fromhex(encoded.replace('\\x',''))
init=(code/'p7/p7_pure.go').read_text();assert 'base.MemoryInit(m, 0, int32(8388608), v7, int32(8981670))' in init
literals={}
for address in (8705264,8759171,8542780):literals[str(address)]=blob[address-8388608:].split(b'\0',1)[0].decode()
assert literals['8705264'].endswith('/storage/innobase/trx/trx0purge.cc') and literals['8759171']=='hdr_page_no != FIL_NULL' and literals['8542780']=='tail.trx_no <= last_trx_no'
record['static_literals']=literals;record['literal_note']='Code provenance anchors only; not evidence an assertion failed.'
out.write_text(json.dumps(record,indent=2)+'\n')
