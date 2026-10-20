"""SQL-only routine feasibility probe; no runtime or generated-source edits."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import time

import pymysql
from pymysql.constants import CLIENT


def statements(text):
    """mysql-client delimiter handling, with quotes and comments kept distinct.

    DELIMITER is a client directive, not SQL. No rewriting of server statements.
    Used only for the fixed upstream base/fix scripts (not a product importer).
    """
    delimiter = ';'
    pending = []
    quote = None
    block = False
    for line in text.splitlines(keepends=True):
        if not quote and not block and re.match(r'^\s*DELIMITER\s+', line, re.I):
            assert not ''.join(pending).strip(), ''.join(pending)[-100:]
            delimiter = line.split()[1]
            continue
        i = 0
        while i < len(line):
            c = line[i]
            if block:
                if line.startswith('*/', i):
                    block = False
                    pending.append(' ')
                    i += 2
                else:
                    i += 1
                continue
            if quote:
                pending.append(c)
                if c == '\\' and i + 1 < len(line):
                    pending.append(line[i+1]); i += 2; continue
                if c == quote:
                    if i + 1 < len(line) and line[i+1] == quote:
                        pending.append(line[i+1]); i += 2; continue
                    quote = None
                i += 1
                continue
            if line.startswith('/*', i):
                # These pinned scripts contain plain comments only.
                assert not line.startswith(('/*!', '/*M!'), i)
                block = True; i += 2; continue
            if c == '#' or (line.startswith('--', i) and
                            (i+2 == len(line) or line[i+2].isspace())):
                pending.append('\n'); break
            if c in "'\"`":
                quote = c; pending.append(c); i += 1; continue
            if line.startswith(delimiter, i):
                sql = ''.join(pending).strip(); pending = []
                if sql: yield sql
                i += len(delimiter); continue
            pending.append(c); i += 1
    assert not quote and not block
    assert not ''.join(pending).strip(), ''.join(pending)[-100:]


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


def run(a):
    result = dict(mode=a.mode, port=a.port, scripts={}, stages=[])
    db = None
    if a.host:
        import mariamem
        start=time.perf_counter(); db=mariamem.start(host_binary=a.host, log_path=a.output.with_suffix('.guest.log'))
        result['start_ms']=(time.perf_counter()-start)*1000
        args=db.connection_info(); result['guest_identity']=db._session.guest_identity
    else:
        args=dict(host='127.0.0.1', port=a.port, user='root', database='test')
    try:
        with pymysql.connect(**args, autocommit=True, client_flag=CLIENT.MULTI_RESULTS,
                             read_timeout=120, write_timeout=30) as conn:
            q=conn.cursor()
            result['identity']=safe(q,'SELECT VERSION(), @@version_comment, @@sql_mode, @@skip_grant_tables')
            result['before']=[safe(q,s) for s in ('SHOW DATABASES','SHOW TABLES FROM mysql',
                'SELECT COUNT(*) FROM information_schema.ROUTINES',
                'SELECT COUNT(*) FROM information_schema.PARAMETERS',
                'SELECT COUNT(*) FROM information_schema.USERS',
                'CREATE PROCEDURE test.feas_before() SELECT 1')]
            source=a.source/'scripts'
            base=list(statements((source/'mariadb_system_tables.sql').read_text()))
            fix=list(statements((source/'mariadb_system_tables_fix.sql').read_text()))
            for name,sqls in [('base',base),('fix',fix)]:
                result['scripts'][name]=dict(count=len(sqls),sha256=hashlib.sha256((source/('mariadb_system_tables'+('_fix' if name=='fix' else '')+'.sql')).read_bytes()).hexdigest())
            if a.mode == 'baseline':
                result['routines']=routines(q)
            else:
                result['setup']=[safe(q,'CREATE DATABASE IF NOT EXISTS mysql'),safe(q,'USE mysql'),safe(q,"SET sql_mode=''"),safe(q,'SET @auth_root_socket=NULL')]
                if a.mode in ('proc-only','damaged-proc'):
                    ddl=next(s for s in base if s.startswith('CREATE TABLE IF NOT EXISTS proc ('))
                    result['stages'].append(dict(stage='official-base-proc', steps=[safe(q,ddl)]))
                    if a.mode == 'damaged-proc':
                        result['stages'].append(dict(stage='controlled-wrong-nullability',steps=[safe(q,"ALTER TABLE mysql.proc MODIFY comment text COLLATE utf8mb3_bin NULL"),safe(q,'CREATE PROCEDURE test.feas_bad_definition() SELECT 1')]))
                    result['proc_ddl']=safe(q,'SHOW CREATE TABLE mysql.proc')
                    result['routines']=routines(q)
                    if db: result['before_fix_logs']=db.logs
                    if a.mode == 'damaged-proc':
                        result['stages'].append(dict(stage='restore-official-nullability',steps=[safe(q,"ALTER TABLE mysql.proc MODIFY comment text COLLATE utf8mb3_bin NOT NULL")]))
                        result['after_repair']=routines(q)
                else:
                    for name, sqls in [('base',base),('fix',fix)]:
                        start=time.perf_counter(); steps=[safe(q,s) for s in sqls]
                        result['stages'].append(dict(stage=name,elapsed_ms=(time.perf_counter()-start)*1000,steps=steps))
                        result[name+'_proc_ddl']=safe(q,'SHOW CREATE TABLE mysql.proc')
                        result[name+'_routines']=routines(q)
                    result['routines']=result['fix_routines']
                result['after']=[safe(q,s) for s in ('SHOW TABLES FROM mysql','SELECT ROUTINE_NAME, ROUTINE_TYPE FROM information_schema.ROUTINES', 'SELECT COUNT(*) FROM information_schema.PARAMETERS')]
            result['events']=safe(q,'CREATE EVENT test.feas_event ON SCHEDULE EVERY 1 DAY DO SELECT 1')
            if db: result['guest_logs']=db.logs
    finally:
        if db:
            result['final_guest_logs']=db.logs
            start=time.perf_counter();db.close();result['close_ms']=(time.perf_counter()-start)*1000
        a.output.parent.mkdir(parents=True,exist_ok=True)
        a.output.write_text(json.dumps(result,indent=2,ensure_ascii=False,default=str)+'\n')


if __name__ == '__main__':
    p=argparse.ArgumentParser();p.add_argument('--host');p.add_argument('--port',type=int,default=57019)
    p.add_argument('--mode',choices=['baseline','proc-only','damaged-proc','base-fix'],required=True)
    p.add_argument('--source',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    run(p.parse_args())
