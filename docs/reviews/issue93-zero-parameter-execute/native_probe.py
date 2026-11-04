import json,os,struct,sys
from pathlib import Path
import pymysql
sys.path.insert(0,str(Path(os.environ['SOURCE'])/'tests'))
from v06_prepared_p1_probe import prepare,close_ping
from v06_prepared_call_probe import result_chain
info=dict(host='127.0.0.1',port=int(os.environ['NATIVE_PORT']),user='root',password='',autocommit=True,read_timeout=5,write_timeout=5)
r={'scope':'Native zero-parameter COM_STMT_EXECUTE suffix acceptance','image_id':os.environ['NATIVE_IMAGE_ID'],'image_digest':os.environ['NATIVE_IMAGE_DIGEST'],'cells':[]}
for name,suffix in [('canonical',b''),('flag0',b'\0'),('flag1',b'\1'),('flag2',b'\2'),('flag255',b'\xff'),('two-bytes',b'\1\0'),('junk',b'not-a-flag')]:
 with pymysql.connect(**info) as c:
  with c.cursor() as q:q.execute('SELECT VERSION()');r['native_version']=q.fetchone()[0]
  sid,meta=prepare(c,'SELECT 7 AS n');assert len(meta['parameters'])==0
  payload=struct.pack('<IBI',sid,0,1)+suffix
  parts=result_chain(c,payload,allow_error=True)
  assert parts[0].get('rows')==['000007000000'],parts
  assert r['native_version']=='12.3.3-MariaDB-ubu2404',r['native_version']
  with c.cursor() as q:q.execute('SELECT 11');following=q.fetchone();assert following==(11,)
  close_ping(c,sid)
  r['cells'].append({'name':name,'payload_hex':payload.hex(),'trace':parts,'following_query':list(following)})
Path(os.environ['NATIVE_OUTPUT']).write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
