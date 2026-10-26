"""The success assessor must reject corruption of observed browser/ownership evidence."""
import copy
import importlib.util
import json
from pathlib import Path

import pytest

HERE=Path(__file__).parent/'e2e_guest_spike'
spec=importlib.util.spec_from_file_location('guest_assessor',HERE/'run.py')
runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
observed=json.loads((HERE/'assessment-fixtures.json').read_text())['events']
reference=json.loads((HERE/'native-reference.json').read_text())['interpreters']['3.11']['observation']


def assess(kind,events,**overrides):
    args=dict(code=1,counts=dict(tests=3,errors=0,failures=1,skipped=0),events=events,
              failures=[dict(name='test_02_fail_after_commit',message='E2E_EXPECTED_FAILURE_AFTER_COMMIT')],reference=reference[kind])
    args.update(overrides)
    return runner.browser_assessment(kind,**args)


@pytest.mark.parametrize('kind',['python','go'])
def test_actual_observation_passes_and_unrelated_failure_does_not(kind):
    assert assess(kind,observed[kind])
    assert not assess(kind,observed[kind],code=0)
    assert not assess(kind,observed[kind],failures=[dict(name='test_02_fail_after_commit',message='connection lost')])
    assert not assess(kind,observed[kind],counts=dict(tests=3,errors=1,failures=1,skipped=0))


@pytest.mark.parametrize('kind',['python','go'])
@pytest.mark.parametrize('event,field,value',[
    ('case_before','rows',[['LEAK',1,'ready']]),
    ('case_after','rows',[]),
    ('app_reaped','reaped',False),
    ('guest_host_cleanup','directory_removed',False),
    ('baseline_captured','source_consumed',False),
    ('browser_started','version','wrong'),
])
def test_reject_data_lifetime_and_browser_defects(kind,event,field,value):
    events=copy.deepcopy(observed[kind])
    next(e for e in events if e['event']==event)[field]=value
    assert not assess(kind,events)


@pytest.mark.parametrize('event,field,value',[
    ('guest_reset','child_id','wrong-generation'),
    ('guest_reset','port',1),
    ('guest_reset','old_closed',False),
    ('relay_closed','forced_clients',1),
    ('relay_closed','threads_stopped',False),
    ('case_before','pid',1),
])
def test_reject_reset_binding_and_same_app_defects(event,field,value):
    events=copy.deepcopy(observed['python'])
    next(e for e in events if e['event']==event)[field]=value
    assert not assess('python',events)


def test_reject_unclosed_go_child():
    events=copy.deepcopy(observed['go'])
    next(e for e in events if e['event']=='guest_child_closed')['closed']=False
    assert not assess('go',events)
