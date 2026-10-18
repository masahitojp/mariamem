"""Bounded multi-result native/guest comparison. No SQL splitting or fallback."""
import argparse,json,sys
from pathlib import Path
import mysql.connector,pymysql
from pymysql.constants import CLIENT


def run(port):
    records=[]
    def record(name,fn):
        try:records.append(dict(case=name,result='PASS',detail=fn()))
        except Exception as e:records.append(dict(case=name,result='FAIL',error=repr(e)))
    def raw_chain():
        with pymysql.connect(host='127.0.0.1',port=port,user='root',database='test',client_flag=CLIENT.MULTI_STATEMENTS,autocommit=True,read_timeout=15) as c:
            q=c.cursor();q.execute('DROP TABLE IF EXISTS spike_multi');q.execute('CREATE TABLE spike_multi(id INT PRIMARY KEY, value INT) ENGINE=InnoDB')
            q.execute('INSERT INTO spike_multi VALUES(1,10); SELECT value FROM spike_multi; UPDATE spike_multi SET value=11 WHERE id=1; SELECT value FROM spike_multi')
            got=[];states=[]
            while True:
                got.append(dict(rows=q.fetchall() if q.description else None,affected=q.rowcount));states.append(c.server_status)
                if not q.nextset():break
            assert got==[dict(rows=None,affected=1),dict(rows=((10,),),affected=1),dict(rows=None,affected=1),dict(rows=((11,),),affected=1)],got
            assert all(s&8 for s in states[:-1]) and not(states[-1]&8),states
            q.execute('SELECT 101; SELECT * FROM missing_spike_table; INSERT INTO spike_multi VALUES(2,20)')
            assert q.fetchall()==((101,),)
            try:q.nextset()
            except pymysql.MySQLError as e:assert e.args[0]==1146,e
            else:raise AssertionError('missing middle statement error')
            q.execute('SELECT COUNT(*) FROM spike_multi');assert q.fetchone()==(1,)
            try:q.execute('SELEC broken; SELECT 2')
            except pymysql.MySQLError as e:assert e.args[0]==1064,e
            else:raise AssertionError('missing first statement error')
            q.execute('SELECT 1');assert q.fetchone()==(1,)
            c.autocommit(False)
            q.execute('INSERT INTO spike_multi VALUES(3,30); SELECT COUNT(*) FROM spike_multi')
            assert q.rowcount==1;assert q.nextset();assert q.fetchone()==(2,);assert not q.nextset();c.rollback()
            q.execute('SELECT COUNT(*) FROM spike_multi');assert q.fetchone()==(1,)
            return dict(results=got,statuses=states,middle_error=1146,first_error=1064,reused=True,rollback=True)
    record('raw-single-packet-mixed-results-error-reuse-rollback',raw_chain)
    def unflagged():
        with pymysql.connect(host='127.0.0.1',port=port,user='root',database='test',autocommit=True,read_timeout=15) as c:
            q=c.cursor()
            try:q.execute('SELECT 1; SELECT 2')
            except pymysql.MySQLError as e:assert e.args[0]==1064,e
            else:raise AssertionError('unnegotiated multi statement accepted')
            q.execute('SELECT 3');assert q.fetchone()==(3,);return dict(errno=1064,reused=True)
    record('unflagged-still-single-statement',unflagged)
    for pure in (True,False):
        def consumer(pure=pure):
            # Deliberately no client_flags / ssl / interpolation override.
            with mysql.connector.connect(host='127.0.0.1',port=port,user='root',database='test',use_pure=pure,autocommit=True,connection_timeout=10,read_timeout=15) as c:
                q=c.cursor();q.execute('SELECT 11; SELECT 22');rows=[q.fetchall()]
                while q.nextset():rows.append(q.fetchall())
                assert rows==[[(11,)],[(22,)]],rows
                q.close();p=c.cursor(prepared=True);p.execute('SELECT ?, ?, ?',(-7,'日本語',None));assert p.fetchone()==(-7,'日本語',None);p.close()
                q=c.cursor();q.execute('SELECT 44');assert q.fetchone()==(44,);q.close()
                return dict(rows=rows,prepared_after_multi=True,connection_after_close=True)
        record('connector-default-multi-then-prepared-'+('pure' if pure else 'cext'),consumer)
    return records

p=argparse.ArgumentParser();p.add_argument('--port',type=int);p.add_argument('--host');p.add_argument('--output',required=True);a=p.parse_args()
if a.host:
 import mariamem
 with mariamem.start(host_binary=a.host) as db:results=run(db.connection_info()['port'])
else:results=run(a.port)
Path(a.output).write_text(json.dumps(results,indent=2)+'\n');print(json.dumps(results,indent=2));sys.exit(any(x['result']=='FAIL' for x in results))
