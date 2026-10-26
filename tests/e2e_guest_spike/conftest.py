"""Test-only consumer of existing SDK; business apps/browser assertions unchanged."""
import contextlib
import importlib.util
import json
import os
from pathlib import Path
import socket
import sys
import threading
import time

import pytest

HERE=Path(__file__).resolve().parent
NATIVE=HERE.parent/'e2e_native_control'
sys.path.insert(0,str(HERE))
from live import LiveRelay,LiveBusy,LiveFailed
spec=importlib.util.spec_from_file_location('native_fixture',NATIVE/'conftest.py')
native=importlib.util.module_from_spec(spec);spec.loader.exec_module(native)
record=native.record
SCHEMA='e2e_app'


def info_env(info):
    return dict(os.environ,E2E_DB_HOST=info['host'],E2E_DB_PORT=str(info['port']),E2E_DB_NAME=SCHEMA,
                PYTHONUNBUFFERED='1',E2E_CHILD_DIAGNOSTICS='1',
                PYTHONPATH=os.pathsep.join([str(HERE/'diagnostics'),os.environ.get('PYTHONPATH','')]))


def connect(info):
    import MySQLdb
    return MySQLdb.connect(host=info['host'],port=info['port'],user=info['user'],passwd=info['password'],
                          db=SCHEMA,charset='utf8mb4',autocommit=True,connect_timeout=2)


def query(info,sql,params=None):
    with contextlib.closing(connect(info)) as connection:
        with connection.cursor() as cursor:
            cursor.execute(sql,params);return cursor.fetchall()


def rows(info):
    return [list(r) for r in query(info,'SELECT sku,quantity,status FROM orders_order ORDER BY id')]


@contextlib.contextmanager
def baseline(kind):
    if kind=='go':
        from go_provider import GoOwner
        owner=GoOwner(record)
        try:yield owner
        finally:owner.close()
        return
    import mariamem
    source=mariamem.start(host_binary=os.environ['E2E_GUEST_HOST'],startup_timeout=60)
    session=source._session;snapshot=None
    try:
        info=source.connection_info()
        import MySQLdb
        with contextlib.closing(MySQLdb.connect(host=info['host'],port=info['port'],user='root',db=info['database'],autocommit=True)) as c:
            with c.cursor() as cursor:cursor.execute('CREATE DATABASE '+SCHEMA+' CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci')
        if kind=='python':
            native.manage(info_env(info),'migrate','--noinput')
            revisions=query(info,"SELECT name FROM django_migrations WHERE app='orders' ORDER BY name")
            assert revisions==(('0001_initial',),('0002_status',))
            record('migration_chain',revisions=[r[0] for r in revisions])
        else:
            for sql in (NATIVE/'goapp/schema.sql').read_text().split(';'):
                if sql.strip():query(info,sql)
        assert rows(info)==[['SEED',2,'ready']]
        source.wait_disconnected()
        snapshot=source.snapshot()
        assert source.closed
        record('baseline_captured',kind=kind,source_consumed=True)
        yield snapshot
    finally:
        if snapshot is not None:snapshot.close()
        source.close()
        reaped=session._process.poll() is not None;removed=not session.root.exists()
        record('guest_host_cleanup',reaped=reaped,directory_removed=removed)
        assert reaped and removed


@pytest.fixture(scope='session')
def lineage():
    with baseline(os.environ['E2E_KIND']) as saved:yield saved


@pytest.fixture(scope='session')
def application(lineage):
    if os.environ['E2E_KIND']=='go':yield None;return
    relay=LiveRelay(lineage.fork,record)
    try:
        info=relay.backend.connection_info();info['port']=relay.port
        env=info_env(info)
        with native.server(SCHEMA,env,'python') as app:yield app,relay,env
    finally:relay.close()


@pytest.fixture(scope='session')
def browser():
    # Reuse the exact native browser acquisition/identity/closure implementation.
    yield from native.browser.__wrapped__()


@pytest.fixture
def browser_page(request,lineage,application,browser):
    from playwright.sync_api import expect
    kind=os.environ['E2E_KIND']
    with contextlib.ExitStack() as stack:
        if kind=='go':
            child=lineage.fork()
            def close():
                child.wait_disconnected();child.close()
                record('guest_child_closed',child_id=child.id,closed=child.closed)
            stack.callback(close)
            info=child.connection_info();env=info_env(info)
            env['E2E_MYSQL_DSN']='root@tcp('+info['host']+':'+str(info['port'])+')/'+SCHEMA+'?charset=utf8mb4&parseTime=true'
            record('guest_child',child_id=child.id,backend_port=info['port'])
            url,health=stack.enter_context(native.server(SCHEMA,env,'go'))
        else:
            (url,health),relay,env=application
            if os.environ.get('E2E_MUTATE_SKIP_RESET')!='1':relay.reset(timeout=5)
            assert relay.state=='ready','no test admission while relay failed'
            info=relay.backend.connection_info()
            if os.environ.get('E2E_MUTATE_RESTART_APP')=='1':url,health=stack.enter_context(native.server(SCHEMA,env,'python'))
        actual=rows(info);record('baseline_checked',name=request.node.name,rows=actual)
        assert actual==[['SEED',2,'ready']]
        record('case_before',name=request.node.name,pid=health['pid'],http_url=url,schema=SCHEMA,rows=actual,
               child_id=(child.id if kind=='go' else relay.backend.id),
               db_port=(info['port'] if kind=='go' else relay.port))
        context=browser.new_context();stack.callback(context.close)
        page=context.new_page();page.set_default_timeout(10000)
        page.goto(url+'/orders')
        expect(page.get_by_test_id('order')).to_have_text(['SEED:2:ready'])
        try:yield page
        finally:record('case_after',name=request.node.name,rows=rows(info))


@pytest.fixture
def isolated_live():
    with baseline('python') as saved:
        relay=LiveRelay(saved.fork,record)
        try:yield relay,saved
        finally:relay.close()
