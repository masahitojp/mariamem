"""Fixed real consumer controls: native vs explicit UNQUALIFIED P5 guest.

No driver-mode forcing for default, SQL retries or error-code rewriting.
"""
import argparse
from decimal import Decimal
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import ssl
import subprocess
import sys

from v06_prepared_p4_lifetime import connection, packet, drained
from v06_prepared_p2_matrix import query

MODES=('pure','default','cext')


def scalar(value):
    if isinstance(value, (bytes, bytearray)):
        return {'type':'bytes','hex':bytes(value).hex()}
    if isinstance(value, Decimal):
        return {'type':'decimal','value':str(value)}
    return value


def python_case(info, mode, out=None):
    import mysql.connector as connector
    assert importlib.metadata.version('mysql-connector-python')=='26.7.0'
    if mode=='cext' and not connector.HAVE_CEXT:
        return {'result':'SKIP','reason':'explicit C extension unavailable; default and pure remain required'}
    kwargs={} if mode=='default' else {'use_pure':mode=='pure'}
    if out is None:out={}
    out.update(mode=mode,connector=connector.__version__)
    out['stage']='connect'
    with connector.connect(**info,connection_timeout=5,read_timeout=15,write_timeout=15,**kwargs) as c:
        out['implementation']=type(c).__name__
        with c.cursor() as q:
            q.execute('DROP TABLE IF EXISTS test.p5_connector')
            q.execute('CREATE TABLE test.p5_connector(id INT PRIMARY KEY,v VARBINARY(30)) ENGINE=InnoDB')
            q.execute('DROP PROCEDURE IF EXISTS test.p5_connector_call')
            q.execute('CREATE PROCEDURE test.p5_connector_call(IN x INT) BEGIN SELECT x; SELECT x+1; END')
        out['stage']='prepared-values'
        values=[]
        with c.cursor(prepared=True) as q:
            for v in [None, -17, 9223372036854775807, '雪', b'A\x00B', Decimal('123.45')]:
                q.execute('SELECT %s',(v,));row=q.fetchone();assert row is not None
                assert q.fetchone() is None
                values.append(scalar(row[0]))
        out['prepared_values']=values
        out['nul_projection_integrity']='PASS' if values[4] in ('A\0B',{'type':'bytes','hex':'410042'}) else 'FAIL'
        with c.cursor(prepared=True) as q:
            q.execute('INSERT INTO test.p5_connector VALUES(%s,%s)',(1,b'A\0B'))
        out['stage']='rollback'
        c.rollback()
        with c.cursor() as q:
            q.execute('SELECT COUNT(*) FROM test.p5_connector');assert q.fetchone()==(0,)
        with c.cursor(prepared=True) as q:
            q.execute('INSERT INTO test.p5_connector VALUES(%s,%s)',(1,b'A\0B'))
        c.commit()
        with c.cursor(prepared=True) as q:
            q.execute('SELECT v FROM test.p5_connector WHERE id=%s',(1,))
            assert bytes(q.fetchone()[0])==b'A\0B';assert q.fetchone() is None
            try:q.execute('INSERT INTO test.p5_connector VALUES(%s,%s)',(1,b''))
            except connector.Error as e:
                assert e.errno==1062
                out['duplicate_error']={'errno':e.errno,'sqlstate':e.sqlstate}
            else:raise AssertionError('duplicate accepted')
        c.rollback()
        out['stage']='syntax-error'
        # Preserve the accepted native-parity C-extension syntax presentation.
        with c.cursor(prepared=True) as q:
            try:q.execute('SELEC invalid')
            except connector.Error as e:out['syntax_error']={'errno':e.errno,'sqlstate':e.sqlstate}
            else:raise AssertionError('syntax accepted')
        with c.cursor() as q:
            q.execute('SELECT 1');assert q.fetchone()==(1,)
            q.execute('SELECT 7; SELECT 8')
            sets=[]
            while True:
                if q.with_rows:sets.append([list(row) for row in q.fetchall()])
                if not q.nextset():break
            assert sets==[[[7]],[[8]]],sets
            out['default_multi_statement']=sets
            q.execute("SHOW GLOBAL STATUS LIKE 'Prepared_stmt_count'")
            out['prepared_after']=int(q.fetchone()[1]);assert out['prepared_after']==0
        expected=2006 if out['implementation']=='CMySQLConnection' else 1064
        assert out['syntax_error']['errno']==expected,out
        out['crud_binary_table_and_text_controls']='PASS'
        out['stage']='prepared-call'
        with c.cursor(prepared=True) as q:
            q.execute('CALL test.p5_connector_call(%s)',(7,))
            sets=[]
            while True:
                if q.with_rows:sets.append([[scalar(v) for v in row] for row in q.fetchall()])
                if not q.nextset():break
            assert sets==[[[7]],[[8]]],sets
            out['prepared_call']=sets
        out.update(transaction_binary_values=True,following_query=True,result='PASS')
        out.pop('stage',None)
    return out


def comparable(case):
    return {k:v for k,v in case.items() if k not in ('mode','runtime','logs','temporary_removed','active_connections_after')}


def compare_reference(result,reference):
    assert reference['result']=='PASS'
    expected_names={*MODES,'go'}
    if set(result['cases'])!=expected_names:raise AssertionError('missing consumer mode')
    differences=[]
    for name,c in result['cases'].items():
        if name=='cext' and c.get('result')=='SKIP':continue
        target=name
        if name=='default':
            # The required default call is unmodified. Match the native fixture
            # of its actual selected implementation, never silently force pure.
            target='cext' if c.get('implementation')=='CMySQLConnection' else 'pure'
        if comparable(c)!=comparable(reference['cases'][target]):differences.append(name)
    return differences


def exercise(info=None,host=None,consumer=None):
    result={'scope':'P5 fixed real Go/Python consumers, not full P5 or Qualification','environment':{
        'python':sys.version,'openssl':ssl.OPENSSL_VERSION,'os':platform.system(),'arch':platform.machine()},'cases':{},'failures':{}}
    for mode in (*MODES,'go'):
        db=None;out={}
        try:
            if host:
                import mariamem
                db=mariamem.start(host_binary=str(host));current=db.connection_info()
            else:current=info
            with connection(current) as c:
                version=query(c,'SELECT VERSION()')[0][0]
                assert version.startswith('12.3.3')
                result.setdefault('engine_versions',{})[mode]=version
                assert drained(c)==0
                raw=packet(c,22,b'SELEC invalid')
                assert raw[0]==255 and int.from_bytes(raw[1:3],'little')==1064 and raw[4:9]==b'42000'
                out['raw_syntax']={'errno':1064,'sqlstate':'42000','packet':raw.hex()}
            if mode=='go':
                env=dict(os.environ,MARIAMEM_P5_DSN=f"{current['user']}:{current.get('password','')}@tcp({current['host']}:{current['port']})/{current.get('database','test')}?timeout=5s&readTimeout=15s&writeTimeout=15s")
                r=subprocess.run([str(consumer)],env=env,capture_output=True,text=True,timeout=90)
                out.update(json.loads(r.stdout));out['stderr']=r.stderr
                assert r.returncode==0 and out['result']=='PASS',out
            else:out.update(python_case(current,mode,out))
            if db:
                db.wait_disconnected(timeout=10);out['active_connections_after']=db.status()['active_connections'];assert out['active_connections_after']==0
        except Exception as e:out.update(result='FAIL',error=repr(e))
        finally:
            if db:
                directory=db.log_path.parent
                try:out['logs']=db.logs;db.close();db.close();assert not directory.exists();out['temporary_removed']=True
                except Exception as e:out.update(result='FAIL',cleanup_error=repr(e))
        result['cases'][mode]=out
        if out.get('result') not in ('PASS','SKIP') or (mode!='cext' and out.get('result')!='PASS'):
            result['failures'][mode]=out.get('error',out.get('cleanup_error','required mode did not PASS'))
    result['result']='FAIL' if result['failures'] else 'PASS'
    return result


def main():
    p=argparse.ArgumentParser();g=p.add_mutually_exclusive_group(required=True)
    g.add_argument('--host',type=Path);g.add_argument('--native-port',type=int)
    p.add_argument('--consumer',type=Path,required=True);p.add_argument('--reference',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    r=exercise(info=dict(host='127.0.0.1',port=a.native_port,user='root',database='test') if a.native_port else None,host=a.host,consumer=a.consumer)
    r['consumer_sha256']=hashlib.sha256(a.consumer.read_bytes()).hexdigest()
    if a.reference:
        try:
            r['different_cases']=compare_reference(r,json.loads(a.reference.read_text()))
            if r['different_cases']:r['result']='FAIL'
        except Exception as e:r['reference_error']=repr(e);r['result']='FAIL'
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2)+'\n')
    if r['result']!='PASS':raise SystemExit(1)

if __name__=='__main__':main()
