"""Untimed guest oracle; source probe and measurements remain unmodified."""
from pathlib import Path
import os,json,re,sys
w=Path(__file__).resolve().parents[1];t=w/'temp';e=w/'evidence';sys.path.insert(0,str(t/'source/python'));import mariamem,pymysql
scratch=t/'verification-scratch';scratch.mkdir();os.environ['TMPDIR']=str(scratch)
trace=t/'verification-timing';trace.mkdir();os.environ['MARIAMEM_TIMING_DIR']=str(trace);os.environ['GOMAXPROCS']='8'
expected={(id,level) for id in [2048,2304] for level in range(3)}
db=snapshot=child=session=None;out={'result':'FAIL','phases':{}};errors=[]
def check(db,label):
 with pymysql.connect(**db.connection_info(),autocommit=True,charset='utf8mb4') as c:
  with c.cursor() as q:
   for enc in ['utf8mb3','utf8mb4']:
    q.execute(f"SELECT STRCMP(_{enc}'a' COLLATE {enc}_uca1400_ai_ci,_{enc}'A' COLLATE {enc}_uca1400_ai_ci)");assert q.fetchone()==(0,)
 db.wait_disconnected();logs=db.logs;rows=[tuple(map(int,r)) for r in re.findall(r'UCA_PREPARED_VERIFY id=(\d+) level=(\d+) bytes=(\d+) match=(\d+)',logs)]
 assert rows and all(n==918016 and match==1 for id,level,n,match in rows),logs
 assert {(id,level) for id,level,n,match in rows}==expected,(label,rows)
 out['phases'][label]={'matches':rows,'logs':logs}
try:
 db=mariamem.start(host_binary=str(t/'dev-native/mariamem-dev-host'));session=db._session;check(db,'root');snapshot=db.snapshot(max_forks=4);child=snapshot.fork(host_binary=str(t/'dev-native/mariamem-dev-host'));check(child,'fork');out['result']='PASS'
finally:
 for owner in [child,snapshot,db]:
  if owner:
   try:owner.close()
   except Exception as x:errors.append(str(x))
 if session:out['cleanup']={'refs':session._refs,'process_exit':session._process.poll(),'reaped':session._reaped.is_set(),'root_exists':session.root.exists()}
 out['cleanup_errors']=errors
 if errors or out.get('cleanup')!={'refs':0,'process_exit':0,'reaped':True,'root_exists':False}:out['result']='FAIL'
 (e/'guest-table-verification.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n')
assert out['result']=='PASS',out
print('actual guest root + Fork: all six full tables match original producer; cleanup PASS')
