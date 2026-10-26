"""Negative oracles: a browser exit or expected failure alone cannot mean PASS."""
import copy
import importlib.util
from pathlib import Path
import pytest

spec=importlib.util.spec_from_file_location('e2e_native_runner',Path(__file__).parent/'e2e_native_control/run.py')
runner=importlib.util.module_from_spec(spec);spec.loader.exec_module(runner)


def fixture(kind):
    before,after=[],[];events=[]
    names=['test_01_commit_order','test_02_fail_after_commit','test_03_next_case_sees_only_baseline']
    baseline=[['SEED',2,'ready']]
    for i,name in enumerate(names):
        pid=10 if kind=='python' else 10+i;schema='app' if kind=='python' else 'app'+str(i)
        if kind=='go' or i==0:
            events += [dict(event='app_started',pid=pid,schema=schema),dict(event='app_ready',pid=pid,db_version='12.3.3-MariaDB'),dict(event='app_reaped',pid=pid,reaped=True,exit_code=0),dict(event='schema_removed',schema=schema)]
        before.append(dict(event='case_before',name=name,pid=pid,http_url='http://local',schema=schema,rows=baseline))
        after.append(dict(event='case_after',name=name,rows=baseline+[[['ORDER-A',3,'ready'],['FAILED-A',4,'ready']][i]] if i<2 else baseline))
        if kind=='python':events.append(dict(event='native_reset'))
    events+=before+after+[dict(event='browser_started',version='141.0.7390.37'),dict(event='browser_closed')]
    if kind=='python':events.append(dict(event='migration_chain',revisions=['0001_initial','0002_status']))
    return dict(code=1,counts=dict(tests=3,errors=0,failures=1,skipped=0),events=events,
                failures=[dict(name=names[1],message='E2E_EXPECTED_FAILURE_AFTER_COMMIT')])


@pytest.mark.parametrize('kind',['python','go'])
def test_control_rejects_cleanup_data_and_failure_mutations(kind):
    good=fixture(kind);assert runner.assess(kind,**good)
    for event,key,value in [('app_reaped','reaped',False),('case_before','rows',[]),('case_after','rows',[])]:
        bad=copy.deepcopy(good);next(e for e in bad['events'] if e['event']==event)[key]=value
        assert not runner.assess(kind,**bad)
    for missing in ['app_ready','browser_closed','schema_removed']:
        bad=copy.deepcopy(good);bad['events']=[e for e in bad['events'] if e['event']!=missing]
        assert not runner.assess(kind,**bad)
    for counts in [dict(good['counts'],errors=1),dict(good['counts'],skipped=1),dict(good['counts'],failures=0)]:
        assert not runner.assess(kind,**dict(good,counts=counts))
    assert not runner.assess(kind,**dict(good,code=0))
    assert not runner.assess(kind,**dict(good,failures=[dict(name='wrong_test',message='E2E_EXPECTED_FAILURE_AFTER_COMMIT')]))
    assert not runner.assess(kind,**dict(good,failures=[dict(name=good['failures'][0]['name'],message='unrelated failure')]))


def test_python_rejects_process_restart_or_missing_reset():
    good=fixture('python')
    bad=copy.deepcopy(good);[e for e in bad['events'] if e['event']=='case_before'][1]['pid']=999
    assert not runner.assess('python',**bad)
    bad=copy.deepcopy(good);bad['events']=[e for e in bad['events'] if e['event']!='native_reset']
    assert not runner.assess('python',**bad)
