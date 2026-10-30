"""Actual P1 snapshot held behind the test-only observation barrier.

This is a lifecycle feasibility control, not a resource observation campaign.
"""
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

HOOK=r'''
import importlib.util as _br_import,socket as _br_socket
_br_spec=_br_import.spec_from_file_location('p1_barrier',os.environ['P1_BARRIER_PATH'])
_br_barrier=_br_import.module_from_spec(_br_spec);_br_spec.loader.exec_module(_br_barrier)
@pytest.hookimpl(hookwrapper=True,specname='pytest_fixture_setup')
def pytest_barrier_fixture_setup(fixturedef,request):
    outcome=yield
    if outcome.excinfo is not None or fixturedef.argname!='mariamem_snapshot':return
    snapshot=outcome.get_result()
    event={'worker_pid':os.getpid(),'host_pid':snapshot._session._process.pid,
           'source_closed':SOURCES[0].closed,'baseline_closed':snapshot._closed}
    ready=Path(os.environ['P1_BARRIER_READY'])
    temporary=ready.with_suffix('.tmp');temporary.write_text(json.dumps(event));temporary.replace(ready)
    with _br_socket.socket(fileno=int(os.environ['P1_BARRIER_FD'])) as channel:
        _br_barrier.owner_checkpoint(channel,lambda:None,timeout_seconds=90)
    record({'event':'barrier_released'})
'''
CASE='''
import pymysql
def test_child(mariamem_fork):
    info=mariamem_fork.connection_info()
    connection=pymysql.connect(**info)
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT COUNT(*) FROM app.users')
            assert cursor.fetchone()[0]==2
    finally:connection.close()
    mariamem_fork.wait_disconnected()
    assert mariamem_fork.status()['active_connections']==0
'''


def run(root, output, host, source, installed, base_conf):
    output.mkdir(); project=output/'consumer';project.mkdir()
    (project/'conftest.py').write_text(base_conf+HOOK)
    (project/'test_barrier.py').write_text(CASE)
    ready=output/'ready.json';events=output/'owners.jsonl'
    parent,child=socket.socketpair()
    env={k:v for k,v in os.environ.items() if not k.startswith(('PYTEST_','PYTHON','MARIAMEM_','MYSQLMEM_'))}
    if not installed:env['PYTHONPATH']=str(root/'python')
    env.update(PYTHONDONTWRITEBYTECODE='1',PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',
               MARIAMEM_TEST_HOST=str(Path(host).absolute()),P1_METHOD='command',
               P1_COMMAND_SCRIPT=str(root/'tests/fixture_entry_acceptance/p1_migrate.py'),
               P1_MIGRATION_SOURCE=str(root/'tests/preparation_migration_acceptance/migrations'),
               P1_EVENT_FILE=str(events),P1_BARRIER_READY=str(ready),P1_BARRIER_FD=str(child.fileno()),
               P1_BARRIER_PATH=str(root/'tests/fixture_entry_acceptance/observation_barrier.py'))
    command=[sys.executable,'-m','pytest','-p','mariamem.pytest_plugin','test_barrier.py',
             '-q','--tb=short','--junitxml='+str(output/'results.xml')]
    stdout=output/'stdout.txt';stderr=output/'stderr.txt'
    spec=__import__('importlib.util',fromlist=['spec_from_file_location'])
    module_spec=spec.spec_from_file_location('p1_barrier',root/'tests/fixture_entry_acceptance/observation_barrier.py')
    barrier=spec.module_from_spec(module_spec);module_spec.loader.exec_module(barrier)
    with stdout.open('wb') as out,stderr.open('wb') as err:
        process=subprocess.Popen(command,cwd=project,env=env,stdout=out,stderr=err,
                                 pass_fds=(child.fileno(),),start_new_session=True)
        child.close()
        try:
            deadline=time.monotonic()+90
            while not ready.exists():
                if process.poll() is not None:raise AssertionError('pytest exited before snapshot ready')
                if time.monotonic()>=deadline:raise TimeoutError('snapshot readiness timed out')
                time.sleep(.02)
            state=json.loads(ready.read_text())
            assert state['worker_pid']==process.pid and state['host_pid']>0
            assert state['source_closed'] is True and state['baseline_closed'] is False
            def observe():
                os.kill(state['host_pid'],0)
                assert process.poll() is None
                return {'host_alive':True,'worker_alive':True}
            observed=barrier.observe_parked({process:parent},observe,timeout_seconds=30)
            assert process.wait(timeout=90)==0
        finally:
            parent.close()
            if process.poll() is None:
                try:os.killpg(process.pid,signal.SIGTERM)
                except ProcessLookupError:pass
                try:process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid,signal.SIGKILL);process.wait(timeout=5)
    suites=ET.parse(output/'results.xml').getroot().findall('.//testsuite')
    counts={k:sum(int(s.get(k,0)) for s in suites) for k in ('tests','failures','errors','skipped')}
    assert counts==dict(tests=1,failures=0,errors=0,skipped=0)
    rows=[json.loads(line) for line in events.read_text().splitlines()]
    assert sum(r.get('event')=='barrier_released' for r in rows)==1
    assert sum(r.get('event')=='close' and r.get('kind')=='mariamem_fork' for r in rows)==1
    assert sum(r.get('event')=='close' and r.get('kind')=='mariamem_snapshot' for r in rows)==1
    final=[r for r in rows if r.get('event')=='final']
    assert len(final)==1 and all(final[0][k] is True for k in ('closed','host_reaped','directory_removed'))
    result=dict(result='PASS_BOUNDED_REAL_P1_BARRIER',source_commit=source,installed_wheel=installed,
                state=state,observation=observed,counts=counts,final_owner=final[0],
                scope='One actual P1 snapshot/worker; liveness and cleanup only, no resource census or retention campaign')
    (output/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    return result
