"""R1–R8 against an unchanged real guest; compact per-case evidence."""
import argparse
import asyncio
from concurrent.futures import ThreadPoolExecutor
import contextvars
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import socket
import subprocess
import sys
import threading
import traceback

import mariamem
import pymysql
from pymysql import connect as saved_py_alias
try:
    import mysql.connector as connector
    from mysql.connector import connect as saved_connector_alias
    connector_import_error = None
except (ImportError, AttributeError) as error:
    connector = None
    connector_import_error = repr(error)
from sqlalchemy import create_engine, text, URL
from router import Router, RouteError


def query(conn, sql, args=None):
    with conn.cursor() as cur:
        cur.execute(sql, args)
        return cur.fetchall() if cur.description else ()


def info(db):
    return dict(db.connection_info(), database='app', autocommit=True)


def direct(db):
    return pymysql.connect(**info(db))


class Sentinel:
    def __init__(self):
        self.socket = socket.socket()
        self.socket.bind(('127.0.0.1', 0))
        self.socket.listen()
        self.socket.settimeout(.1)
        self.port = self.socket.getsockname()[1]
        self.attempts = 0
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self.loop)
        self.thread.start()
    def loop(self):
        while not self.stop.is_set():
            try:
                c, _ = self.socket.accept()
            except socket.timeout:
                continue
            self.attempts += 1
            c.close()
    def close(self):
        self.stop.set(); self.thread.join(); self.socket.close()


def expect(code, fn):
    try:
        fn()
    except RouteError as e:
        assert e.code == code, (e.code, code)
        assert 'not-a-real-secret' not in str(e)
        return {'code': e.code, 'stage': e.stage, 'message': str(e)}
    raise AssertionError('Expected rejection: ' + code)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--host', required=True)
    parser.add_argument('--go-consumer', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--mutation', choices=['no_pool_check','fallback','ignore_retired','global_target'])
    args=parser.parse_args()
    result={'system':platform.platform(),'python':sys.version,'mutation':args.mutation,
            'connector_import_error':connector_import_error,'packages':{k:importlib.metadata.version(k) for k in ['PyMySQL','SQLAlchemy','mysql-connector-python']},'cases':[]}
    sentinel=Sentinel()
    original=dict(host='127.0.0.1',port=sentinel.port,user='application',password='not-a-real-secret',database='app',autocommit=True,connect_timeout=2)
    router=Router('127.0.0.1',sentinel.port,mutation=args.mutation)
    dbs=[]; baseline=None
    def case(row, name, fn):
        before=sentinel.attempts
        try:
            detail=fn()
            assert sentinel.attempts==before, 'original endpoint was contacted'
            result['cases'].append(dict(row=row,name=name,status='PASS',detail=detail,sentinel_attempts=sentinel.attempts-before))
        except NotImplementedError as e:
            result['cases'].append(dict(row=row,name=name,status='SKIP',reason=str(e)))
        except BaseException as e:
            result['cases'].append(dict(row=row,name=name,status='FAIL',error_type=type(e).__name__,error=str(e),traceback=traceback.format_exc(),sentinel_attempts=sentinel.attempts-before))
        print(row,name,result['cases'][-1]['status'],flush=True)
    try:
        setup=mariamem.start(host_binary=args.host)
        dbs.append(setup)
        with pymysql.connect(**setup.connection_info(),autocommit=True) as conn:
            query(conn,'CREATE DATABASE app')
            query(conn,'CREATE TABLE app.marker(id INT PRIMARY KEY,value VARCHAR(100))')
            query(conn,"INSERT INTO app.marker VALUES(1,'seed')")
            query(conn,'CREATE TABLE app.writes(value VARCHAR(100))')
        setup.wait_disconnected()
        baseline=setup.snapshot()
        a,b=baseline.fork(),baseline.fork(); dbs.extend([a,b])
        for db,value in [(a,'A'),(b,'B')]:
            with direct(db) as c: query(c,'UPDATE marker SET value=%s WHERE id=1',(value,))
        delayed=saved_py_alias(**original,defer_connect=True)
        url=URL.create('mysql+pymysql',username=original['user'],password=original['password'],host=original['host'],port=original['port'],database='app')
        engine=create_engine(url,pool_size=4,max_overflow=0,pool_timeout=2)
        router.install();router.enroll(engine)
        def marker(c):
            return query(c,'SELECT value FROM app.marker WHERE id=1')[0][0]
        def r1():
            with router.bind(a):
                observed=[]
                for make in [lambda:pymysql.connect(**original),lambda:saved_py_alias(**original)]:
                    with make() as c: observed.append(marker(c))
                delayed.connect();observed.append(marker(delayed));delayed.close()
                delayed.connect();observed.append(marker(delayed));delayed.close()
                with saved_py_alias(**original,defer_connect=True) as c:
                    c.connect();observed.append(marker(c))
                assert observed==['A']*5
                return {'markers':observed,'saved_class_alias':True,'deferred_before_install':True}
        def r2():
            observed=[]
            # Diagnostic held-idle boundary: old physical connection intentionally
            # survives scope retirement to test the generation oracle independently.
            for db in [a,b,a]:
                with router.bind(db,cleanup=False):
                    with engine.connect() as c: observed.append(c.scalar(text('SELECT value FROM marker WHERE id=1')))
            assert observed==['A','B','A'], observed
            return {'markers':observed,'held_idle_diagnostic':True,**router.observations}
        def r3():
            events=[]
            with router.bind(a):
                with engine.connect() as c:
                    tx=c.begin()
                    events.append(expect('active_pool',lambda:router.enroll(engine)))
                    tx.rollback()
            custom_calls=[]
            custom=create_engine(url,creator=lambda:custom_calls.append(1))
            events.append(expect('custom_creator',lambda:router.enroll(custom)));custom.dispose()
            assert not custom_calls
            unknown=create_engine(URL.create('mysql+pymysql',**{k:info(a)[k] for k in ['host','port','database']}))
            events.append(expect('unknown_profile',lambda:router.enroll(unknown)));unknown.dispose()
            return events
        def parallel():
            barrier=threading.Barrier(2)
            def worker(db,expected):
                observed=[]
                with router.bind(db):
                    barrier.wait(timeout=5)
                    for _ in range(3):
                        with engine.begin() as c:
                            observed.append(c.scalar(text('SELECT value FROM marker WHERE id=1')))
                            c.execute(text('INSERT INTO writes(value) VALUES (:v)'),{'v':expected+'-thread'})
                    barrier.wait(timeout=5)
                assert observed==[expected]*3, observed
                return observed
            with ThreadPoolExecutor(2) as ex:
                futures=[ex.submit(worker,db,expected) for db,expected in [(a,'A'),(b,'B')]]
                observed = [f.result(timeout=15) for f in futures]
            for db,other in [(a,'B-thread'),(b,'A-thread')]:
                with direct(db) as c: assert query(c,'SELECT COUNT(*) FROM writes WHERE value=%s',(other,))[0][0]==0
            return observed
        def r4_context():
            observed=[]
            with router.bind(a):
                with saved_py_alias(**original) as c: observed.append(marker(c))
                with router.bind(b):
                    with saved_py_alias(**original) as c: observed.append(marker(c))
                with saved_py_alias(**original) as c: observed.append(marker(c))
                ctx=contextvars.copy_context()
                def from_thread():
                    with saved_py_alias(**original) as c:return marker(c)
                with ThreadPoolExecutor(1) as ex:
                    observed.append(ex.submit(ctx.run,from_thread).result())
                    missing=ex.submit(lambda:expect('missing_target',from_thread)).result()
            assert observed==['A','B','A','A']
            return {'markers':observed,'unpropagated':missing}
        def r4_async():
            async def task(db,expected):
                with router.bind(db):
                    await asyncio.sleep(0)
                    with saved_py_alias(**original) as c: value=marker(c)
                    assert value==expected
                    await asyncio.sleep(0)
                    return value
            async def run():return await asyncio.gather(task(a,'A'),task(b,'B'))
            return {'markers':asyncio.run(run()),'note':'sync DBAPI in asyncio tasks; no async driver claim'}
        def retired():
            with router.bind(a):ctx=contextvars.copy_context()
            def delayed_call():
                with saved_py_alias(**original) as c:return marker(c)
            return ctx.run(lambda:expect('expired_target',delayed_call))
        def r5_failures():
            details=[]
            class CleanupBroken:
                def close(self):raise OSError('injected close failure')
            for stage in ['setup','test','cleanup']:
                try:
                    with router.bind(a) as lease:
                        c=saved_py_alias(**original);assert marker(c)=='A'
                        if stage=='cleanup':lease.connections.append(CleanupBroken())
                        raise ValueError(stage+' original')
                except ValueError as e:
                    assert str(e)==stage+' original'
                    if stage=='cleanup':assert 'routing cleanup also failed' in e.__notes__[0]
                    details.append({'stage':stage,'preserved':str(e),'notes':getattr(e,'__notes__',[])})
                assert router.current.get() is None
            with router.bind(a):
                try:
                    with router.bind(b):raise ValueError('nested setup')
                except ValueError:pass
                with saved_py_alias(**original) as c:assert marker(c)=='A'
            closing=baseline.fork();dbs.append(closing)
            with router.bind(closing):
                closing.close()
                details.append(expect('closed_target',lambda:saved_py_alias(**original)))
            return details
        def no_target():return expect('missing_target',lambda:saved_py_alias(**original))
        def r6():
            rejected=[]
            with router.bind(a):
                for opts,code in [({'unix_socket':'/not-used.sock'},'transport_conflict'),({'read_default_file':'/not-read.cnf'},'option_file'),({'ssl':{'check_hostname':False}},'tls_unavailable')]:
                    rejected.append(expect(code,lambda opts=opts:saved_py_alias(**dict(original,**opts))))
                if connector:
                    rejected.append(expect('unsupported_factory',lambda:connector.connect(**{k:v for k,v in dict(original,option_files='/not-read.cnf').items() if k!='connect_timeout'})))
                with saved_py_alias(**dict(original,charset='utf8mb4',autocommit=False)) as c:
                    actual=query(c,'SELECT DATABASE(),@@autocommit,@@character_set_connection')[0]
                    assert actual==('app',0,'utf8mb4'), actual
                    assert marker(c)=='A'
                    query(c,'INSERT INTO writes(value) VALUES (%s)',('rollback-python',));c.rollback()
                    assert query(c,"SELECT COUNT(*) FROM writes WHERE value='rollback-python'")[0][0]==0
            return {'rejections':rejected,'settings':actual}
        def r7_python():
            if connector is None: raise NotImplementedError(connector_import_error)
            modes=[]
            for label,extra in [('default',{}),('pure',{'use_pure':True})]+([('c',{'use_pure':False})] if connector.HAVE_CEXT else []):
                kw={k:v for k,v in original.items() if k!='connect_timeout'}
                with router.bind(b):
                    c=saved_connector_alias(**kw,**extra)
                    try:
                        cur=c.cursor(prepared=True);cur.execute('SELECT value FROM marker WHERE id=%s',(1,));value=cur.fetchone()[0]
                        if isinstance(value,bytes):value=value.decode()
                        assert value=='B',value
                        cur.close();c.autocommit=False
                        cur=c.cursor(prepared=True);cur.execute('INSERT INTO writes(value) VALUES (%s)',('connector-rollback',));c.rollback();cur.close()
                        cur=c.cursor(prepared=True);cur.execute('SELECT COUNT(*) FROM writes WHERE value=%s',('connector-rollback',));assert cur.fetchone()[0]==0;cur.close()
                        cur=c.cursor(prepared=True);cur.execute('INSERT INTO writes(value) VALUES (%s)',('connector-commit-'+label,));c.commit();cur.close()
                        cur=c.cursor(prepared=True);cur.execute('SELECT COUNT(*) FROM writes WHERE value=%s',('connector-commit-'+label,));assert cur.fetchone()[0]==1;cur.close()
                        modes.append({'mode':label,'actual_class':type(c).__name__,'marker':value,'prepared':True,'rollback':True,'commit':True})
                    finally:c.close()
            if not connector.HAVE_CEXT:
                modes.append({'mode':'c','status':'SKIP','reason':'explicit C extension unavailable; default/pure executed'})
            return modes
        def r7_go():
            dsns=[]
            for db,value in [(a,'A'),(b,'B')]:
                x=info(db);dsns.extend([f"{x['user']}:{x['password']}@tcp({x['host']}:{x['port']})/app?parseTime=true",value])
            p=subprocess.run([args.go_consumer,*dsns],capture_output=True,text=True,timeout=30)
            assert p.returncode==0,p.stderr
            return json.loads(p.stdout)
        def r8():
            observed=[]
            for mode in ['injection','routing']:
                left,right=baseline.fork(),baseline.fork();dbs.extend([left,right])
                for db in [left,right]:
                    if mode=='injection':
                        with direct(db) as c:
                            value=marker(c);query(c,'INSERT INTO writes(value) VALUES (%s)',('new-test',))
                    else:
                        with router.bind(db):
                            with saved_py_alias(**original) as c:
                                value=marker(c);query(c,'INSERT INTO writes(value) VALUES (%s)',('new-test',))
                    assert value=='seed'
                    with direct(db) as c: assert query(c,'SELECT COUNT(*) FROM writes')[0][0]==1
                    observed.append({'mode':mode,'marker':value,'own_rows':1})
                left.wait_disconnected();right.wait_disconnected();left.close();right.close()
            return {'children':observed,'prepared_once':True,'first_test':'define preparation and binding fixture','second_test':'reuse fixture; add assertions only'}
        if args.mutation:
            selected={'no_pool_check':('R2','idle-generation',r2),'fallback':('R5','missing-target',no_target),'ignore_retired':('R5','retired-context',retired),'global_target':('R4','parallel-targets',parallel)}[args.mutation]
            case(*selected)
        else:
            for entry in [('R1','direct-alias-deferred-reconnect',r1),('R2','idle-generation',r2),('R3','registration-rejections',r3),('R4','parallel-targets',parallel),('R4','nested-thread-context',r4_context),('R4','async-task-context',r4_async),('R5','retired-context',retired),('R5','failure-cleanup',r5_failures),('R5','missing-target',no_target),('R6','options-and-schema',r6),('R7','connector-prepared',r7_python),('R7','go-owned-pools',r7_go),('R8','two-test-workflows',r8)]:case(*entry)
    except BaseException as e:
        result['fatal']={'type':type(e).__name__,'message':str(e),'traceback':traceback.format_exc()}
    finally:
        try:router.uninstall()
        except BaseException as e:result['uninstall_error']=repr(e)
        if baseline:baseline.close()
        for db in reversed(dbs):
            try:db.close()
            except BaseException as e:result.setdefault('close_errors',[]).append(repr(e))
        sentinel.close()
        result['sentinel_attempts']=sentinel.attempts
        result['observations']=router.observations
        result['all_hosts_reaped']=all(db._session._reaped.is_set() for db in dbs if db._session)
        result['passed']=not result.get('fatal') and not result.get('close_errors') and not result.get('uninstall_error') and all(x['status']=='PASS' for x in result['cases']) and result['all_hosts_reaped']
        Path(args.output).write_text(json.dumps(result,indent=2)+'\n')
    return 0 if result['passed'] else 1

if __name__=='__main__':sys.exit(main())
