"""Failure-oracle classification only; no guest, Alembic import or native build."""
import copy
import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location('migration_spike', Path(__file__).parent/'preparation_migration_spike/run.py')
spike = importlib.util.module_from_spec(spec)
spec.loader.exec_module(spike)


def error_events(stage):
    return [
        {'event':'source_start'}, {'event':'prepare_start'},
        {'event':'preparation_original_profile_refused'},
        {'event':'preparation_engines_disposed'},
        {'event':'prepare_error','stage':stage,'oracle':{'migration':'revision_failure','seed':'seed_failure'}[stage],'exception':'ProgrammingError',
         'original_exception':'ProgrammingError','errno':1146},
        {'event':'source_cleanup','closed':True,'host_reaped':True,'directory_removed':True},
    ]


@pytest.mark.parametrize('mode,stage', [('revision_failure','migration'),('seed_failure','seed')])
def test_exact_preparation_failure_is_accepted(mode, stage):
    assert spike.assess(mode,1,{'tests':2,'errors':2,'failures':0,'skipped':0},error_events(stage),0)


@pytest.mark.parametrize('fault', ['wrong_statement','wrong_stage','wrong_errno','wrong_exception','snapshot','test_ran','host_alive','contacts','exit','skip'])
def test_unrelated_failure_or_leaked_lifetime_is_rejected(fault):
    events=error_events('migration');counts={'tests':2,'errors':2,'failures':0,'skipped':0}
    code,contacts=1,0
    if fault=='wrong_statement':events[4]['oracle']=None
    if fault=='wrong_stage':events[4]['stage']='seed'
    if fault=='wrong_errno':events[4]['errno']=2003
    if fault=='wrong_exception':events[4]['original_exception']='AssertionError'
    if fault=='snapshot':events.append({'event':'snapshot_attempt'})
    if fault=='test_ran':events.append({'event':'test_pass'})
    if fault=='host_alive':events[5]['host_reaped']=False
    if fault=='contacts':contacts=1
    if fault=='exit':code=2
    if fault=='skip':counts.update(errors=1,skipped=1)
    assert not spike.assess('revision_failure',code,counts,events,contacts)


def test_success_requires_two_independent_children():
    events=[e for e in error_events('migration') if e['event']!='prepare_error']
    events.extend([{'event':'prepared_state'},{'event':'snapshot_attempt'},
                   {'event':'snapshot_success'},{'event':'preparation_disconnected','active_connections':0},
                   {'event':'test_pass','name':'commit','child':'A'},
                   {'event':'test_pass','name':'independent_initial_state','child':'B'}])
    counts={'tests':2,'errors':0,'failures':0,'skipped':0}
    assert spike.assess('success',0,counts,events,0)
    changed=copy.deepcopy(events);changed[-1]['child']='A'
    assert not spike.assess('success',0,counts,changed,0)
