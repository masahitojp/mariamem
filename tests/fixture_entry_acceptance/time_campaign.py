"""P1 three-time checkpoint, separate from the complete resource campaign."""
import hashlib
import importlib.metadata
import json
import math
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

BATCHES = ['warmup', 'observed_1', 'observed_2', 'observed_3']

OBSERVER = r'''
import time as _tm_time, hashlib as _tm_hash
_tm_dir=Path(os.environ['P1_TIME_DIRECTORY'])
_tm_worker=os.environ.get('PYTEST_XDIST_WORKER','main')
_tm_original_record=record
def record(value):
    value=dict(value,worker=_tm_worker)
    if value.get('event')=='final':
        assert len(SOURCES)==1
        value['host_pid']=SOURCES[0]._session._process.pid
    _tm_original_record(value)
def _tm_emit(event,**fields):
    with (_tm_dir/('timing-'+_tm_worker+'.jsonl')).open('a') as stream:
        stream.write(json.dumps(dict(event=event,worker=_tm_worker,at_ns=_tm_time.monotonic_ns(),**fields))+'\n')
def _tm_call(name,operation,*args,**kwargs):
    before=_tm_time.monotonic_ns();ok=False
    try:
        result=operation(*args,**kwargs);ok=True;return result
    finally:_tm_emit('phase',name=name,seconds=(_tm_time.monotonic_ns()-before)/1e9,ok=ok)
def _tm_wait(paths):
    deadline=_tm_time.monotonic()+20
    while not all(p.exists() for p in paths):
        if (_tm_dir/'STOP').exists():raise RuntimeError('P1 timing peer failed; admission stopped')
        if _tm_time.monotonic()>=deadline:raise TimeoutError('P1 timing peer/barrier timeout')
        _tm_time.sleep(.005)
def pytest_configure(config):
    import mariamem.pytest_plugin as entry
    original=entry._run_command
    entry._run_command=lambda *args,**kwargs:_tm_call('prepare',original,*args,**kwargs)
@pytest.hookimpl(hookwrapper=True,specname='pytest_fixture_setup')
def pytest_time_fixture_setup(fixturedef,request):
    before=_tm_time.monotonic_ns();outcome=yield
    if outcome.excinfo is not None:return
    name=fixturedef.argname
    if name not in ('mariamem_server','mariamem_snapshot','mariamem_fork'):return
    value=outcome.get_result()
    if name=='mariamem_server':
        _tm_emit('phase',name='start',seconds=(_tm_time.monotonic_ns()-before)/1e9,ok=True)
        for method,label in [('wait_disconnected','disconnect'),('snapshot','capture')]:
            original=getattr(value,method)
            def measured(*args,_original=original,_label=label,**kwargs):return _tm_call(_label,_original,*args,**kwargs)
            setattr(value,method,measured)
    if name=='mariamem_snapshot':
        original=value.fork
        def fork(*args,**kwargs):
            child=_tm_call('admission',original,*args,**kwargs)
            _tm_emit('child_open',child=child._handle)
            return child
        value.fork=fork
    close=value.close
    def measured_close():
        result=_tm_call('cleanup',close)
        if name=='mariamem_fork':_tm_emit('child_close',child=value._handle)
        return result
    value.close=measured_close
@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_setup(item):
    params=getattr(getattr(item,'callspec',None),'params',{})
    batch=params.get('batch');case=params.get('case')
    labels=['warmup','observed_1','observed_2','observed_3']
    if batch and labels.index(batch)>0:
        previous=labels[labels.index(batch)-1]
        _tm_wait([_tm_dir/(previous+'.'+str(i)+'.done') for i in range(4)])
    _tm_emit('case_start',node=item.nodeid,batch=batch,case=case)
    yield
@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_call(item):
    before=_tm_time.monotonic_ns();outcome=yield
    _tm_emit('phase',name='case',seconds=(_tm_time.monotonic_ns()-before)/1e9,ok=outcome.excinfo is None)
    if outcome.excinfo is not None:(_tm_dir/'STOP').write_text('case failed')
@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_teardown(item):
    outcome=yield
    params=getattr(getattr(item,'callspec',None),'params',{})
    batch=params.get('batch');case=params.get('case')
    _tm_emit('case_end',node=item.nodeid,batch=batch,case=case,ok=outcome.excinfo is None)
    if outcome.excinfo is not None:(_tm_dir/'STOP').write_text('cleanup failed')
    if batch:(_tm_dir/(batch+'.'+str(case)+'.done')).write_text('teardown finished')
'''

SECOND = '''import pytest
from test_first import baseline
pytestmark=pytest.mark.shadow_maria
def test_seed_again(mariamem_app_db):
    baseline()
'''

REPEAT = '''import pytest
from sqlalchemy import text
import application
from test_first import baseline
from conftest import _tm_emit, _tm_wait, _tm_dir
pytestmark=pytest.mark.shadow_maria
@pytest.mark.parametrize('batch,case',[
    pytest.param(batch,case,marks=pytest.mark.xdist_group(name='slot'+str(case%2)))
    for batch in ['warmup','observed_1','observed_2','observed_3'] for case in range(4)])
def test_repeat(batch,case,mariamem_app_db):
    baseline()
    with application.engine.connect() as first, application.engine.connect() as second:
        held=mariamem_app_db.status()['active_connections']
        assert held==2
        _tm_emit('sql_hold_begin',batch=batch,case=case,connections=held)
        if __import__('os').environ['P1_TIME_WORKERS']=='2':
            wave=case//2
            (_tm_dir/(batch+'.'+str(case)+'.ready')).write_text('two connections held')
            _tm_wait([_tm_dir/(batch+'.'+str(i)+'.ready') for i in (2*wave,2*wave+1)])
        first.execute(text("INSERT INTO users(id,name,rating) VALUES(3,'created',7)"));first.commit()
        _tm_emit('sql_hold_end',batch=batch,case=case,connections=held)
'''


def validate_second_edit(before, after):
    if set(after)-set(before) != {'test_second.py'} or set(before)-set(after):
        raise ValueError('second-test edit must add exactly test_second.py')
    if any(after[name] != digest for name,digest in before.items()):
        raise ValueError('second-test edit rewrote existing lifecycle/application input')


def assess(events, owners, counts, code, cases, workers, repeated):
    def need(value, reason):
        if not value:
            raise ValueError(reason)
    need(code == 0 and counts == dict(tests=cases, failures=0, errors=0, skipped=0), 'unexpected JUnit/exit')
    expected = {'main'} if workers == 1 else {'gw0', 'gw1'}
    need({e['worker'] for e in events} == expected, 'wrong worker census')
    phases = {}
    for worker in expected:
        rows = [e for e in events if e['worker'] == worker]
        worker_cases = cases if workers == 1 else cases // 2
        for name, count in [('start',1),('prepare',1),('disconnect',1),('capture',1),
                            ('admission',worker_cases),('case',worker_cases),('cleanup',worker_cases+2)]:
            values = [e for e in rows if e['event']=='phase' and e['name']==name]
            need(len(values)==count and all(e['ok'] is True and type(e['seconds']) in (int,float)
                 and math.isfinite(e['seconds']) and e['seconds']>0 for e in values), 'phase missing/failed: '+name)
        opened = [e['child'] for e in rows if e['event']=='child_open']
        closed = [e['child'] for e in rows if e['event']=='child_close']
        need(len(opened)==worker_cases and len(set(opened))==worker_cases and sorted(opened)==sorted(closed), 'child ownership census')
        balance=0
        for event in sorted((e for e in rows if e['event'] in ('child_open','child_close')),key=lambda e:e['at_ns']):
            balance += 1 if event['event']=='child_open' else -1
            need(0<=balance<=1, 'worker child overlap/budget')
        need(balance==0, 'child balance')
        owned=[e for e in owners if e.get('worker')==worker]
        need(sum(e.get('event')=='prepared' for e in owned)==1, 'preparation not once per worker')
        need(sum(e.get('event')=='final' for e in owned)==1, 'worker final owner missing')
        for kind,count in [('mariamem_fork',worker_cases),('mariamem_snapshot',1),('mariamem_server',1)]:
            need(sum(e.get('event')=='close' and e.get('kind')==kind for e in owned)==count,'owner cleanup census')
        phases[worker] = {name:[e['seconds'] for e in rows if e['event']=='phase' and e['name']==name]
                          for name in ('start','prepare','disconnect','capture','admission','case','cleanup')}
    finals = [e for e in owners if e.get('event')=='final']
    need(len(finals)==workers and all(e[k] is True for e in finals for k in ('closed','host_reaped','directory_removed')), 'final cleanup missing')
    need(len({e['host_pid'] for e in finals})==workers,'source host not independent')
    need(sum(e.get('event')=='prepared' for e in owners)==workers, 'preparation not once per worker')
    windows=[]
    if repeated:
        for label in BATCHES:
            starts=[e for e in events if e['event']=='case_start' and e['batch']==label]
            ends=[e for e in events if e['event']=='case_end' and e['batch']==label]
            need(len(starts)==len(ends)==4 and {e['case'] for e in starts}==set(range(4)) and
                 {e['case'] for e in ends}==set(range(4)) and all(e['ok'] for e in ends), 'batch census')
            begin=min(e['at_ns'] for e in starts);end=max(e['at_ns'] for e in ends)
            need(end>begin and (not windows or windows[-1]['end_ns']<=begin), 'overlapping/reversed batch windows')
            windows.append(dict(label=label,start_ns=begin,end_ns=end,elapsed_seconds=(end-begin)/1e9))
        holds=[e for e in events if e['event'] in ('sql_hold_begin','sql_hold_end')]
        need(len(holds)==2*cases and all(e['connections']==2 for e in holds), 'physical hold observations missing')
        balance=0;peak=0
        for event in sorted(holds,key=lambda e:e['at_ns']):
            balance += event['connections']*(1 if event['event']=='sql_hold_begin' else -1)
            need(0<=balance<=2*workers, 'held-connection budget/census')
            peak=max(peak,balance)
        need(balance==0 and peak==2*workers, 'parallel physical overlap not observed')
    else:
        peak=None
    return dict(phase_seconds_by_worker=phases,batches=windows,peak_held_sql_connections=peak)


def run(root, output, host, source, installed, base_conf, cases_text):
    first_started=time.monotonic()
    root=Path(root);output=Path(output);output.mkdir(parents=True,exist_ok=False)
    plan=json.loads((root/'docs/reviews/v06x-p1-time-campaign-plan.json').read_text())
    assert plan['repeated_batch']['labels']==BATCHES and plan['repeated_batch']['workers']==[1,2]
    project=output/'project';project.mkdir()
    sentinel=socket.socket();sentinel.bind(('127.0.0.1',0));sentinel.listen();sentinel.setblocking(False)
    before=time.monotonic()
    first=cases_text.split('def test_seed_again',1)[0]
    app=(root/'tests/preparation_migration_acceptance/application.py').read_text()
    assert app.count("database='app'))")==1
    app=app.replace("database='app'))","database='app'),pool_size=1,max_overflow=1)")
    (project/'application.py').write_text(app)
    (project/'conftest.py').write_text(base_conf+OBSERVER)
    (project/'pytest.ini').write_text('[pytest]\nmariamem_route_profiles = app=127.0.0.1:'+str(sentinel.getsockname()[1])+'/app\n')
    (project/'test_first.py').write_text(first)
    scaffold=time.monotonic()-before
    def source_files():
        return {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in project.iterdir()
                if p.is_file() and p.suffix in ('.py','.ini')}
    first_files=source_files()
    results={}
    def execute(label, filenames, count, workers=1, repeated=False):
        directory=output/label;directory.mkdir();sync=directory/'sync';sync.mkdir()
        env={k:v for k,v in os.environ.items() if not k.startswith(('PYTEST_','PYTHON','MARIAMEM_','MYSQLMEM_'))}
        if not installed:env['PYTHONPATH']=str(root/'python')
        env.update(PYTHONDONTWRITEBYTECODE='1',PYTEST_DISABLE_PLUGIN_AUTOLOAD='1',
                   MARIAMEM_TEST_HOST=str(Path(host).absolute()),P1_METHOD='command',
                   P1_INSTALLED_CONSUMER='1' if installed else '0',
                   P1_COMMAND_SCRIPT=str(root/'tests/fixture_entry_acceptance/p1_migrate.py'),
                   P1_MIGRATION_SOURCE=str(root/'tests/preparation_migration_acceptance/migrations'),
                   P1_EVENT_FILE=str(directory/'owners.jsonl'),P1_TIME_DIRECTORY=str(sync),
                   P1_TIME_WORKERS=str(workers),MIGRATION_ORIGINAL_PORT=str(sentinel.getsockname()[1]),P1_FAIL_TEST='0')
        argv=[sys.executable,'-m','pytest','-p','mariamem.pytest_plugin','-p','xdist.plugin',*filenames,'-q','--tb=short','--junitxml='+str(directory/'results.xml')]
        if workers==2:argv+=['-n','2','--dist=loadgroup']
        started=time.monotonic();process=subprocess.Popen(argv,cwd=project,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,start_new_session=True)
        try:
            stdout,stderr=process.communicate(timeout=180)
        except BaseException:
            for sig in (signal.SIGINT,signal.SIGTERM,signal.SIGKILL):
                try:os.killpg(process.pid,sig)
                except ProcessLookupError:pass
                try:process.communicate(timeout=5);break
                except subprocess.TimeoutExpired:continue
            raise
        elapsed=time.monotonic()-started
        (directory/'stdout.txt').write_bytes(stdout);(directory/'stderr.txt').write_bytes(stderr)
        suites=ET.parse(directory/'results.xml').getroot().findall('.//testsuite')
        counts={k:sum(int(s.get(k,0)) for s in suites) for k in ('tests','failures','errors','skipped')}
        events=[json.loads(line) for path in sorted(sync.glob('timing-*.jsonl')) for line in path.read_text().splitlines()]
        owners=[json.loads(line) for line in (directory/'owners.jsonl').read_text().splitlines()]
        derived=assess(events,owners,counts,process.returncode,count,workers,repeated)
        result=dict(command=argv,wall_seconds=elapsed,counts=counts,workers=workers,**derived)
        (directory/'result.json').write_text(json.dumps(result,indent=2)+'\n')
        results[label]=result
    try:
        execute('first',['test_first.py'],1)
        first_total=time.monotonic()-first_started
        second_started=time.monotonic();(project/'test_second.py').write_text(SECOND);edit=time.monotonic()-second_started
        second_files=source_files();validate_second_edit(first_files,second_files)
        execute('second',['test_first.py','test_second.py'],2)
        second_total=time.monotonic()-second_started
        (project/'test_repeat.py').write_text(REPEAT)
        for workers in (1,2):execute('repeat-workers'+str(workers),['test_repeat.py'],16,workers,True)
        try:connection,_=sentinel.accept()
        except BlockingIOError:pass
        else:connection.close();raise AssertionError('original application endpoint contacted')
    finally:sentinel.close()
    receipt=dict(result='PASS_P1_TIME_CHECKPOINT',source_commit=source,installed_wheel=installed,
                 host_sha256=hashlib.sha256(Path(host).read_bytes()).hexdigest(),python=sys.version,
                 first_test_setup_seconds=first_total,second_test_edits_seconds=second_total,
                 first_scaffold_seconds=scaffold,second_edit_seconds=edit,first_test_lines=len(first.splitlines()),
                 first_input_sha256=first_files,second_input_sha256=second_files,
                 packages={name:importlib.metadata.version(name) for name in ('pytest','pytest-xdist','SQLAlchemy','PyMySQL','Alembic')},
                 code_sha256={name:hashlib.sha256((root/name).read_bytes()).hexdigest() for name in
                              ('tests/fixture_entry_acceptance/time_campaign.py','tests/test_p1_runtime.py')},
                 added_second_test_lines=len(SECOND.splitlines()),repeated_lifecycle_lines=0,
                 acquisition=plan['acquisition'],human_authoring_minutes=None,phase_times_are_not_summed=True,
                 runs=results,plan_sha256=hashlib.sha256((root/'docs/reviews/v06x-p1-time-campaign-plan.json').read_bytes()).hexdigest(),
                 input_sha256={p:hashlib.sha256((project/p).read_bytes()).hexdigest() for p in ('application.py','conftest.py','pytest.ini','test_first.py','test_second.py','test_repeat.py')},
                 original_endpoint_contacts=0,remaining=plan['still_required'])
    (output/'result.json').write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt
