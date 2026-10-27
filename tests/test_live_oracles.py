"""Reject evidence corruption using actual observed public Live browser events."""
import copy
import importlib.util
import json
from pathlib import Path

import pytest

HERE=Path(__file__).parent/'live_acceptance'
spec=importlib.util.spec_from_file_location('public_live_assessor',HERE/'run.py')
runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)
fixtures=json.loads((HERE/'oracle-fixtures.json').read_text())['events']
reference=json.loads((HERE/'native-reference.json').read_text())['interpreters']['3.11']['observation']


def accepted(kind,events,**changes):
    args=dict(code=1,counts=dict(tests=3,errors=0,failures=1,skipped=0),events=events,
              failures=[dict(name='test_02_fail_after_commit',message='E2E_EXPECTED_FAILURE_AFTER_COMMIT')],reference=reference['python' if kind=='python' else 'go'])
    args.update(changes)
    return runner.assess(kind,**args)


@pytest.mark.parametrize('kind',['python','go-live','go-fork'])
def test_real_observation_passes_but_unrelated_failure_does_not(kind):
    assert accepted(kind,fixtures[kind])
    assert not accepted(kind,fixtures[kind],code=0)
    assert not accepted(kind,fixtures[kind],failures=[dict(name='test_02_fail_after_commit',message='connection lost')])


@pytest.mark.parametrize('kind',['python','go-live','go-fork'])
@pytest.mark.parametrize('event,field,value',[
    ('case_before','rows',[['LEAK',1,'ready']]),
    ('case_after','rows',[]),
    ('guest_host_cleanup','directory_removed',False),
    ('app_reaped','reaped',False),
    ('baseline_captured','source_consumed',False),
    ('browser_started','version','wrong'),
])
def test_reject_data_cleanup_and_browser_corruption(kind,event,field,value):
    events=copy.deepcopy(fixtures[kind]);next(e for e in events if e['event']==event)[field]=value
    assert not accepted(kind,events)


@pytest.mark.parametrize('kind',['python','go-live'])
@pytest.mark.parametrize('event,field,value',[
    ('case_before','pid',1),
    ('case_before','generation',99),
    ('case_before','db_port',1),
    ('reset_committed','generation',99),
    ('live_closed','active_before_close',1),
    ('live_closed','close_returned',False),
])
def test_reject_live_identity_and_drain_corruption(kind,event,field,value):
    events=copy.deepcopy(fixtures[kind]);next(e for e in events if e['event']==event)[field]=value
    assert not accepted(kind,events)


def test_go_app_abnormal_exit_is_not_cleanup_success():
    events=copy.deepcopy(fixtures['go-live']);next(e for e in events if e['event']=='app_reaped')['exit_code']=1
    assert not accepted('go-live',events)
