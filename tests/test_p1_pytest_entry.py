"""Actual pytest setup/teardown and worker-local admission with controlled owners."""
import importlib.util
import copy
import os
from pathlib import Path

import pytest

from mariamem._pytest_owner import _Owner

spec = importlib.util.spec_from_file_location('p1_existing_fixtures', Path(__file__).with_name('test_routing_pytest.py'))
helper = importlib.util.module_from_spec(spec)
spec.loader.exec_module(helper)


@pytest.mark.parametrize('ordinary_failure', [False, True])
def test_cleanup_debt_blocks_next_body_but_ordinary_assertion_does_not(tmp_path, ordinary_failure):
    conf = '''
from contextlib import contextmanager
original = Baseline.fork
@contextmanager
def replacement(self):
    with original(self) as child:
        yield child
        if child.data.get('fail_cleanup'):
            raise OSError('CONTROLLED_CHILD_CLEANUP')
Baseline.fork = replacement
'''
    tests = '''
def test_first(mariamem_fork):
    mariamem_fork.data['fail_cleanup'] = FAIL_CLEANUP
    raise AssertionError('ORIGINAL_ASSERTION')
def test_second(mariamem_fork):
    assert mariamem_fork.data == {}
    from pathlib import Path
    Path('second-body').touch()
'''.replace('FAIL_CLEANUP', repr(not ordinary_failure))
    result, events = helper.fake_suite(tmp_path, conf, tests, False)
    assert result.returncode == 1 and 'ORIGINAL_ASSERTION' in result.stdout
    assert (tmp_path/'second-body').exists() == ordinary_failure
    assert events.count('fork') == (2 if ordinary_failure else 1)
    assert events.count('child.close') == events.count('fork')
    assert events[-2:] == ['baseline.close', 'source.close']
    if ordinary_failure:
        assert 'mariamem entry failures' not in result.stdout
    else:
        assert 'CONTROLLED_CHILD_CLEANUP' in result.stdout
        assert 'dependent admission stopped for this worker' in result.stdout
        assert 'cleanup=unconfirmed' in result.stdout


def test_command_descriptor_is_third_input_and_callback_return_is_ignored(tmp_path):
    (tmp_path/'prepare.py').write_text('import os,json,pathlib;pathlib.Path("target").write_text(os.environ["MARIAMEM_PREPARE_CONNECTION_INFO"])')
    conf = '''
import sys
from mariamem import PrepareCommand
DB.connection_info = lambda self: {'host':'127.0.0.1','port':1234,'database':'app'}
@pytest.fixture(scope='session')
def mariamem_prepare():
    return PrepareCommand([sys.executable, 'prepare.py'])
'''
    result, events = helper.fake_suite(tmp_path, conf, 'def test_body(mariamem_fork): pass', False)
    assert result.returncode == 0, result.stdout + result.stderr
    assert '1234' in (tmp_path/'target').read_text()
    assert events.count('snapshot') == events.count('fork') == 1


def test_callback_returning_a_descriptor_never_executes_it(tmp_path):
    result, events = helper.fake_suite(tmp_path, '''
from mariamem import PrepareCommand
@pytest.fixture(scope='session')
def mariamem_prepare():
    return lambda db: PrepareCommand(['must-not-execute'])
''', 'def test_body(mariamem_fork): pass', False)
    assert result.returncode == 0, result.stdout + result.stderr
    assert events.count('snapshot') == 1


@pytest.mark.parametrize('value', ['42', 'False', '{}', '[]'])
def test_unknown_preparation_values_remain_usage_errors(tmp_path, value):
    result, events = helper.fake_suite(tmp_path, f'''
@pytest.fixture(scope='session')
def mariamem_prepare():
    return {value}
''', 'def test_body(mariamem_fork): pass', False)
    assert result.returncode == 1
    assert 'must return None, a callable accepting the preparation DB, or PrepareCommand.' in result.stdout
    assert 'snapshot' not in events and 'fork' not in events
    assert events[-1] == 'source.close'


def test_prepare_fixture_error_and_source_cleanup_both_survive(tmp_path):
    result, events = helper.fake_suite(tmp_path, '''
from contextlib import contextmanager
@contextmanager
def fail_close(**options):
    record('start')
    try: yield DB('source')
    finally:
        record('source.close')
        raise OSError('ORIGINAL_SOURCE_CLEANUP')
plugin.start = fail_close
@pytest.fixture(scope='session')
def mariamem_prepare(mariamem_server):
    raise ValueError('ORIGINAL_FIXTURE_FAILURE')
''', 'def test_body(mariamem_fork): pass', False)
    assert result.returncode == 1
    assert 'ORIGINAL_FIXTURE_FAILURE' in result.stdout and 'ORIGINAL_SOURCE_CLEANUP' in result.stdout
    assert 'mariamem prepare:' in result.stdout and 'cleanup=unconfirmed' in result.stdout
    assert events == ['start', 'source.close']


def test_routing_cleanup_debt_precedes_child_cleanup_and_blocks_next(tmp_path):
    result, events = helper.fake_suite(tmp_path, '''
from contextlib import contextmanager
class Router:
    profiles = {'app':None}
    @contextmanager
    def bind(self, profile, db):
        yield
        record('routing.close')
        raise RuntimeError('ORIGINAL_ROUTING_CLEANUP')
@pytest.fixture(scope='session')
def mariamem_router(): return Router()
''', '''
def test_first(mariamem_app_db): pass
def test_second(mariamem_app_db):
    raise AssertionError('SECOND_BODY_MUST_NOT_RUN')
''', False)
    assert result.returncode == 1 and 'ORIGINAL_ROUTING_CLEANUP' in result.stdout
    assert 'AssertionError: SECOND_BODY_MUST_NOT_RUN' not in result.stdout
    assert events.index('routing.close') < events.index('child.close')
    assert events.count('fork') == 1 and events[-1] == 'source.close'


def test_partial_enter_and_combined_unwind_keep_actual_fd_and_original(tmp_path):
    owner = _Owner()
    original = ValueError('original')
    cleanup = OSError('cleanup')
    class Manager:
        def __enter__(self):
            self.fd = os.open(tmp_path/'backing', os.O_CREAT | os.O_RDWR, 0o600)
            return self
        def __exit__(self, *args):
            os.close(self.fd)
            raise cleanup
    manager = Manager()
    with pytest.raises(ValueError) as caught:
        with owner.context(lambda: manager, 'capture'):
            raise original
    assert caught.value is original and cleanup in original.cleanup_errors
    assert owner.debt is cleanup and owner.uncertain
    with pytest.raises(OSError): os.fstat(manager.fd)
    # Closed flags are never used to suppress a returned public owner's Close.
    class Partial:
        closed = True
        def __enter__(self):
            self.fd = os.open(tmp_path/'partial', os.O_CREAT | os.O_RDWR, 0o600)
            raise original
        def close(self): os.close(self.fd)
    partial = Partial()
    with pytest.raises(ValueError) as caught:
        with _Owner().context(lambda: partial, 'capture'): pass
    assert caught.value is original
    with pytest.raises(OSError): os.fstat(partial.fd)


def test_unconfirmed_command_cleanup_is_never_completed_in_owner_summary():
    owner = _Owner()
    error = RuntimeError('command')
    error.process_cleanup = 'unconfirmed'
    owner.fail('prepare', error)
    assert owner.uncertain and owner.stopped is error


def test_xdist_reports_final_cleanup_and_keeps_other_worker_running(tmp_path):
    pytest.importorskip('xdist')
    (tmp_path/'test_other.py').write_text('''
from pathlib import Path
def test_other_one(mariamem_fork):
    assert mariamem_fork.data == {}
    Path('other-one').touch()
def test_other_two(mariamem_fork):
    assert mariamem_fork.data == {}
    Path('other-two').touch()
''')
    result, events = helper.fake_suite(tmp_path, '''
from contextlib import contextmanager
original = Baseline.fork
@contextmanager
def replacement(self):
    with original(self) as child:
        yield child
        if child.data.get('fail_cleanup'):
            raise OSError('WORKER_CLEANUP_DEBT')
Baseline.fork = replacement
''', '''
def test_first(mariamem_fork):
    mariamem_fork.data['fail_cleanup'] = True
def test_second(mariamem_fork):
    from pathlib import Path
    Path('blocked-body').touch()
''', False, '-p', 'xdist.plugin', '-n', '2', '--dist=loadfile')
    assert result.returncode == 1, result.stdout + result.stderr
    assert (tmp_path/'other-one').exists() and (tmp_path/'other-two').exists()
    assert not (tmp_path/'blocked-body').exists()
    assert events.count('start') == events.count('source.close') == 2
    assert events.count('fork') == events.count('child.close') == 3
    assert 'mariamem entry failures' in result.stdout and 'cleanup=unconfirmed' in result.stdout
    assert 'gw0:' in result.stdout or 'gw1:' in result.stdout


def test_required_hosts_run_new_entry_controls_for_both_python_minors():
    root = Path(__file__).resolve().parents[1]
    text = (root/'.github/workflows/live-host.yml').read_text()
    segment = text.split('- name: Public Go/Python browser Live, Fork control and actual defects', 1)[1]
    segment = segment.split('- name:', 1)[0]
    assert 'for py in "$PY311" "$PY314"' in segment
    runtime = text.split('- name: P1 real prepared command and callback on both Python minors', 1)[1].split('- name:', 1)[0]
    assert 'for py in "$PY311" "$PY314"' in runtime
    assert 'MARIAMEM_TEST_HOST="$PWD/build/mariamem-host"' in runtime and 'tests/test_p1_runtime.py' in runtime
    assert 'pytest_version=7.0.0' in runtime and 'pytest_version=9.0.2' in runtime
    assert 'P1_INSTALLED_CONSUMER=1' in runtime and '--no-deps build/dist/*.whl' in runtime
    assert 'tests/test_prepare_command.py tests/test_p1_pytest_entry.py' in runtime
    assert 'cp tests/evidence/alpha-wheel.json build/live-evidence/p1-wheel.json' in runtime
    assert "P1_RESOURCE_EXPERIMENT: '0'" in runtime
    assert 'tests/test_owned_snapshot_unit.py' in runtime
    for deferred in ('test_p1_resource_probe.py', 'test_p1_resource_guard.py', 'test_p1_observation_barrier.py'):
        assert deferred not in runtime
    triggers = text.split('permissions:', 1)[0]
    assert '  workflow_call:' in triggers
    assert '  workflow_dispatch:' not in triggers
    assert '  pull_request:' not in triggers and '  push:' not in triggers
    native = text.split('- name: Fresh P1 authored command and callback native control', 1)[1].split('- uses:', 1)[0]
    assert 'tests/fixture_entry_acceptance/native.py' in native
    assert '--expected-source-commit "$SOURCE_COMMIT"' in native
    assert 'ref: ${{ inputs.source_commit }}' in text
    assert 'needs.scope' not in text


def test_expected_assertion_cannot_hide_final_source_cleanup_error(tmp_path):
    spec=importlib.util.spec_from_file_location('p1_runtime_results',Path(__file__).with_name('test_p1_runtime.py'))
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    tests="""
import pytest
def test_first(mariamem_fork): raise AssertionError('EXPECTED_ASSERTION')
@pytest.mark.parametrize('n',range(5))
def test_remaining(n,mariamem_fork): assert mariamem_fork.data=={}
"""
    conf="""
from contextlib import contextmanager
@contextmanager
def replacement(**options):
    record('start')
    source=DB('source')
    try: yield source
    finally:
        source.closed=True
        record('source.close')
        raise OSError('EXTRA_SOURCE_CLEANUP_ERROR')
plugin.start=replacement
"""
    clean=tmp_path/'clean';clean.mkdir()
    failed=tmp_path/'failed';failed.mkdir()
    positive,_=helper.fake_suite(clean,'',tests,False,'--junitxml=report.xml')
    assert positive.returncode==1
    module.validate_case_counts(module.read_case_counts(clean/'report.xml'),True)
    negative,events=helper.fake_suite(failed,conf,tests,False,'--junitxml=report.xml')
    assert negative.returncode==1 and 'EXTRA_SOURCE_CLEANUP_ERROR' in negative.stdout
    assert events.count('fork')==events.count('child.close')==6
    with pytest.raises(AssertionError,match='extra cleanup errors'):
        module.validate_case_counts(module.read_case_counts(failed/'report.xml'),True)


def test_owner_cleanup_interrupt_preserves_primary_without_swallowing_interrupt(tmp_path):
    primary = ValueError('original operation')
    interrupt = KeyboardInterrupt()
    class Manager:
        def __enter__(self): return self
        def __exit__(self, *args): raise interrupt
    owner = _Owner()
    with pytest.raises(KeyboardInterrupt) as caught:
        with owner.context(Manager, 'capture'):
            raise primary
    assert caught.value is interrupt and interrupt.__cause__ is primary
    assert owner.debt is interrupt and owner.uncertain


def test_readonly_callback_error_keeps_identity_and_cleanup_cause():
    from dataclasses import dataclass
    @dataclass(frozen=True)
    class ReadonlyError(Exception):
        message: str
    primary = ReadonlyError('original read-only callback error')
    owner = _Owner()
    with pytest.raises(BaseException) as caught:
        with owner.operation('prepare'):
            raise primary
    assert caught.value is primary and owner.stopped is primary
    cleanup = OSError('original cleanup')
    class Manager:
        def __enter__(self): return self
        def __exit__(self, *args): raise cleanup
    with pytest.raises(BaseException) as caught:
        with _Owner().context(Manager, 'capture'):
            raise primary
    assert caught.value is primary and primary.__cause__ is cleanup


def test_readonly_callback_error_has_pytest_fallback_without_changing_its_type(tmp_path):
    result,events=helper.fake_suite(tmp_path, '''
class ReadonlyError(Exception):
    def __setattr__(self,name,value):
        if name in ('__notes__','cleanup_errors'):
            raise AttributeError('diagnostic metadata is read-only')
        super().__setattr__(name,value)
@pytest.fixture(scope='session')
def mariamem_prepare():
    def prepare(db): raise ReadonlyError('ORIGINAL_READONLY_FAILURE')
    return prepare
''', 'def test_body(mariamem_fork): pass', False)
    assert result.returncode==1 and 'ReadonlyError: ORIGINAL_READONLY_FAILURE' in result.stdout
    assert 'FrozenInstanceError' not in result.stdout
    assert 'next: inspect original error' in result.stdout and 'entry-owned finalizers completed' in result.stdout
    assert events==['start','source.close']


def _time_campaign_observations(workers=2):
    spec=importlib.util.spec_from_file_location('p1_time_oracles',Path(__file__).parent/'fixture_entry_acceptance/time_campaign.py')
    campaign=importlib.util.module_from_spec(spec);spec.loader.exec_module(campaign)
    events=[];owners=[]
    names=['main'] if workers==1 else ['gw0','gw1']
    for index,worker in enumerate(names):
        count=16//workers
        for phase,total in [('start',1),('prepare',1),('disconnect',1),('capture',1),('admission',count),('case',count),('cleanup',count+2)]:
            events.extend(dict(event='phase',worker=worker,name=phase,seconds=.001,ok=True) for _ in range(total))
        owners.extend([dict(event='prepared',worker=worker),dict(event='final',worker=worker,host_pid=100+index,closed=True,host_reaped=True,directory_removed=True)])
        owners.extend(dict(event='close',worker=worker,kind=kind) for kind,n in [('mariamem_fork',count),('mariamem_snapshot',1),('mariamem_server',1)] for _ in range(n))
    for batch_index,batch in enumerate(campaign.BATCHES):
        base=1000*(batch_index+1)
        for case in range(4):
            worker=names[case%workers]
            start=base+(case//workers)*100+case%workers
            end=start+50
            identity=batch_index*4+case
            events.extend([dict(event='case_start',worker=worker,at_ns=start,batch=batch,case=case),
                           dict(event='child_open',worker=worker,at_ns=start+1,child=identity),
                           dict(event='child_close',worker=worker,at_ns=end-1,child=identity),
                           dict(event='case_end',worker=worker,at_ns=end,batch=batch,case=case,ok=True),
                           dict(event='sql_hold_begin',worker=worker,at_ns=start+10,batch=batch,case=case,connections=2),
                           dict(event='sql_hold_end',worker=worker,at_ns=end-10,batch=batch,case=case,connections=2)])
    return campaign,events,owners,dict(tests=16,failures=0,errors=0,skipped=0)


@pytest.mark.parametrize('workers',[1,2])
def test_three_time_oracles_keep_worker_phases_and_disjoint_batches(workers):
    campaign,events,owners,counts=_time_campaign_observations(workers)
    result=campaign.assess(events,owners,counts,0,16,workers,True)
    assert [b['label'] for b in result['batches']]==campaign.BATCHES
    assert result['peak_held_sql_connections']==2*workers
    assert len(result['phase_seconds_by_worker'])==workers


@pytest.mark.parametrize('mutation',['exit','counts','skip','worker','prepare','zero_time','nan_time',
                                    'cleanup','host_identity','owner_close','prepared_twice','batch_overlap',
                                    'connections','missing_hold','child_identity','child_overlap','case_census'])
def test_three_time_checkpoint_cannot_hide_missing_or_failed_evidence(mutation):
    campaign,events,owners,counts=_time_campaign_observations()
    code=0
    if mutation=='exit':code=1
    elif mutation=='counts':counts['tests']=17
    elif mutation=='skip':counts['skipped']=1
    elif mutation=='worker':events[0]['worker']='gw2'
    elif mutation=='prepare':events=[e for e in events if not (e['event']=='phase' and e['name']=='prepare')]
    elif mutation in ('zero_time','nan_time'):events[0]['seconds']=0 if mutation=='zero_time' else float('nan')
    elif mutation=='cleanup':next(e for e in owners if e['event']=='final')['host_reaped']=False
    elif mutation=='host_identity':
        for e in owners:
            if e['event']=='final':e['host_pid']=100
    elif mutation=='owner_close':owners.remove(next(e for e in owners if e['event']=='close'))
    elif mutation=='prepared_twice':owners.append(copy.deepcopy(next(e for e in owners if e['event']=='prepared')))
    elif mutation=='batch_overlap':next(e for e in events if e['event']=='case_start' and e['batch']=='observed_1')['at_ns']=1
    elif mutation=='connections':next(e for e in events if e['event']=='sql_hold_begin')['connections']=1
    elif mutation=='missing_hold':events.remove(next(e for e in events if e['event']=='sql_hold_end'))
    elif mutation=='child_identity':next(e for e in events if e['event']=='child_open' and e['child']==2)['child']=0
    elif mutation=='child_overlap':next(e for e in events if e['event']=='child_open' and e['child']==2)['at_ns']=1002
    else:next(e for e in events if e['event']=='case_start')['case']=7
    with pytest.raises(ValueError):campaign.assess(events,owners,counts,code,16,2,True)


@pytest.mark.parametrize('mutation',[None,'rewritten_fixture','extra_file','deleted_first'])
def test_second_test_delta_is_measured_not_declared(mutation):
    campaign,_,_,_=_time_campaign_observations()
    before={'application.py':'a','conftest.py':'b','pytest.ini':'c','test_first.py':'d'}
    after={**before,'test_second.py':'e'}
    if mutation=='rewritten_fixture':after['conftest.py']='different'
    elif mutation=='extra_file':after['extra.py']='x'
    elif mutation=='deleted_first':del after['test_first.py']
    if mutation:
        with pytest.raises(ValueError):campaign.validate_second_edit(before,after)
    else:campaign.validate_second_edit(before,after)


@pytest.mark.parametrize('consumed', [False, True])
def test_capture_failure_keeps_original_and_finalizes_preserved_or_consumed_source(tmp_path, consumed):
    result, events = helper.fake_suite(tmp_path, '''
from contextlib import contextmanager
@contextmanager
def failed_snapshot(self):
    record('capture.attempt')
    self.closed = CONSUMED
    raise ValueError('ORIGINAL_CAPTURE_FAILURE')
    yield
DB.snapshot = failed_snapshot
'''.replace('CONSUMED', repr(consumed)), '''
def test_first(mariamem_fork):
    raise AssertionError('BODY_MUST_NOT_RUN')
def test_second(mariamem_fork):
    raise AssertionError('BODY_MUST_NOT_RUN')
''', False)
    assert result.returncode == 1
    assert 'ValueError: ORIGINAL_CAPTURE_FAILURE' in result.stdout
    assert 'mariamem capture:' in result.stdout
    assert 'AssertionError: BODY_MUST_NOT_RUN' not in result.stdout
    assert events == ['start', 'wait:source', 'capture.attempt', 'source.close']
