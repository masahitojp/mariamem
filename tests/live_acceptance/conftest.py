"""Real public Go/Python Live and unchanged native business/browser inputs."""
import contextlib
import importlib.util
import os
from pathlib import Path
import sys

import pytest

HERE=Path(__file__).resolve().parent
NATIVE=HERE.parent/'e2e_native_control'
sys.path.insert(0,str(HERE))
spec=importlib.util.spec_from_file_location('native_live_helpers',NATIVE/'conftest.py')
native=importlib.util.module_from_spec(spec);spec.loader.exec_module(native)
record=native.record
SCHEMA='e2e_app'


def info_env(info):
    diagnostics=HERE/'diagnostics'
    return dict(os.environ,E2E_DB_HOST=info['host'],E2E_DB_PORT=str(info['port']),E2E_DB_NAME=SCHEMA,
                PYTHONUNBUFFERED='1',E2E_CHILD_DIAGNOSTICS='1',E2E_NUMERIC_HTTP_BIND='1',
                PYTHONPATH=os.pathsep.join([str(diagnostics),os.environ.get('PYTHONPATH','')]))


def connect(info):
    import MySQLdb
    return MySQLdb.connect(host=info['host'],port=info['port'],user=info['user'],passwd=info['password'],db=SCHEMA,charset='utf8mb4',autocommit=True,connect_timeout=2)


def rows(info):
    with contextlib.closing(connect(info)) as c:
        with c.cursor() as cursor:
            cursor.execute('SELECT sku,quantity,status FROM orders_order ORDER BY id')
            return [list(r) for r in cursor.fetchall()]


@contextlib.contextmanager
def baseline(kind):
    if kind!='python':
        from go_provider import GoOwner
        owner=GoOwner(record)
        try:yield owner
        finally:owner.close()
        return
    import mariamem
    source=mariamem.start(host_binary=os.environ['E2E_GUEST_HOST'],startup_timeout=60)
    session=source._session;saved=None
    try:
        info=source.connection_info()
        import MySQLdb
        with contextlib.closing(MySQLdb.connect(host=info['host'],port=info['port'],user='root',db=info['database'],autocommit=True)) as c:
            with c.cursor() as cursor:cursor.execute('CREATE DATABASE '+SCHEMA+' CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci')
        try:native.manage(info_env(info),'migrate','--noinput')
        except __import__('subprocess').CalledProcessError as error:
            (Path(os.environ['E2E_OUTPUT'])/'migration-error.txt').write_bytes(error.stdout+b'\n'+error.stderr)
            raise
        assert rows(info)==[['SEED',2,'ready']]
        source.wait_disconnected();saved=source.snapshot();assert source.closed
        record('baseline_captured',kind=kind,source_consumed=True)
        yield saved
    finally:
        if saved is not None:saved.close()
        source.close()
        reaped=session._process.poll() is not None;removed=not session.root.exists()
        record('guest_host_cleanup',kind='python',reaped=reaped,directory_removed=removed)
        assert reaped and removed


class ObservedLive:
    def __init__(self,live,api):
        self.live=live;self.api=api;self.port=live.connection_info()['port']
        record('live_created',api=api,port=self.port,status=live.status())
    def connection_info(self):return self.live.connection_info()
    def status(self):return self.live.status()
    def reset(self):
        before=self.live.status()
        self.live.reset(timeout=120,drain_timeout=5)
        after=self.live.status()
        assert after['state']=='ready' and after['generation']==before['generation']+1
        assert self.connection_info()['port']==self.port
        record('reset_committed',api=self.api,generation=after['generation'],port=self.port,status=after)
    def close(self):
        before=self.live.status()
        assert before['active_connections']==0,'caller left active physical connections'
        self.live.close();after=self.live.status()
        record('live_closed',api=self.api,active_before_close=before['active_connections'],status=after,close_returned=True)
        assert after['state']=='closed' and after['active_connections']==0


@pytest.fixture(scope='session')
def lineage():
    with baseline(os.environ['E2E_KIND']) as saved:yield saved


@pytest.fixture(scope='session')
def application(lineage):
    kind=os.environ['E2E_KIND']
    if kind=='go-fork':yield None;return
    live=ObservedLive(lineage.live(),'Python public Live' if kind=='python' else 'Go public Live')
    try:
        info=live.connection_info();env=info_env(info)
        appkind='python' if kind=='python' else 'go'
        if appkind=='go':env['E2E_MYSQL_DSN']='root@tcp('+info['host']+':'+str(info['port'])+')/'+SCHEMA+'?charset=utf8mb4&parseTime=true'
        with native.server(SCHEMA,env,appkind) as app:yield app,live,env
    finally:live.close()


@pytest.fixture(scope='session')
def browser():yield from native.browser.__wrapped__()


@pytest.fixture
def browser_page(request,lineage,application,browser):
    from playwright.sync_api import expect
    kind=os.environ['E2E_KIND']
    with contextlib.ExitStack() as stack:
        if kind=='go-fork':
            child=lineage.fork()
            def close():
                child.wait_disconnected();child.close();record('guest_child_closed',child_id=child.id,closed=child.closed)
            stack.callback(close)
            info=child.connection_info();env=info_env(info)
            env['E2E_MYSQL_DSN']='root@tcp('+info['host']+':'+str(info['port'])+')/'+SCHEMA+'?charset=utf8mb4&parseTime=true'
            url,health=stack.enter_context(native.server(SCHEMA,env,'go'))
            generation=child.id
        else:
            (url,health),live,env=application
            if os.environ.get('E2E_MUTATE_SKIP_RESET')!='1':live.reset()
            assert live.status()['state']=='ready','no next test admission after reset failure'
            info=live.connection_info();generation=live.status()['generation']
            if os.environ.get('E2E_MUTATE_RESTART_APP')=='1':url,health=stack.enter_context(native.server(SCHEMA,env,'python' if kind=='python' else 'go'))
        actual=rows(info);record('baseline_checked',name=request.node.name,rows=actual)
        assert actual==[['SEED',2,'ready']]
        record('case_before',name=request.node.name,pid=health['pid'],http_url=url,rows=actual,generation=generation,db_port=info['port'])
        context=browser.new_context();stack.callback(context.close)
        page=context.new_page();page.set_default_timeout(10000);page.goto(url+'/orders')
        expect(page.get_by_test_id('order')).to_have_text(['SEED:2:ready'])
        try:yield page
        finally:record('case_after',name=request.node.name,rows=rows(info))


@pytest.fixture
def isolated_live():
    with baseline('python') as saved:
        live=saved.live()
        try:yield live,saved
        finally:live.close()


@pytest.fixture
def replacement_probe():
    with baseline('probe') as owner:
        probe=owner.probe()
        try:yield probe,owner
        finally:probe.close()
