"""Real guest/schema/seed/command/routing checks, separate from resource acceptance."""
import hashlib
import importlib.util
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import signal
import sys
import xml.etree.ElementTree as ET

import pytest

ROOT = Path(__file__).resolve().parents[1]
HOST = os.environ.get('MARIAMEM_TEST_HOST')
pytestmark = pytest.mark.skipif(not HOST, reason='P1 real guest requires MARIAMEM_TEST_HOST')


def read_case_counts(path):
    root=ET.parse(path).getroot()
    suites=[root] if root.tag=='testsuite' else list(root.iter('testsuite'))
    return {key:sum(int(s.get(key,0)) for s in suites) for key in ('tests','failures','errors','skipped')}


def validate_case_counts(counts,ordinary_failure):
    expected={'tests':6,'failures':int(ordinary_failure),'errors':0,'skipped':0}
    assert counts==expected, 'unexpected P1 child results (including extra cleanup errors): '+repr(counts)


CONF = '''
import os,sys,json,pytest
from pathlib import Path
from mariamem import PrepareCommand
SOURCES=[]
def record(value):
    with Path(os.environ['P1_EVENT_FILE']).open('a') as out:
        out.write(json.dumps(value)+'\\n')
@pytest.fixture(scope='session')
def mariamem_options():
    return {} if os.environ.get('P1_INSTALLED_CONSUMER')=='1' else {'host_binary':os.environ['MARIAMEM_TEST_HOST']}
@pytest.fixture(scope='session')
def mariamem_sqlalchemy_engines():
    import application
    return (application.engine,)
@pytest.fixture(scope='session')
def mariamem_prepare():
    if os.environ['P1_METHOD']=='command':
        return PrepareCommand([sys.executable,os.environ['P1_COMMAND_SCRIPT']])
    sys.path.insert(0,str(Path(os.environ['P1_COMMAND_SCRIPT']).parent))
    from p1_migrate import prepare
    return lambda db: prepare(db.connection_info(),Path(os.environ['P1_MIGRATION_SOURCE']))
@pytest.hookimpl(hookwrapper=True)
def pytest_fixture_setup(fixturedef,request):
    outcome=yield
    if outcome.excinfo is not None: return
    if fixturedef.argname=='mariamem_server':
        SOURCES.append(outcome.get_result())
    if fixturedef.argname in ('mariamem_server','mariamem_snapshot','mariamem_fork'):
        value=outcome.get_result()
        close=value.close
        label=fixturedef.argname
        def observed_close():
            result=close()
            record({'event':'close','kind':label})
            return result
        value.close=observed_close
@pytest.hookimpl(trylast=True)
def pytest_sessionfinish(session):
    for source in SOURCES:
        record({'event':'final','closed':source.closed,
                'host_reaped':source._session._process.poll() is not None,
                'directory_removed':not source._session.root.exists(),'binary':source._session.binary})
'''
CASES = '''
import os,pytest
from sqlalchemy import text
import application
pytestmark=pytest.mark.shadow_maria
SEED=[(1,'legacy',0),(2,'seed',5)]
def baseline():
    assert application.users()==SEED
    with application.engine.connect() as c:
        assert [tuple(row) for row in c.execute(text('SELECT id,user_id,email FROM addresses'))]==[(1,2,'seed@example.test')]
        assert [row[0] for row in c.execute(text('SHOW COLUMNS FROM users'))]==['id','name','rating']
def test_commit(mariamem_app_db):
    baseline()
    application.create_user()
    with application.engine.begin() as c:
        c.execute(text('ALTER TABLE users ADD COLUMN child_only INT'))
    if os.environ.get('P1_FAIL_TEST')=='1':
        raise AssertionError('ORDINARY_TEST_FAILURE')
def test_seed_again(mariamem_app_db): baseline()
@pytest.mark.parametrize('n',range(4))
def test_batch(n,mariamem_app_db):
    baseline()
    application.create_user()
'''


def preflight_consumer():
    sys.path.insert(0,str(ROOT/'scripts'))
    from git_identity import verify_go_binary
    source=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    host_info=verify_go_binary(ROOT,Path(HOST).absolute(),source)
    installed=os.environ.get('P1_INSTALLED_CONSUMER')=='1'
    bundled_host=None
    if installed:
        reference_path = os.environ.get('P1_NATIVE_REFERENCE')
        assert reference_path, 'installed P1 acceptance requires a fresh source-bound native reference'
        spec = importlib.util.spec_from_file_location('p1_native_reference', ROOT/'tests/fixture_entry_acceptance/native.py')
        native = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(native)
        native.validate_reference(json.loads((Path(reference_path)/'result.json').read_text()),
                                  source, f'{sys.version_info.major}.{sys.version_info.minor}')
        import mariamem
        package=Path(mariamem.__file__).resolve().parent
        assert not package.is_relative_to(ROOT/'python'), 'source-tree fallback used'
        distribution=importlib.metadata.distribution('mariamem')
        assert Path(distribution.locate_file('mariamem')).resolve()==package
        expected={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'python/mariamem').glob('*.py')}
        actual={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in package.glob('*.py')}
        assert actual==expected, 'installed module bytes differ or source fallback used'
        bundled_host=package/'_native/mariamem-host'
        verify_go_binary(ROOT,bundled_host,source)
        assert hashlib.sha256(bundled_host.read_bytes()).digest()==hashlib.sha256(Path(HOST).read_bytes()).digest()
    return source,installed,bundled_host


@pytest.mark.parametrize('method,workers,reverse,ordinary_failure', [
    ('command',1,False,False), ('callback',1,True,False),
    ('command',2,False,False), ('command',1,False,True),
])
def test_real_prepared_entry(tmp_path, method, workers, reverse, ordinary_failure):
    source,installed,bundled_host=preflight_consumer()
    project=tmp_path/'consumer';project.mkdir()
    events=project/'events.jsonl'
    # Reuse the authored app and migrations. Only fix its test pool budget.
    app=(ROOT/'tests/preparation_migration_acceptance/application.py').read_text()
    app=app.replace("database='app'))", "database='app'),pool_size=1,max_overflow=1)")
    (project/'application.py').write_text(app)
    (project/'conftest.py').write_text(CONF)
    (project/'test_app.py').write_text(CASES)
    # Use a closed local port; routing must intercept rather than connect there.
    import socket
    with socket.socket() as sentinel:
        sentinel.bind(('127.0.0.1',0));sentinel.listen()
        port=sentinel.getsockname()[1]
        (project/'pytest.ini').write_text('[pytest]\nmariamem_route_profiles = app=127.0.0.1:'+str(port)+'/app\n')
        env={k:v for k,v in os.environ.items() if not k.startswith(('PYTEST_','PYTHON','MARIAMEM_','MYSQLMEM_'))}
        if not installed:env['PYTHONPATH']=str(ROOT/'python')
        env.update(PYTHONDONTWRITEBYTECODE='1',PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',
                   MARIAMEM_TEST_HOST=str(Path(HOST).absolute()),P1_METHOD=method,
                   P1_COMMAND_SCRIPT=str(ROOT/'tests/fixture_entry_acceptance/p1_migrate.py'),
                   P1_MIGRATION_SOURCE=str(ROOT/'tests/preparation_migration_acceptance/migrations'),
                   P1_EVENT_FILE=str(events),MIGRATION_ORIGINAL_PORT=str(port),P1_FAIL_TEST='1' if ordinary_failure else '0')
        argv=[sys.executable,'-m','pytest','-p','mariamem.pytest_plugin','-q','--tb=short','--junitxml=p1-junit.xml']
        if workers==2:argv+=['-p','xdist.plugin','-n','2']
        if reverse:argv+=['test_app.py::test_seed_again','test_app.py::test_commit','test_app.py::test_batch']
        process=subprocess.Popen(argv,cwd=project,env=env,text=True,stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE,start_new_session=True)
        try:
            stdout,stderr=process.communicate(timeout=180)
        except BaseException:
            try:
                os.killpg(process.pid,signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                process.communicate(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid,signal.SIGKILL)
                process.communicate(timeout=5)
            raise
        result=subprocess.CompletedProcess(argv,process.returncode,stdout,stderr)
        (project/'pytest-output.txt').write_text(result.stdout+result.stderr)
        sentinel.setblocking(False)
        with pytest.raises(BlockingIOError):sentinel.accept()
    assert result.returncode==(1 if ordinary_failure else 0),result.stdout+result.stderr
    counts=read_case_counts(project/'p1-junit.xml')
    validate_case_counts(counts,ordinary_failure)
    rows=[json.loads(line) for line in events.read_text().splitlines()]
    prepared=[r for r in rows if r['event']=='prepared']
    final=[r for r in rows if r['event']=='final']
    closes=[r for r in rows if r['event']=='close']
    assert len(prepared)==workers and len({r['worker'] for r in prepared})==workers
    assert len(final)==workers and all(r['closed'] and r['host_reaped'] and r['directory_removed'] for r in final)
    if installed:assert all(Path(r['binary']).resolve()==bundled_host.resolve() for r in final)
    assert sum(r['kind']=='mariamem_fork' for r in closes)==6
    assert sum(r['kind']=='mariamem_snapshot' for r in closes)==workers
    assert sum(r['kind']=='mariamem_server' for r in closes)==workers
    if ordinary_failure:
        assert '1 failed, 5 passed' in result.stdout and 'ORDINARY_TEST_FAILURE' in result.stdout
    print(json.dumps({'result':'P1_REAL_ENTRY_PASS','source_commit':source,'method':method,'workers':workers,'installed_wheel':installed,
        'host_sha256':hashlib.sha256(Path(HOST).read_bytes()).hexdigest(),
        'reverse':reverse,'ordinary_failure':ordinary_failure,'cases':6,'junit_counts':counts,'final_owners':final,
        'inputs_sha256':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in [
            'tests/fixture_entry_acceptance/p1_migrate.py','tests/preparation_migration_acceptance/application.py',
            'tests/preparation_migration_acceptance/migrations/versions/m1_initial.py',
            'tests/preparation_migration_acceptance/migrations/versions/m2_addresses.py']},
        'packages':{p:importlib.metadata.version(p) for p in ['pytest','pytest-xdist','SQLAlchemy','PyMySQL','Alembic']}}))


def test_three_time_campaign(tmp_path):
    source,installed,_=preflight_consumer()
    spec=importlib.util.spec_from_file_location('p1_time_campaign',ROOT/'tests/fixture_entry_acceptance/time_campaign.py')
    campaign=importlib.util.module_from_spec(spec);spec.loader.exec_module(campaign)
    result=campaign.run(ROOT,tmp_path/'time-campaign',HOST,source,installed,CONF,CASES)
    print(json.dumps(dict(result=result['result'],source_commit=source,
                         evidence=str(tmp_path/'time-campaign/result.json'),installed_wheel=installed)))


def test_real_fd_admission_stop(tmp_path):
    source,installed,_=preflight_consumer()
    spec=importlib.util.spec_from_file_location('p1_fd_stop',ROOT/'tests/fixture_entry_acceptance/fd_stop_control.py')
    control=importlib.util.module_from_spec(spec);spec.loader.exec_module(control)
    result=control.run(ROOT,tmp_path/'fd-stop',HOST,source,installed,CONF)
    print(json.dumps(dict(result=result['result'],source_commit=source,
                          evidence=str(tmp_path/'fd-stop/result.json'),installed_wheel=installed)))


def test_real_fd_stop_rejects_guard_bypass(tmp_path):
    source,installed,_=preflight_consumer()
    spec=importlib.util.spec_from_file_location('p1_fd_stop',ROOT/'tests/fixture_entry_acceptance/fd_stop_control.py')
    control=importlib.util.module_from_spec(spec);spec.loader.exec_module(control)
    output=tmp_path/'fd-stop-bypass'
    with pytest.raises(AssertionError):
        control.run(ROOT,output,HOST,source,installed,CONF,bypass_guard=True)
    counts=read_case_counts(output/'results.xml')
    assert counts==dict(tests=3,failures=0,errors=0,skipped=0)
    assert (output/'consumer'/'blocked-body').exists() and (output/'consumer'/'after-body').exists()
    rows=[json.loads(line) for line in (output/'owners.jsonl').read_text().splitlines()]
    assert [r['call'] for r in rows if r.get('event')=='fork_invoked']==[1,2,3]
    finals=[r for r in rows if r.get('event')=='final']
    assert len(finals)==1 and all(finals[0][k] is True for k in ('closed','host_reaped','directory_removed'))


def test_real_snapshot_observation_barrier(tmp_path):
    source,installed,_=preflight_consumer()
    spec=importlib.util.spec_from_file_location('p1_barrier_guest',ROOT/'tests/fixture_entry_acceptance/barrier_guest_control.py')
    control=importlib.util.module_from_spec(spec);spec.loader.exec_module(control)
    result=control.run(ROOT,tmp_path/'barrier-guest',HOST,source,installed,CONF)
    print(json.dumps(dict(result=result['result'],source_commit=source,
                          evidence=str(tmp_path/'barrier-guest/result.json'),installed_wheel=installed)))
