"""Real canonical-guest text chaining; binary prepared scope remains separate."""
import os
import mariamem
import pymysql
from pymysql.constants import CLIENT
import pytest

HOST=os.environ.get('MARIAMEM_TEST_HOST')
pytestmark=pytest.mark.skipif(not HOST,reason='requires explicit canonical candidate host')

def connection(db, flags=0):
    return pymysql.connect(**db.connection_info(),autocommit=True,
                           client_flag=flags,read_timeout=30)

def test_mixed_chain_error_reuse_and_rollback():
    with mariamem.start(host_binary=HOST) as db, connection(db,CLIENT.MULTI_STATEMENTS) as c:
        q=c.cursor();q.execute('CREATE TABLE text_multi(id INT PRIMARY KEY,value INT) ENGINE=InnoDB')
        q.execute('INSERT INTO text_multi VALUES(1,10); SELECT value FROM text_multi; UPDATE text_multi SET value=11 WHERE id=1; SELECT value FROM text_multi')
        results=[];states=[]
        while True:
            results.append((q.fetchall() if q.description else None,q.rowcount))
            states.append(int(q._result.has_next or 0))
            if not q.nextset():break
        assert results==[(None,1),(((10,),),1),(None,1),(((11,),),1)]
        assert all(s&8 for s in states[:-1]) and not states[-1]&8
        q.execute('SELECT 101; SELECT * FROM missing_text_multi; INSERT INTO text_multi VALUES(2,20)')
        assert q.fetchall()==((101,),)
        with pytest.raises(pymysql.MySQLError) as error:q.nextset()
        assert error.value.args[0]==1146
        q.execute('SELECT COUNT(*) FROM text_multi');assert q.fetchone()==(1,)
        with pytest.raises(pymysql.MySQLError) as error:q.execute('SELEC broken; SELECT 2')
        assert error.value.args[0]==1064
        c.autocommit(False)
        q.execute('INSERT INTO text_multi VALUES(3,30); SELECT COUNT(*) FROM text_multi')
        assert q.rowcount==1 and q.nextset() and q.fetchone()==(2,) and not q.nextset()
        c.rollback();q.execute('SELECT COUNT(*) FROM text_multi');assert q.fetchone()==(1,)


def test_unflagged_session_rejects_multiple_statements():
    with mariamem.start(host_binary=HOST) as db, connection(db) as c:
        q=c.cursor()
        with pytest.raises(pymysql.MySQLError) as error:q.execute('SELECT 1; SELECT 2')
        assert error.value.args[0]==1064
        q.execute('SELECT 3');assert q.fetchone()==(3,)


def test_text_option_toggle_errors_and_stable_connection():
    with mariamem.start(host_binary=HOST) as db, connection(db) as c:
        q=c.cursor();q.execute('SELECT CONNECTION_ID()');before=q.fetchone()[0]
        c._execute_command(27,b'\x00\x00');assert c._read_packet().is_eof_packet()
        q.execute('SELECT 41; SELECT 42');assert q.fetchone()==(41,) and q.nextset() and q.fetchone()==(42,) and not q.nextset()
        c._execute_command(27,b'\x01\x00');assert c._read_packet().is_eof_packet()
        with pytest.raises(pymysql.MySQLError) as error:q.execute('SELECT 41; SELECT 42')
        assert error.value.args[0]==1064
        for payload,errno in [(b'\xff\xff',1047),(b'',1235),(b'\x00',1235),(b'\x00\x00\x00',1235)]:
            c._execute_command(27,payload)
            with pytest.raises(pymysql.MySQLError) as error:c._read_packet()
            assert error.value.args[0]==errno
        q.execute('SELECT CONNECTION_ID()');assert q.fetchone()==(before,)


def test_call_beyond_experimental_result_count_limit():
    with mariamem.start(host_binary=HOST) as db, connection(db) as c:
        q=c.cursor()
        q.execute('CREATE PROCEDURE test.many_results() BEGIN '+''.join(f'SELECT {i};' for i in range(129))+' END')
        q.execute('CALL test.many_results()');rows=[]
        while True:
            rows.append(q.fetchall() if q.description else None)
            if not q.nextset():break
        assert rows==[((i,),) for i in range(129)]+[None]
        q.execute('SELECT 9');assert q.fetchone()==(9,)


@pytest.mark.parametrize('found',[False,True])
def test_found_rows_and_multi_flags_remain_independent(found):
    with mariamem.start(host_binary=HOST) as db, connection(db,CLIENT.MULTI_STATEMENTS|(CLIENT.FOUND_ROWS if found else 0)) as c:
        q=c.cursor();q.execute('CREATE TABLE text_found(id INT PRIMARY KEY) ENGINE=InnoDB')
        q.execute('INSERT INTO text_found VALUES(1)');q.execute('UPDATE text_found SET id=1 WHERE id=1')
        assert q.rowcount==int(found)


def test_binary_prepare_is_not_silently_adopted():
    with mariamem.start(host_binary=HOST) as db, connection(db) as c:
        c._execute_command(22,b'SELECT ?')
        with pytest.raises(pymysql.MySQLError) as error:c._read_packet()
        assert error.value.args[0]==1235
        q=c.cursor();q.execute('SELECT 43');assert q.fetchone()==(43,)
