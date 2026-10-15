"""Small receiver fixtures with the actual guest identity, no SQL process."""
import copy,hashlib,json,os,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];sys.path.insert(0,str(ROOT/'python'))
from mariamem.snapshot import _host_identity
from d2_python import D2Snapshot
host=Path(sys.argv[1]).resolve();options={'host_binary':str(host)};_,build=_host_identity(options)
m={'format':'mariamem-cold-snapshot','version':1,'wasm_sha256':build,'source_storage':'memory','entries':{'.':{'kind':'directory'},'a':{'kind':'file','bytes':1,'sha256':hashlib.sha256(b'x').hexdigest()}}}
l={'parents':0,'segments':[16384],'dirs':['.'],'files':{'a':{'size':1,'refs':[{'seg':0,'off':0,'valid':1}]}}}
checks=[]
for case in ['valid','guest','content','range','inventory','parent','segment-size']:
 with tempfile.TemporaryDirectory() as directory:
  temporary=tempfile.TemporaryDirectory(dir=directory);root=Path(temporary.name)/'snapshot';(root/'segments').mkdir(parents=True)
  manifest=copy.deepcopy(m);layout=copy.deepcopy(l);data=b'x'+bytes(16383)
  if case=='guest':manifest['wasm_sha256']='0'*64
  if case=='content':data=b'y'+data[1:]
  if case=='range':layout['files']['a']['refs'][0]['off']=16384
  if case=='inventory':manifest['entries']['missing']={'kind':'directory'}
  if case=='parent':layout['parents']=1
  if case=='segment-size':layout['segments'][0]=32768
  (root/'segments/0').write_bytes(data);(root/'d2.json').write_text(json.dumps({'manifest':manifest,'layout':layout}))
  try:owner=D2Snapshot.acquire(root,options,temporary)
  except ValueError as exc:
   assert case!='valid',str(exc);checks.append({'case':case,'result':'rejected','message':str(exc)})
  else:
   assert case=='valid',case
   pinned=owner.clone();owner.close();pinned.verify();pinned.close();checks.append({'case':case,'result':'accepted-clone-survives-close'})
print(json.dumps({'status':'PASS','checks':checks},indent=2))
