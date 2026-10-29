"""Real P1 retained-snapshot feasibility; not full resource acceptance."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

CONF=r'''
import json,os,pytest,pymysql
from pathlib import Path
SOURCES=[]
def record(value):
    with Path(os.environ['P1_EVENT_FILE']).open('a') as out:out.write(json.dumps(value)+'\n')
@pytest.fixture(scope='session')
def mariamem_options():
    return {} if os.environ.get('P1_INSTALLED_CONSUMER')=='1' else {'host_binary':os.environ['MARIAMEM_TEST_HOST']}
@pytest.fixture(scope='session')
def mariamem_prepare():
    def prepare(db):
        connection=pymysql.connect(**db.connection_info())
        try:
            sql=Path(os.environ['P1_RETENTION_SQL']).read_text()
            with connection.cursor() as cursor:
                for statement in sql.split(';'):
                    if statement.strip():cursor.execute(statement)
            connection.commit()
        finally:connection.close()
        record({'event':'prepared'})
    return prepare
@pytest.hookimpl(hookwrapper=True)
def pytest_fixture_setup(fixturedef,request):
    outcome=yield
    if outcome.excinfo is not None:return
    if fixturedef.argname=='mariamem_server':SOURCES.append(outcome.get_result())
    if fixturedef.argname in ('mariamem_server','mariamem_snapshot','mariamem_fork'):
        value=outcome.get_result();original=value.close;label=fixturedef.argname
        def close():
            result=original();record({'event':'close','kind':label});return result
        value.close=close
@pytest.hookimpl(trylast=True)
def pytest_sessionfinish(session):
    for source in SOURCES:
        record({'event':'final','closed':source.closed,'host_reaped':source._session._process.poll() is not None,
                'directory_removed':not source._session.root.exists()})
'''
CASE=r'''
import pymysql
def test_retained(mariamem_fork):
    connection=pymysql.connect(**mariamem_fork.connection_info())
    try:
        with connection.cursor() as cursor:
            for n in range(64):
                cursor.execute('SELECT id,HEX(payload) FROM resource_%02d' % n)
                assert cursor.fetchall()==((1,'73656564'),)
    finally:connection.close()
    mariamem_fork.wait_disconnected()
    assert mariamem_fork.status()['active_connections']==0
'''


def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module


def run(root,output,host,source,installed):
    """Sequentially hold one, two and three independent pytest snapshots.

    RSS/disk checks bound admission in this feasibility run. Counters are
    snapshots, not continuous guards; no full FD/temp/connection acceptance is
    implied. Callers must use source-stamped host and installed-wheel preflight.
    """
    output.mkdir();resources=json.loads((root/'docs/reviews/v06x-fixture-acceptance.json').read_text())['resources']
    sql=root/resources['retention_input']['path']
    assert hashlib.sha256(sql.read_bytes()).hexdigest()==resources['retention_input']['sha256']
    barrier=load(root/'tests/fixture_entry_acceptance/observation_barrier.py','p1_barrier')
    guest=load(root/'tests/fixture_entry_acceptance/barrier_guest_control.py','p1_barrier_guest')
    sys.path.insert(0,str(root/'scripts'))
    from go_fixture_campaign import process_rss,available_memory
    baseline=sum(process_rss(os.getpid()).values())
    group=barrier.RetainedOwners(timeout_seconds=60);owners=[];observations=[];completed=False
    try:
        for number in (1,2,3):
            previous=process_rss(os.getpid());rss=sum(previous.values())
            disk=shutil.disk_usage(output).free
            if rss-baseline>resources['incremental_rss_ceiling_bytes'] or disk<resources['min_free_disk_bytes']:
                raise RuntimeError('feasibility pre-admission resource STOP')
            directory=output/('owner'+str(number));directory.mkdir();project=directory/'consumer';project.mkdir()
            (project/'conftest.py').write_text(CONF+guest.HOOK);(project/'test_retained.py').write_text(CASE)
            ready=directory/'ready.json';events=directory/'owners.jsonl';parent,child=socket.socketpair()
            env={k:v for k,v in os.environ.items() if not k.startswith(('PYTEST_','PYTHON','MARIAMEM_','MYSQLMEM_'))}
            if not installed:env['PYTHONPATH']=str(root/'python')
            env.update(PYTHONDONTWRITEBYTECODE='1',PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',
                       MARIAMEM_TEST_HOST=str(Path(host).absolute()),P1_RETENTION_SQL=str(sql),
                       P1_EVENT_FILE=str(events),P1_BARRIER_READY=str(ready),P1_BARRIER_FD=str(child.fileno()),
                       P1_BARRIER_PATH=str(root/'tests/fixture_entry_acceptance/observation_barrier.py'))
            command=[sys.executable,'-m','pytest','-p','mariamem.pytest_plugin','test_retained.py','-q',
                     '--tb=short','--junitxml='+str(directory/'results.xml')]
            out=(directory/'stdout.txt').open('wb');err=(directory/'stderr.txt').open('wb')
            try:process=subprocess.Popen(command,cwd=project,env=env,stdout=out,stderr=err,pass_fds=(child.fileno(),),start_new_session=True)
            except BaseException:parent.close();child.close();out.close();err.close();raise
            child.close();owners.append((process,parent,out,err,directory))
            deadline=time.monotonic()+90
            while not ready.exists():
                if process.poll() is not None:raise RuntimeError('retained worker exited before ready; see '+str(directory))
                if time.monotonic()>=deadline:raise TimeoutError('retained worker readiness timeout')
                time.sleep(.02)
            state=json.loads(ready.read_text())
            assert state['worker_pid']==process.pid and state['source_closed'] is True and state['baseline_closed'] is False
            group.add(process,parent)
            def observe():
                members=process_rss(os.getpid());memory,method=available_memory();free=shutil.disk_usage(output).free
                pids={str(p.pid) for p,_,_,_,_ in owners}
                states=[json.loads((d/'ready.json').read_text()) for _,_,_,_,d in owners]
                assert pids <= set(members) and {str(s['host_pid']) for s in states} <= set(members)
                total=sum(members.values())
                if total-baseline>resources['incremental_rss_ceiling_bytes'] or free<resources['min_free_disk_bytes']:
                    raise RuntimeError('feasibility sampled resource STOP')
                return dict(retained=number,process_tree_rss_bytes=total,baseline_rss_bytes=baseline,
                            available_memory_bytes=memory,available_memory_method=method,disk_free_bytes=free,
                            process_rss_bytes=members,host_pids=[s['host_pid'] for s in states])
            observations.append(group.sample(observe))
        group.release()
        for process,_,_,_,directory in owners:
            if process.wait(timeout=90)!=0:raise AssertionError('retained worker failed; see '+str(directory))
        final=[]
        for _,_,_,_,directory in owners:
            suites=ET.parse(directory/'results.xml').getroot().findall('.//testsuite')
            counts={k:sum(int(s.get(k,0)) for s in suites) for k in ('tests','failures','errors','skipped')}
            assert counts==dict(tests=1,failures=0,errors=0,skipped=0)
            rows=[json.loads(line) for line in (directory/'owners.jsonl').read_text().splitlines()]
            assert sum(r.get('event')=='prepared' for r in rows)==1
            for kind in ('mariamem_server','mariamem_snapshot','mariamem_fork'):
                assert sum(r.get('event')=='close' and r.get('kind')==kind for r in rows)==1
            done=[r for r in rows if r.get('event')=='final']
            assert len(done)==1 and all(done[0][k] is True for k in ('closed','host_reaped','directory_removed'))
            final.append(done[0])
        result=dict(result='PASS_RETENTION_LIFECYCLE_FEASIBILITY',source_commit=source,installed_wheel=installed,
                    input_sha256=hashlib.sha256(sql.read_bytes()).hexdigest(),observations=observations,
                    owners=len(owners),cleanup_complete=True,final_owners=final,
                    scope='Three P1 pytest processes, each with one 64-table snapshot. RSS/free disk are point samples only.',
                    remaining='Complete aligned FD/allocated-temp/connection census, continuous guards, native control, mutations and required-host full P1 acceptance')
        (output/'result.json').write_text(json.dumps(result,indent=2)+'\n');completed=True;return result
    finally:
        if not group.released:group.abort()
        for process,parent,out,err,_ in owners:
            parent.close()
            if not completed:
                try:os.killpg(process.pid,signal.SIGTERM)
                except ProcessLookupError:pass
        for process,_,out,err,_ in owners:
            try:process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid,signal.SIGKILL);process.wait(timeout=5)
            out.close();err.close()
