from pathlib import Path
import hashlib,json
E=Path(__file__).resolve().parent;s=(E/'review-binding.py').read_text();before=(E/'binding-review.json').read_bytes();cases={
'worker-arithmetic':s.replace('path,body=find(index);changes=[]',"path,body=find(index);body=body.replace('int32(-2)','int32(-3)',1) if oldfn=='Fn153' else body;changes=[]"),
'crc-non-address-constant':s.replace("body=body.rstrip();newfn=", "body=body.rstrip().replace('int64(12288)','int64(12289)',1);newfn="),
'crc-table-byte':s.replace("offset=newdata.find(table)","newdata=newdata.replace(table,bytes([table[0]^1])+table[1:],1);offset=newdata.find(table)")}
results={}
for name,code in cases.items():
 assert code!=s
 try:exec(compile(code,str(E/'review-binding.py'),'exec'),{'__file__':str(E/'review-binding.py'),'__name__':'__main__'})
 except (AssertionError,ValueError) as e:results[name]={'rejected':True,'error':str(e)}
 else:raise AssertionError('mutation admitted '+name)
 assert (E/'binding-review.json').read_bytes()==before
(E/'binding-negative-controls.json').write_text(json.dumps(results,indent=2)+'\n');print('PASS three binding mutations rejected; positive proof unchanged')
