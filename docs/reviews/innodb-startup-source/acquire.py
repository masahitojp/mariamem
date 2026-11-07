from pathlib import Path
import json,subprocess,base64,hashlib,time,sys
w=Path(__file__).resolve().parents[1];e=w/'evidence';t=w/'temp';plan=json.loads((e/'plan.json').read_text());pin=plan['source_commit'];records=json.loads((e/'source-files.json').read_text()) if (e/'source-files.json').exists() else []
for name in sys.argv[1:]:
 assert not name.startswith('/') and '..' not in Path(name).parts
 target=t/'upstream'/name
 if target.exists():
  prior=next(r for r in records if r['path']==name)
  assert hashlib.sha256(target.read_bytes()).hexdigest()==prior['sha256']
  print('EXISTS_VERIFIED',name);continue
 prior=next((r for r in records if r['path']==name),None)
 if prior is None:assert len(records)<plan['maximum_upstream_files']
 r=subprocess.run(['gh','api','repos/MariaDB/server/contents/'+name+'?ref='+pin],capture_output=True,timeout=30,check=True)
 j=json.loads(r.stdout);assert j['encoding']=='base64';data=base64.b64decode(j['content']);assert len(data)==j['size']
 blob=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest();assert blob==j['sha']
 target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
 row=dict(path=name,source_commit=pin,github_blob=blob,sha256=hashlib.sha256(data).hexdigest(),bytes=len(data))
 if prior is None:records.append(row)
 else:assert row==prior
 (e/'source-files.json').write_text(json.dumps(records,indent=2)+'\n');print('FETCHED',name,len(data),flush=True)
