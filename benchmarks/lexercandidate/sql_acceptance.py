"""Finite lexer SQL/native differential and independent Snapshot children."""
import argparse,json,hashlib,subprocess,sys,platform
from pathlib import Path
import pymysql

def semantic(c):
 def q(sql):
  with c.cursor() as cur:cur.execute(sql);return cur.fetchall()
 out={'literals':q("SELECT '日本語',HEX(x'0041'),b'101'+0,N'word','a''b'"),'comments':q('SELECT 2 /* ; ? */ + 3 -- comment\n'),'identifier':q('SELECT `id`,`v` FROM fork_probe ORDER BY id'),'nul':q("SELECT HEX(CONCAT('a',CHAR(0),'b'))")}
 old=q('SELECT @@SESSION.sql_mode')[0][0]
 try:
  q("SET SESSION sql_mode='NO_BACKSLASH_ESCAPES,ANSI_QUOTES'")
  out['modes']=q('SELECT "v", \'a\\b\' FROM fork_probe WHERE "id"=2')
 finally:
  with c.cursor() as cur:cur.execute('SET SESSION sql_mode=%s',(old,))
 return json.loads(json.dumps(out))
def seed(c):
 with c.cursor() as q:
  q.execute('CREATE TABLE fork_probe(id INT PRIMARY KEY,v INT NOT NULL) ENGINE=InnoDB')
  q.execute('INSERT INTO fork_probe VALUES(1,1),(2,2)')
def main():
 p=argparse.ArgumentParser();p.add_argument('--native-port',type=int);p.add_argument('--native',type=Path);p.add_argument('--host',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 result={'result':'FAIL','platform':platform.platform(),'source_commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()}
 if a.native_port:
  with pymysql.connect(host='127.0.0.1',port=a.native_port,user='root',database='test',autocommit=True,charset='utf8mb4') as c:
   with c.cursor() as q:q.execute('SELECT VERSION()');result['version']=q.fetchone()[0]
   assert result['version'].startswith('12.3.3-');seed(c);result['semantic']=semantic(c)
  result['result']='PASS_NATIVE'
 else:
  import mariamem
  reference=json.loads(a.native.read_text());assert reference['result']=='PASS_NATIVE';expected=reference['semantic'];d=sn=session=None;children=[]
  result['native_sha256']=hashlib.sha256(a.native.read_bytes()).hexdigest();result['host_sha256']=hashlib.sha256(a.host.read_bytes()).hexdigest()
  try:
   d=mariamem.start(host_binary=str(a.host.resolve()));session=d._session
   with pymysql.connect(**d.connection_info(),autocommit=True,charset='utf8mb4') as c:seed(c);assert semantic(c)==expected
   d.wait_disconnected();sn=d.snapshot(max_forks=2);assert sn.max_forks==2
   for i in range(2):
    child=sn.fork();children.append(child)
    with pymysql.connect(**child.connection_info(),autocommit=True,charset='utf8mb4') as c:
     assert semantic(c)==expected
     with c.cursor() as q:q.execute('UPDATE fork_probe SET v=77 WHERE id=1');q.execute('SELECT v FROM fork_probe WHERE id=1');assert q.fetchone()==(77,)
    child.wait_disconnected()
   result.update(result='PASS_GUEST',children=2,semantic=expected)
  finally:
   errors=[]
   for obj in list(reversed(children))+[sn,d]:
    if obj:
     try:obj.close()
     except BaseException as ex:errors.append(str(ex))
   result['cleanup_errors']=errors;assert not errors,errors
   if session is not None:
    result['cleanup']={'refs':session._refs,'process_exit':session._process.poll(),'reaped':session._reaped.is_set(),'root_exists':session.root.exists()}
    assert result['cleanup']=={'refs':0,'process_exit':0,'reaped':True,'root_exists':False},result['cleanup']
 a.output.write_text(json.dumps(result,indent=2)+'\n');print(result['result'])
if __name__=='__main__':main()
