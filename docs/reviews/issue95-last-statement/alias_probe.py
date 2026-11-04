"""Sequential last-statement alias controls; no PREPARE/EXECUTE pipelining."""
import argparse,json,struct,sys
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--source',type=Path,required=True);p.add_argument('--port',type=int,required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();sys.path.insert(0,str(a.source/'tests'))
import pymysql
from v06_prepared_p1_probe import prepare,close_ping
from v06_prepared_call_probe import result_chain
A=0xffffffff;info=dict(host='127.0.0.1',port=a.port,user='root',password='',autocommit=True,read_timeout=5,write_timeout=5)
r={'scope':'SEQUENTIAL_ALIAS_LIFECYCLE_NOT_PIPELINE_SUPPORT','checks':[]}
def execute(c,sid,value=7,reuse=False,blob=False,stream=False):
 body=struct.pack('<IBI',sid,0,1)+b'\0'+bytes([not reuse])
 if not reuse:body+=bytes([252 if blob else 3,0])
 if not stream:body+=bytes([len(value)])+value if blob else struct.pack('<i',value)
 return result_chain(c,body,allow_error=True)
def check(name,parts,value=None,errno=None):
 if errno:assert parts[0].get('errno')==errno,(name,parts)
 else:assert parts[0].get('rows')==[b'\0\0'.hex()+struct.pack('<i',value).hex()],(name,parts)
 r['checks'].append({'name':name,'result':'PASS','errno':errno,'value':value})
with pymysql.connect(**info) as c:
 r['server_capabilities']=c.server_capabilities;r['client_capabilities']=c.client_flag
 with c.cursor() as q:q.execute('SELECT VERSION()');r['version']=q.fetchone()[0]
 check('before-prepare',execute(c,A),errno=1243)
 first,_=prepare(c,'SELECT ? AS n');check('actual-id',execute(c,first),7);check('alias',execute(c,A,8),8);check('alias-requires-fresh-types',execute(c,A,9,True),errno=1835);check('actual-id-reuses-alias-types',execute(c,first,9,True),9)
 second,_=prepare(c,'SELECT ? AS second_value');check('latest-prepare',execute(c,A,11),11)
 check('older-explicit-id',execute(c,first,12),12);check('explicit-does-not-retarget',execute(c,A,13),13)
 close_ping(c,first);check('close-older-keeps-latest',execute(c,A,14),14)
 try:prepare(c,'SELEC broken ?')
 except pymysql.err.ProgrammingError as e:assert e.args[0]==1064
 else:raise AssertionError('invalid prepare succeeded')
 check('failed-prepare-invalidates',execute(c,A),errno=1243);check('old-actual-id-survives',execute(c,second,15),15);check('actual-id-does-not-revive',execute(c,A),errno=1243)
 third,_=prepare(c,'SELECT ? AS restored');check('reprepare-restores',execute(c,A,16),16)
 c._execute_command(26,struct.pack('<I',A));assert c._read_packet().is_ok_packet();check('reset-alias-keeps-latest',execute(c,A,17),17)
 close_ping(c,A);check('close-alias-retires-actual',execute(c,third),errno=1243);check('close-no-fallback',execute(c,A),errno=1243);check('older-actual-still-owned',execute(c,second,18),18)
 with pymysql.connect(**info) as other:
  check('other-connection-no-alias',execute(other,A),errno=1243);sid,_=prepare(other,'SELECT ? AS isolated');check('other-connection-own-alias',execute(other,A,19),19)
  check('other-prepare-does-not-revive-first',execute(c,A),errno=1243);close_ping(other,sid)
 sid,_=prepare(c,'SELECT ? AS blob_value');c._execute_command(24,struct.pack('<IH',A,0)+b'abc')
 # Synchronize no-response command before EXECUTE.
 c._execute_command(14,b'');assert c._read_packet().is_ok_packet()
 parts=execute(c,A,blob=True,stream=True);assert parts[0].get('rows')==['000003616263'],parts
 r['checks'].append({'name':'long-data-alias-execute','result':'PASS','row_hex':parts[0]['rows'][0]})
 c._execute_command(24,struct.pack('<IH',A,9)+b'x');c._execute_command(14,b'');assert c._read_packet().is_ok_packet()
 check('long-data-deferred-error-alias',execute(c,A,blob=True,stream=True),errno=1210)
 c._execute_command(26,struct.pack('<I',A));assert c._read_packet().is_ok_packet()
 parts=execute(c,A,b'z',blob=True);assert parts[0].get('rows')==['0000017a'],parts
 r['checks'].append({'name':'reset-alias-clears-long-data-error','result':'PASS'})
 close_ping(c,sid);close_ping(c,second)
 zero,_=prepare(c,'SELECT 7 AS n');check('zero-parameter-alias',result_chain(c,struct.pack('<IBI',A,0,1),allow_error=True),7);close_ping(c,zero)
 with c.cursor() as q:
  q.execute('CREATE DATABASE IF NOT EXISTS alias95_probe')
  q.execute('CREATE TEMPORARY TABLE alias95_probe.items(id INT PRIMARY KEY)')
 sid,_=prepare(c,'INSERT INTO alias95_probe.items VALUES (?)')
 assert 'ok_packet' in execute(c,A,7)[0]
 check('sql-error-does-not-retire-alias',execute(c,A,7),errno=1062)
 assert 'ok_packet' in execute(c,A,8)[0]
 r['checks'].append({'name':'alias-works-after-sql-error','result':'PASS'})
 close_ping(c,A)
 with c.cursor() as q:q.execute('SELECT 1');assert q.fetchone()==(1,)
 r['following_query']='PASS'
r['result']='PASS';a.output.write_text(json.dumps(r,indent=2)+'\n');print(json.dumps(r))
