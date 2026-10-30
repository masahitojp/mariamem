"""Fail-closed counter arithmetic controls; these are not runtime admission evidence."""
import copy
import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location('p1_resource_guard',
    Path(__file__).parent / 'fixture_entry_acceptance/resource_guard.py')
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)

LIMITS = dict(incremental_rss_ceiling_bytes=100, owned_disk_ceiling_bytes=200,
              min_free_disk_bytes=300, min_fd_headroom=64,
              active_children_ceiling=2, physical_connections_ceiling=4)
SAMPLE = dict(process_tree_rss_bytes=200, available_memory_bytes=50,
              linked_allocated_bytes=70, unlinked_allocated_bytes=130,
              disk_free_bytes=300, active_children=2, physical_connections=4,
              fd_by_process={'123': {'count': 10, 'soft_limit': 74},
                             '456': {'count': 30, 'soft_limit': 100}})


def test_limits_are_inclusive_and_evaluate_all_fd_owners():
    assert guard.evaluate(SAMPLE, LIMITS, 100) is None
    sample=copy.deepcopy(SAMPLE)
    sample['fd_by_process']['456']['soft_limit']=93
    assert guard.evaluate(sample,LIMITS,100)=='FD headroom guard'


@pytest.mark.parametrize('key,value,expected', [
    ('process_tree_rss_bytes',201,'incremental process-tree RSS guard'),
    ('linked_allocated_bytes',71,'owned disk guard'),
    ('unlinked_allocated_bytes',131,'owned disk guard'),
    ('disk_free_bytes',299,'free disk guard'),
    ('active_children',3,'active child guard'),
    ('physical_connections',5,'physical connection guard'),
])
def test_each_ceiling_stops_admission(key,value,expected):
    sample=copy.deepcopy(SAMPLE);sample[key]=value
    assert guard.evaluate(sample,LIMITS,100)==expected


@pytest.mark.parametrize('key', list(SAMPLE))
def test_missing_counter_is_unverified_even_when_another_limit_is_exceeded(key):
    sample=copy.deepcopy(SAMPLE);del sample[key]
    if key!='process_tree_rss_bytes':sample['process_tree_rss_bytes']=201
    with pytest.raises(guard.UnverifiedResource):guard.evaluate(sample,LIMITS,100)


@pytest.mark.parametrize('value',[None,True,-1,float('nan'),float('inf'),'12'])
def test_unusable_counter_never_authorizes(value):
    sample=copy.deepcopy(SAMPLE);sample['physical_connections']=value
    with pytest.raises(guard.UnverifiedResource):guard.evaluate(sample,LIMITS,100)


@pytest.mark.parametrize('field,value', [('count',0),('count',1.5),('count',True),
                                       ('soft_limit',9),('soft_limit',float('inf'))])
def test_invalid_fd_census_is_unverified(field,value):
    sample=copy.deepcopy(SAMPLE);sample['fd_by_process']['123'][field]=value
    with pytest.raises(guard.UnverifiedResource):guard.evaluate(sample,LIMITS,100)


@pytest.mark.parametrize('key',list(LIMITS))
def test_missing_limit_is_unverified(key):
    limits=LIMITS.copy();del limits[key]
    with pytest.raises(guard.UnverifiedResource):guard.evaluate(SAMPLE,limits,100)


def test_unavailable_baseline_and_memory_are_unverified():
    with pytest.raises(guard.UnverifiedResource):guard.evaluate(SAMPLE,LIMITS,0)
    sample=copy.deepcopy(SAMPLE);sample['available_memory_bytes']=0
    with pytest.raises(guard.UnverifiedResource):guard.evaluate(sample,LIMITS,100)


def test_admit_invokes_child_once_only_after_verified_observation():
    events=[]
    result=guard.admit(lambda: (events.append('observed'),SAMPLE)[1], LIMITS,100,
                       lambda: (events.append('child'),object())[1])
    assert result is not None and events==['observed','child']


@pytest.mark.parametrize('mode',['fd','missing','collector_error'])
def test_failed_admission_never_invokes_child_and_keeps_observation_cause(mode):
    events=[]; sample=copy.deepcopy(SAMPLE)
    if mode=='fd':sample['fd_by_process']['456']['soft_limit']=93
    if mode=='missing':del sample['available_memory_bytes']
    original=OSError('observer failure')
    def collect():
        events.append('observed')
        if mode=='collector_error':raise original
        return sample
    with pytest.raises(guard.AdmissionStopped) as error:
        guard.admit(collect,LIMITS,100,lambda:events.append('child'))
    assert events==['observed']
    if mode=='collector_error':assert error.value.__cause__ is original
    elif mode=='missing':assert isinstance(error.value.__cause__,guard.UnverifiedResource)
    else:assert 'FD headroom guard' in str(error.value)


def test_original_child_error_is_not_reclassified_as_observer_failure():
    original=RuntimeError('child failed')
    def child():raise original
    with pytest.raises(RuntimeError) as error:guard.admit(lambda:SAMPLE,LIMITS,100,child)
    assert error.value is original
