"""Portable resource-meter parsing/accounting; real probes are manual controls."""
import importlib.util
from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('p1_resource_probe', ROOT/'tests/fixture_entry_acceptance/resource_probe.py')
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)

VALID = b'p123\0\nf3\0tREG\0D0x1\0i42\0k0\0s8192\0\nf4\0tREG\0D0x1\0i42\0k0\0s8192\0\n'


def test_duplicate_descriptors_do_not_duplicate_unlinked_file_bytes():
    result = probe.parse_lsof(VALID, {123})
    assert result['fd_total'] == 2
    assert result['fd_backed_unlinked_logical_bytes'] == 8192
    assert len(result['unlinked_files']) == 1


@pytest.mark.parametrize('raw,pids', [
    (b'', {123}), (VALID[:-2], {123}), (VALID, {123,456}),
    (VALID.replace(b'k0\0', b''), {123}),
    (VALID.replace(b's8192\0', b's-1\0'), {123}),
    (VALID.replace(b'f4\0', b'f3\0'), {123}),
    (VALID.replace(b's8192\0', b's4096\0', 1), {123}),
    (VALID.replace(b'tREG\0', b''), {123}),
])
def test_missing_partial_or_unstable_counters_are_not_zero(raw, pids):
    with pytest.raises(ValueError):
        probe.parse_lsof(raw, pids)


def test_tool_warning_is_not_partial_success(monkeypatch):
    monkeypatch.setattr(probe.shutil, 'which', lambda _: '/tool/lsof')
    monkeypatch.setattr(probe.subprocess, 'run', lambda *a, **kw:
                        subprocess.CompletedProcess(a, 0, VALID, b'permission denied'))
    with pytest.raises(RuntimeError, match='UNVERIFIED'):
        probe.collect({123})


def allocation_data():
    return dict(pid=123,fd_count=2,fds=[dict(fd=fd,regular=True,device=1,inode=42,
                links=0,blocks=8,logical_bytes=4*1048576) for fd in (3,4)])


def test_allocation_is_blocks_not_logical_size_and_is_deduplicated():
    result=probe.summarize_allocated(allocation_data(),123)
    assert result['fd_count']==2 and result['unlinked_allocated_bytes']==4096
    assert result['unlinked_files']==[dict(device=1,inode=42,allocated_bytes=4096,logical_bytes=4*1048576)]


@pytest.mark.parametrize('mutation', ['pid','count','duplicate_fd','missing_blocks','negative_blocks',
                                    'unknown_regular','missing_links','changing_file'])
def test_unverified_allocation_cannot_be_admitted(mutation):
    data=allocation_data()
    if mutation=='pid': data['pid']=456
    elif mutation=='count': data['fd_count']=3
    elif mutation=='duplicate_fd': data['fds'][1]['fd']=3
    elif mutation=='missing_blocks': del data['fds'][0]['blocks']
    elif mutation=='negative_blocks': data['fds'][0]['blocks']=-1
    elif mutation=='unknown_regular': del data['fds'][0]['regular']
    elif mutation=='missing_links': del data['fds'][0]['links']
    else: data['fds'][1]['blocks']=16
    with pytest.raises(ValueError,match='UNVERIFIED'):
        probe.summarize_allocated(data,123)


def test_process_tree_allocation_deduplicates_shared_files():
    first=probe.summarize_allocated(allocation_data(),123)
    second=probe.summarize_allocated(dict(allocation_data(),pid=456),456)
    merged=probe.merge_process_allocations({123:first,456:second})
    assert merged['fd_total']==4 and merged['unlinked_allocated_bytes']==4096
    assert len(merged['unlinked_files'])==1


@pytest.mark.parametrize('mutation', ['empty','subtotal','missing','conflict','duplicate','pid','wrong_identity'])
def test_process_tree_allocation_rejects_incomplete_or_inconsistent_census(mutation):
    import copy
    first=probe.summarize_allocated(allocation_data(),123)
    second=probe.summarize_allocated(dict(allocation_data(),pid=456),456)
    observations={123:first,456:second}
    if mutation=='empty':observations={}
    elif mutation=='subtotal':observations[123]['unlinked_allocated_bytes']=0
    elif mutation=='missing':del observations[123]['unlinked_files']
    elif mutation=='conflict':
        observations[456]['unlinked_files'][0]['allocated_bytes']=8192
        observations[456]['unlinked_allocated_bytes']=8192
    elif mutation=='duplicate':
        observations[123]['unlinked_files'].append(copy.deepcopy(observations[123]['unlinked_files'][0]))
    elif mutation=='pid':observations['123']=observations.pop(123)
    else:observations[123]['pid']=456
    with pytest.raises(ValueError,match='UNVERIFIED'):
        probe.merge_process_allocations(observations)


def _window_observations():
    return {123:dict(pid=123,start_unix_ns=100,end_unix_ns=110),
            456:dict(pid=456,start_unix_ns=112,end_unix_ns=120)}


def test_process_window_requires_both_endpoint_censuses_and_bounded_samples():
    result=probe.validate_process_window({123,456},{123,456},_window_observations(),max_window_ns=20)
    assert result['processes']==[123,456] and result['atomic'] is False
    assert result['start_unix_ns']==100 and result['end_unix_ns']==120


@pytest.mark.parametrize('mutation',['missing_process','extra_process','changed_tree','wrong_identity',
                                     'backward_clock','missing_time','window','invalid_pid','bad_budget'])
def test_process_window_rejects_incomplete_or_unaligned_observations(mutation):
    before={123,456};after={123,456};observations=_window_observations();budget=20
    if mutation=='missing_process':del observations[456]
    elif mutation=='extra_process':observations[789]=dict(pid=789,start_unix_ns=100,end_unix_ns=110)
    elif mutation=='changed_tree':after.remove(456)
    elif mutation=='wrong_identity':observations[456]['pid']=123
    elif mutation=='backward_clock':observations[456]['end_unix_ns']=111
    elif mutation=='missing_time':del observations[456]['start_unix_ns']
    elif mutation=='window':observations[456]['end_unix_ns']=121
    elif mutation=='invalid_pid':before.add(-1);after.add(-1);observations[-1]={}
    else:budget=True
    with pytest.raises(ValueError,match='UNVERIFIED'):
        probe.validate_process_window(before,after,observations,max_window_ns=budget)
