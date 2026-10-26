"""Native-only control fixtures. No mariamem or live API emulation."""
import contextlib
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time
import uuid
import hashlib
from urllib.request import urlopen

import pytest

HERE=Path(__file__).resolve().parent


def record(event,**fields):
    with Path(os.environ['E2E_EVENTS']).open('a') as f:
        f.write(json.dumps(dict(event=event,**fields))+'\n')


def connection(schema=None):
    import MySQLdb
    return MySQLdb.connect(host=os.environ['E2E_DB_HOST'],port=int(os.environ['E2E_DB_PORT']),
                          user='root',passwd='',db=schema or '',charset='utf8mb4',autocommit=True)


def query(sql,parameters=None,schema=None):
    with contextlib.closing(connection(schema)) as c:
        with c.cursor() as cursor:
            cursor.execute(sql,parameters)
            return cursor.fetchall()


def manage(env,*args):
    subprocess.run([sys.executable,str(HERE/'pythonapp/manage.py'),*args],env=env,check=True,
                   stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=60)


def schema_name(suffix):
    return 'e2e_'+os.environ['E2E_RUN_TOKEN']+'_'+suffix


def prepare_schema(name,env,kind):
    query('CREATE DATABASE `'+name+'` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci')
    if kind=='python':
        manage(env,'migrate','--noinput')
        migrations=query("SELECT name FROM django_migrations WHERE app='orders' ORDER BY name",schema=name)
        assert migrations==(('0001_initial',),('0002_status',))
        record('migration_chain',schema=name,revisions=[r[0] for r in migrations])
    else:
        for sql in (HERE/'goapp/schema.sql').read_text().split(';'):
            if sql.strip():query(sql,schema=name)


def rows(name):
    return [list(row) for row in query('SELECT sku,quantity,status FROM orders_order ORDER BY id',schema=name)]


@contextlib.contextmanager
def server(name,env,kind):
    out=Path(os.environ['E2E_OUTPUT']);path=out/('server-'+name+'-'+uuid.uuid4().hex[:6]+'.txt')
    if kind=='python':
        with socket.socket() as s:
            s.bind(('127.0.0.1',0));port=s.getsockname()[1]
        argv=[sys.executable,str(HERE/'pythonapp/manage.py'),'runserver','--noreload','--nothreading',f'127.0.0.1:{port}']
    else:
        argv=[os.environ['E2E_GO_APP']]
    with path.open('w') as log:
        process=subprocess.Popen(argv,env=env,stdout=log,stderr=log)
        record('app_started',pid=process.pid,kind=kind,schema=name)
        try:
            deadline=time.monotonic()+30
            while True:
                assert process.poll() is None,'app exited: '+path.name
                assert time.monotonic()<deadline,'app startup timeout: '+path.name
                if kind=='go':
                    text=path.read_text().splitlines()
                    if not text:time.sleep(.05);continue
                    port=int(json.loads(text[0])['address'].rsplit(':',1)[1])
                try:
                    with urlopen(f'http://127.0.0.1:{port}/healthz',timeout=.5) as r:health=json.load(r)
                    assert health['pid']==process.pid and health['db_name']==name
                    assert health['db_version'].startswith('12.3.3-MariaDB')
                    break
                except OSError:time.sleep(.05)
            record('app_ready',**health,http_port=port)
            yield f'http://127.0.0.1:{port}',health
        finally:
            if process.poll() is None:process.terminate()
            try:process.wait(timeout=5)
            except subprocess.TimeoutExpired:process.kill();process.wait(timeout=5)
            record('app_reaped',pid=process.pid,reaped=process.poll() is not None,exit_code=process.returncode)


@pytest.fixture(scope='session')
def application():
    kind=os.environ['E2E_KIND'];env=dict(os.environ)
    if kind=='go':yield None;return
    name=schema_name('python');env['E2E_DB_NAME']=name
    try:
        prepare_schema(name,env,kind)
        with server(name,env,kind) as app:yield app,env
    finally:
        query('DROP DATABASE IF EXISTS `'+name+'`')
        assert query('SELECT COUNT(*) FROM information_schema.schemata WHERE schema_name=%s',(name,))==((0,),)
        record('schema_removed',schema=name)


@pytest.fixture(scope='session')
def browser():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b=p.chromium.launch(headless=True)
        candidates=[f for f in Path(os.environ['PLAYWRIGHT_BROWSERS_PATH']).resolve().rglob('*') if f.is_file() and f.name in ['chrome-headless-shell','headless_shell']]
        assert len(candidates)==1,'expected one pinned headless shell'
        record('browser_started',version=b.version,executable=candidates[0].name,
               executable_sha256=hashlib.sha256(candidates[0].read_bytes()).hexdigest())
        try:yield b
        finally:b.close();record('browser_closed')


@pytest.fixture
def browser_page(request,application,browser):
    from playwright.sync_api import expect
    kind=os.environ['E2E_KIND'];name=schema_name(request.node.name.split('_')[1]) if kind=='go' else schema_name('python')
    env=dict(os.environ,E2E_DB_NAME=name)
    with contextlib.ExitStack() as stack:
        if kind=='go':
            # Native control allocates a fresh schema, not a mariamem Fork.
            prepare_schema(name,env,kind)
            def drop():
                query('DROP DATABASE IF EXISTS `'+name+'`');record('schema_removed',schema=name)
            stack.callback(drop)
            env['E2E_MYSQL_DSN']='root@tcp('+env['E2E_DB_HOST']+':'+env['E2E_DB_PORT']+')/'+name+'?charset=utf8mb4&parseTime=true'
            url,health=stack.enter_context(server(name,env,kind))
        else:
            (url,health),env=application
            # Recorded native data reset; this is not a mariamem baseline/reset implementation.
            if os.environ.get('E2E_MUTATE_SKIP_RESET')!='1':
                manage(env,'flush','--noinput')
                manage(env,'seed_baseline')
                record('native_reset',method='Django flush plus seed_baseline',schema=name)
            if os.environ.get('E2E_MUTATE_RESTART_APP')=='1':
                url,health=stack.enter_context(server(name,env,kind))
        baseline_rows=rows(name)
        record('baseline_checked',name=request.node.name,rows=baseline_rows)
        assert baseline_rows==[['SEED',2,'ready']]
        record('case_before',name=request.node.name,pid=health['pid'],http_url=url,schema=name,rows=rows(name))
        ctx=browser.new_context();stack.callback(ctx.close)
        page=ctx.new_page();page.set_default_timeout(10000)
        page.goto(url+'/orders')
        expect(page.get_by_test_id('order')).to_have_text(['SEED:2:ready'])
        try:yield page
        finally:
            record('case_after',name=request.node.name,rows=rows(name))
            if os.environ.get('E2E_RETAIN_SCREENSHOT')=='1':
                page.screenshot(path=str(Path(os.environ['E2E_OUTPUT'])/(request.node.name+'.png')))
