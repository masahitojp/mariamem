"""Unchanged six-case native-compared routine SQL oracle."""
import time
import pymysql

def execute(cursor, sql):
    sets = []
    cursor.execute(sql)
    while True:
        sets.append(dict(rows=cursor.fetchall() if cursor.description else None,
                         columns=[d[0] for d in cursor.description] if cursor.description else [],
                         affected=cursor.rowcount,
                         more=int(cursor._result.has_next or 0)))
        if not cursor.nextset(): break
    return sets


def safe(cursor, sql):
    start = time.perf_counter()
    try:
        return dict(sql=sql, result='PASS', sets=execute(cursor, sql),
                    elapsed_ms=(time.perf_counter()-start)*1000)
    except pymysql.MySQLError as e:
        return dict(sql=sql, result='FAIL', errno=e.args[0], error=str(e),
                    elapsed_ms=(time.perf_counter()-start)*1000)


def routines(cursor):
    cases = []
    def case(name, body):
        try:
            result = body()
            cases.append(dict(case=name, result='PASS', detail=result))
        except Exception as e:
            cases.append(dict(case=name, result='FAIL', error=repr(e)))
    def query(sql): return execute(cursor, sql)
    def simple():
        query('DROP PROCEDURE IF EXISTS test.feas_simple')
        query('CREATE PROCEDURE test.feas_simple() SELECT 7 AS value')
        got = query('CALL test.feas_simple()')
        assert got[0]['rows'] == ((7,),) and got[-1]['rows'] is None, got
        query('DROP PROCEDURE test.feas_simple'); return got
    case('procedure-create-call-drop', simple)
    def parameters():
        query('DROP PROCEDURE IF EXISTS test.feas_args')
        query('CREATE PROCEDURE test.feas_args(IN a INT, OUT b INT, INOUT c INT) BEGIN SET b=a*2; SET c=c+a; END')
        query('SET @out=NULL, @inout=10'); query('CALL test.feas_args(3,@out,@inout)')
        got = query('SELECT @out, @inout')[0]['rows']
        assert got == ((6,13),), got
        query('DROP PROCEDURE test.feas_args'); return got
    case('in-out-inout', parameters)
    def multiple():
        query('DROP PROCEDURE IF EXISTS test.feas_multi')
        query('CREATE PROCEDURE test.feas_multi() BEGIN SELECT 7 AS a; SELECT 8 AS b; END')
        got=query('CALL test.feas_multi()')
        assert [s['rows'] for s in got] == [((7,),),((8,),),None], got
        assert all(s['more'] & 8 for s in got[:-1]) and not got[-1]['more'] & 8, got
        query('DROP PROCEDURE test.feas_multi'); return got
    case('multiple-results-terminal-ok', multiple)
    def function():
        query('DROP FUNCTION IF EXISTS test.feas_function')
        query('CREATE FUNCTION test.feas_function(a INT) RETURNS INT DETERMINISTIC RETURN a+1')
        got = query('SELECT test.feas_function(4), test.feas_function(NULL)')[0]['rows']
        assert got == ((5,None),), got
        query('DROP FUNCTION test.feas_function'); return got
    case('function-create-invoke-drop-null', function)
    def metadata():
        query('DROP PROCEDURE IF EXISTS test.feas_metadata')
        query('CREATE PROCEDURE test.feas_metadata(IN a INT, OUT b INT) SET b=a')
        r=query("SELECT ROUTINE_TYPE FROM information_schema.ROUTINES WHERE ROUTINE_SCHEMA='test' AND ROUTINE_NAME='feas_metadata'")[0]['rows']
        p=query("SELECT ORDINAL_POSITION, PARAMETER_MODE, PARAMETER_NAME FROM information_schema.PARAMETERS WHERE SPECIFIC_SCHEMA='test' AND SPECIFIC_NAME='feas_metadata' ORDER BY ORDINAL_POSITION")[0]['rows']
        assert r == (('PROCEDURE',),), r
        assert p == ((1,'IN','a'),(2,'OUT','b')), p
        query('DROP PROCEDURE test.feas_metadata')
        return dict(routines=r,parameters=p)
    case('information-schema-routine-and-parameters', metadata)
    def errors():
        query('DROP PROCEDURE IF EXISTS test.feas_error')
        query("CREATE PROCEDURE test.feas_error() BEGIN SELECT 1 AS before_error; SIGNAL SQLSTATE '45000' SET MESSAGE_TEXT='spike expected error'; END")
        cursor.execute('CALL test.feas_error()')
        assert cursor.fetchall() == ((1,),)
        try: cursor.nextset()
        except pymysql.MySQLError as e: assert e.args[0] == 1644, e
        else: raise AssertionError('SIGNAL error missing')
        assert query('SELECT 9')[0]['rows'] == ((9,),)
        query('DROP PROCEDURE test.feas_error')
        missing = safe(cursor, 'CALL test.feas_error()')
        assert missing.get('errno') == 1305, missing
        return dict(signal_errno=1644, after_drop=missing, reused=True)
    case('later-error-reuse-and-after-drop', errors)
    return cases
