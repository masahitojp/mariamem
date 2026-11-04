"""Scoped #93 check using the prior pinned Prisma dogfood and real DB endpoints."""
import argparse,contextlib,hashlib,importlib.util,json,os,struct,subprocess,sys
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--prisma',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--native-port',type=int);p.add_argument('--host',type=Path);a=p.parse_args()
sys.path[:0]=[str(a.source/'python'),str(a.source/'scripts'),str(a.source/'tests')]
import mariamem,pymysql
from git_identity import verify_go_binary
from v06_prepared_p1_probe import prepare,close_ping
from v06_prepared_call_probe import result_chain
spec=importlib.util.spec_from_file_location('prior_matrix',a.prisma/'matrix.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
r={'scope':'ISSUE93_ZERO_PARAMETER_EXECUTE_ONLY','prisma_probe_source_commit':'604a0c588f0a602bf6ea67d811b97bae2748c3ea','source_commit':subprocess.check_output(['git','rev-parse','HEAD'],cwd=a.source,text=True).strip(),'cases':[]}
a.output.parent.mkdir(exist_ok=True,parents=True)
@contextlib.contextmanager
def endpoint():
 if a.host:
  with mariamem.start(host_binary=a.host) as d:yield d.connection_info()
 else:yield dict(host='127.0.0.1',port=a.native_port,user='root',password='')
if a.host:
 r['binary_build_info']=verify_go_binary(a.source,a.host,r['source_commit']);r['binary_sha256']=hashlib.sha256(a.host.read_bytes()).hexdigest()
# Native endpoint must be the dedicated disposable container supplied by the caller.
for name in ('find_many_unfiltered','count_unfiltered','aggregate','group_by','raw_zero_parameter','count_filtered','raw_parameter'):
 with endpoint() as info:
  if a.native_port:m.sql(info,'DROP DATABASE IF EXISTS prisma_matrix')
  m.initialize(info,True);env=m.env_for(info,True)
  out=subprocess.run(['node','--import','tsx','matrix.ts',name],cwd=a.prisma,env=env,text=True,capture_output=True,timeout=45)
  value=m.last_json(out.stdout);r['cases'].append({'name':name,'exit_code':out.returncode,**value})
with endpoint() as info:
 env=m.env_for(info,True)
 driver="""import assert from 'node:assert/strict';import mariadb from 'mariadb';
const c=await mariadb.createConnection({host:process.env.DB_HOST,port:Number(process.env.DB_PORT),user:process.env.DB_USER,password:process.env.DB_PASSWORD,pipelining:false});
try{for(let i=0;i<2;i++)assert.equal(String((await c.execute('SELECT 1 AS n'))[0].n),'1');assert.equal(String((await c.execute('SELECT ? AS n',[7]))[0].n),'7');assert.equal(String((await c.query('SELECT 11 AS n'))[0].n),'11');console.log(JSON.stringify({result:'PASS',repeated_zero_execute:2,parameterized:7,following_text:11}));}finally{await c.end();}
"""
 out=subprocess.run(['node','--input-type=module'],input=driver,cwd=a.prisma,env=env,text=True,capture_output=True,timeout=30)
 r['driver_control']={'exit_code':out.returncode,**m.last_json(out.stdout)}
 r['driver_control_sha256']=hashlib.sha256(driver.encode()).hexdigest()
 if a.host:
  r['raw_controls']=[]
  for suffix,errno in ((b'',None),(b'\0',None),(b'\1',None),(b'\2',1835),(b'\xff',1835),(b'\0\0',1835),(b'\1\0',1835)):
   with pymysql.connect(**info,autocommit=True,read_timeout=5,write_timeout=5) as c:
    sid,_=prepare(c,'SELECT 7 AS n');parts=result_chain(c,struct.pack('<IBI',sid,0,1)+suffix,allow_error=True)
    if errno:assert parts[0]['errno']==errno,parts
    else:assert parts[0]['rows']==['000007000000'],parts
    with c.cursor() as q:q.execute('SELECT 11');assert q.fetchone()==(11,)
    close_ping(c,sid);r['raw_controls'].append({'suffix_hex':suffix.hex(),'expected_errno':errno,'result':'PASS'})
r['result']='PASS' if all(x['exit_code']==0 and x.get('result')=='PASS' for x in r['cases']) and r['driver_control']['exit_code']==0 else 'FAIL'
a.output.write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n');print(json.dumps(r,ensure_ascii=False));assert r['result']=='PASS'
