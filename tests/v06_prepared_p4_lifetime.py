"""P4 first acceptance slice: ownership/reset/quota/disconnect, not LONG_DATA.

Each real-guest scenario owns a fresh root. Native packet traces remain exact;
connection IDs are opaque and the Go consumer checks replacement internally.
"""
import argparse
import json
import os
from pathlib import Path
import struct
import subprocess
import time

import pymysql
from v06_prepared_p1_probe import RawErrorPacket, close_ping, prepare
from v06_prepared_p2_matrix import execute, payload, query


def connection(info):
    return pymysql.connect(**info, autocommit=True, charset='utf8mb4', read_timeout=10, write_timeout=10)


def packet(c, op, body):
    c._execute_command(op, body)
    return c._read_packet(RawErrorPacket).get_all_data()


def count(c):
    return int(query(c,"SHOW GLOBAL STATUS LIKE 'Prepared_stmt_count'")[0][1])


def drained(c, expected=0):
    deadline=time.monotonic()+5
    while True:
        n=count(c)
        if n==expected:return n
        if time.monotonic()>=deadline:raise AssertionError(('native statement leak',n,expected))
        time.sleep(.005)  # asynchronous disconnect cleanup, not a framing delay


def scenario(info, name, out=None):
    if out is None:out={}
    out['trace']=[];out['stage']=name;trace=out['trace']
    with connection(info) as c:
        assert query(c,'SELECT VERSION()')[0][0].startswith('12.3.3')
        query(c,'SET NAMES utf8mb4 COLLATE utf8mb4_general_ci')
        assert drained(c)==0
        if name=='reset-type-reuse-and-transaction':
            query(c,'DROP TABLE IF EXISTS test.p4_reset')
            query(c,'CREATE TABLE test.p4_reset(id INT PRIMARY KEY,v INT) ENGINE=InnoDB')
            query(c,'INSERT INTO test.p4_reset VALUES(1,7)')
            sid,meta=prepare(c,'UPDATE test.p4_reset SET v=? WHERE id=1')
            out['prepare']=meta
            query(c,'START TRANSACTION')
            trace.append(execute(c,sid,[(3,False,struct.pack('<i',29))],[]))
            trace.append(packet(c,26,struct.pack('<I',sid)).hex())
            assert query(c,'SELECT v FROM test.p4_reset')==((29,),)
            query(c,'ROLLBACK');assert query(c,'SELECT v FROM test.p4_reset')==((7,),)
            trace.append(execute(c,sid,[(3,False,struct.pack('<i',31))],[],reuse=True))
            assert query(c,'SELECT v FROM test.p4_reset')==((31,),)
            close_ping(c,sid);query(c,'DROP TABLE test.p4_reset')
        elif name=='malformed-lifecycle-adjacency':
            # Actual ID is deliberately small; exercise 0/1/2/3/4/5-byte bodies.
            # Native accepts a short zero-extended ID, ignores surplus bytes and
            # emits no CLOSE response. Never insert sleeps between these commands.
            for length in range(6):
                sid,_=prepare(c,'SELECT ?');assert sid<256
                body=struct.pack('<I',sid)[:length] if length<4 else struct.pack('<I',sid)+b'x'*(length-4)
                reset=packet(c,26,body);trace.append({'length':length,'reset':reset.hex()})
                assert (reset[0]==255 and int.from_bytes(reset[1:3],'little')==1243) if length==0 else reset[0]==0
                c._execute_command(25,body);c._execute_command(14,b'')
                assert c._read_packet().is_ok_packet()
                after=packet(c,26,struct.pack('<I',sid))
                assert after[0]==0 if length==0 else after[0]==255 and int.from_bytes(after[1:3],'little')==1243
                if length:assert after[4:9]==b'HY000'
                # Error text contains the opaque handle. Compare errno/state;
                # preserve full packets separately, not rewrite packet contents.
                trace[-1]['after_kind']='ok' if after[0]==0 else 'unknown-handle'
                out.setdefault('opaque_handle_observations',[]).append({'id':sid,'after_reset_packet':after.hex()})
                if length==0:close_ping(c,sid)
        elif name=='closed-cross-session-handles':
            sid,_=prepare(c,'SELECT ?')
            with connection(info) as other:
                r=packet(other,26,struct.pack('<I',sid));assert r[0]==255
                assert int.from_bytes(r[1:3],'little')==1243
                assert r[4:9]==b'HY000'
                out.setdefault('opaque_handle_observations',[]).append({'id':sid,'cross_session_reset_packet':r.hex()})
                close_ping(other,sid)
                own,_=prepare(other,'SELECT ?')
                trace.append(execute(other,own,[(3,False,struct.pack('<i',92))],[]))
                close_ping(c,sid)
                trace.append(execute(other,own,[(3,False,struct.pack('<i',93))],[],reuse=True))
                close_ping(other,own)
            r=packet(c,23,payload(sid,[(3,False,struct.pack('<i',7))]));assert r[0]==255
            assert int.from_bytes(r[1:3],'little')==1243 and r[4:9]==b'HY000'
            out.setdefault('opaque_handle_observations',[]).append({'id':sid,'closed_execute_packet':r.hex()})
            trace.append({'closed_execute_errno':1243,'sqlstate':'HY000'})
        elif name=='native-quota-and-recovery':
            old=int(query(c,'SELECT @@global.max_prepared_stmt_count')[0][0]);handles=[]
            try:
                query(c,'SET GLOBAL max_prepared_stmt_count=2')
                handles=[prepare(c,'SELECT ?')[0] for _ in range(2)]
                assert count(c)==2
                error=packet(c,22,b'SELECT ?');assert error[0]==255
                assert int.from_bytes(error[1:3],'little')==1461 and error[4:9]==b'42000'
                trace.append({'quota_errno':1461,'sqlstate':'42000','live':count(c),'error_packet':error.hex()})
                close_ping(c,handles.pop());handles.append(prepare(c,'SELECT ?')[0])
                trace.append(execute(c,handles[-1],[(3,False,struct.pack('<i',77))],[]))
            finally:
                for sid in handles:close_ping(c,sid)
                query(c,f'SET GLOBAL max_prepared_stmt_count={old}')
        elif name in ('idle-quit-cleanup','idle-eof-cleanup'):
            query(c,'DROP TABLE IF EXISTS test.p4_disconnect')
            query(c,'CREATE TABLE test.p4_disconnect(id INT PRIMARY KEY,v INT) ENGINE=InnoDB')
            query(c,'INSERT INTO test.p4_disconnect VALUES(1,7)')
            for i in range(12):
                other=connection(info)
                try:
                    handles=[prepare(other,'SELECT ?')[0] for _ in range(3)]
                    sid,_=prepare(other,'UPDATE test.p4_disconnect SET v=? WHERE id=1')
                    query(other,'START TRANSACTION')
                    reply=execute(other,sid,[(3,False,struct.pack('<i',99))],[])
                    assert reply['kind']=='ok';assert count(c)==4
                finally:
                    if name=='idle-eof-cleanup':other._force_close()
                    else:other.close()
                assert drained(c)==0
                assert query(c,'SELECT v FROM test.p4_disconnect')==((7,),)
            trace.append({'sessions':12,'statements_per_session':4,'live_after':0,'rollback':True})
            query(c,'DROP TABLE test.p4_disconnect')
        else:raise ValueError(name)
        assert query(c,'SELECT 1')==((1,),)
        out.update(result='PASS',following_query='PASS',prepared_after=drained(c))
        out.pop('stage',None)
    return out


CASES=('reset-type-reuse-and-transaction','malformed-lifecycle-adjacency',
       'closed-cross-session-handles','native-quota-and-recovery','idle-quit-cleanup','idle-eof-cleanup')


def exercise(info=None,host=None,consumer=None):
    result={'scope':'P4 lifetime first slice; LONG_DATA and full P4 are unfinished','cases':{},'failures':{}}
    for name in (*CASES,'go-DB-Tx-Conn-pool'):
        db=None;case={}
        try:
            if host:
                import mariamem
                db=mariamem.start(host_binary=host);current=db.connection_info();case['runtime']=db.diagnostics
            else:current=info
            if name=='go-DB-Tx-Conn-pool':
                # DSN stays in the child environment, never logs/command arguments.
                env=os.environ.copy();env['MARIAMEM_P4_DSN']=f"{current['user']}:{current.get('password','')}@tcp({current['host']}:{current['port']})/{current.get('database','test')}?timeout=5s&readTimeout=10s&writeTimeout=10s"
                run=subprocess.run([str(consumer)],env=env,capture_output=True,text=True,timeout=70)
                case['consumer']=json.loads(run.stdout);case['stderr']=run.stderr
                assert run.returncode==0 and case['consumer']['result']=='PASS',case
                assert case['consumer']['open_after']==0
                case['result']='PASS'
            else:scenario(current,name,case)
            if db:
                db.wait_disconnected(timeout=10)
                case['active_connections_after']=db.status()['active_connections'];assert case['active_connections_after']==0
        except Exception as error:case.update(result='FAIL',error=repr(error))
        finally:
            if db:
                temporary=db.log_path.parent
                try:case['logs']=db.logs;db.close();db.close();assert not temporary.exists();case['temporary_removed']=True
                except Exception as error:case.update(result='FAIL',cleanup_error=repr(error))
        result['cases'][name]=case
        if case.get('result')!='PASS':result['failures'][name]=case.get('error',case.get('cleanup_error','missing PASS'))
    result['result']='FAIL' if result['failures'] else 'PASS'
    return result


def comparable(case):
    return {k:case[k] for k in ('trace','prepare','following_query','prepared_after','consumer') if k in case}


def main():
    p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True)
    g.add_argument('--host');g.add_argument('--native-port',type=int)
    p.add_argument('--consumer',type=Path,required=True);p.add_argument('--reference',type=Path)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    result=exercise(info=dict(host='127.0.0.1',port=a.native_port,user='root',database='test') if a.native_port else None,host=a.host,consumer=a.consumer)
    if a.reference:
        native=json.loads(a.reference.read_text());assert native['result']=='PASS'
        differences=[n for n in result['cases'] if comparable(result['cases'][n])!=comparable(native['cases'][n])]
        result['different_cases']=differences;result['native_comparison']='FAIL' if differences else 'PASS'
        if differences:result['result']='FAIL'
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n')
    if result['result']!='PASS':raise SystemExit(1)


if __name__=='__main__':main()
