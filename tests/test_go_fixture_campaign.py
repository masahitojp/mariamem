"""Missing measurements, stale receipts and guard breaches cannot become G1 PASS."""
import copy
import json
import subprocess
from pathlib import Path
import sys
import time
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import go_fixture_campaign as campaign

RESOURCES = json.loads((ROOT / 'docs/reviews/v06x-fixture-acceptance.json').read_text())['resources']


@pytest.mark.parametrize('rss', [0, 4096])
def test_exit_during_collection_is_preserved_but_not_a_live_sample(monkeypatch, rss):
    monkeypatch.setattr(campaign, 'process_rss', lambda pid: {str(pid): rss})
    monkeypatch.setattr(campaign, 'available_memory', lambda: (1024, 'test counter'))
    proc = SimpleNamespace(pid=123, poll=lambda: 0)
    sample, ended = campaign.collect_sample(proc, time.monotonic())
    assert sample is None
    assert ended['members'] == {'123': rss}
    assert ended['returncode'] == 0
    assert ended['reason'] == 'process exited during collection'


def test_live_zero_rss_still_fails_closed(monkeypatch):
    monkeypatch.setattr(campaign, 'process_rss', lambda pid: {str(pid): 0})
    monkeypatch.setattr(campaign, 'available_memory', lambda: (1024, 'test counter'))
    def wait(*, timeout):
        assert timeout == .05
        raise subprocess.TimeoutExpired('owned-process', timeout)
    with pytest.raises(campaign.LiveRSSUnavailable, match='live runtime process RSS') as caught:
        campaign.collect_sample(SimpleNamespace(pid=123, poll=lambda: None, wait=wait), time.monotonic())
    assert caught.value.sample['members'] == {'123': 0}


@pytest.mark.parametrize('code', [0, 2])
def test_zero_rss_before_waitpid_readiness_requires_bounded_actual_exit(monkeypatch, code):
    monkeypatch.setattr(campaign, 'process_rss', lambda pid: {str(pid): 0})
    monkeypatch.setattr(campaign, 'available_memory', lambda: (1024, 'test counter'))
    def wait(*, timeout):
        assert timeout == .05
        return code
    sample, ended = campaign.collect_sample(SimpleNamespace(pid=123, poll=lambda: None, wait=wait), time.monotonic())
    assert sample is None and ended['members'] == {'123': 0}
    assert ended['returncode'] == code
    assert ended['exit_confirmation_timeout_seconds'] == .05
    assert ended['exit_confirmation_elapsed_seconds'] >= 0
    assert ended['reason'] == 'process exited within zero-RSS confirmation window'


def test_live_rss_is_retained(monkeypatch):
    monkeypatch.setattr(campaign, 'process_rss', lambda pid: {str(pid): 4096})
    monkeypatch.setattr(campaign, 'available_memory', lambda: (1024, 'test counter'))
    sample, ended = campaign.collect_sample(SimpleNamespace(pid=123, poll=lambda: None), time.monotonic())
    assert ended is None and sample['process_tree_rss_bytes'] == 4096


@pytest.mark.parametrize('last', ['zero_after_exit', 'missing_after_exit', 'nonzero_exit', 'live_zero',
                                  'zero_before_waitpid', 'nonzero_before_waitpid'])
def test_observer_exit_race_and_counter_failures(tmp_path, monkeypatch, last):
    delayed = last in ('live_zero', 'zero_before_waitpid', 'nonzero_before_waitpid')
    polls = iter([None, None] * 3 + [None, None, None, 0] if delayed
                 else [None, None] * 3 + [None, 2 if last == 'nonzero_exit' else 0])
    code = 2 if last in ('nonzero_exit', 'nonzero_before_waitpid') else 0
    def wait(timeout=None):
        if timeout is not None and last == 'live_zero':
            raise subprocess.TimeoutExpired('test-process', timeout)
        return code
    proc = SimpleNamespace(pid=123, poll=lambda: next(polls, code), wait=wait)
    monkeypatch.setattr(campaign.subprocess, 'Popen', lambda *args, **kwargs: proc)
    monkeypatch.setattr(campaign, 'available_memory', lambda: (1024, 'test counter'))
    monkeypatch.setattr(campaign.time, 'sleep', lambda seconds: None)
    calls = 0
    def read(pid):
        nonlocal calls
        calls += 1
        if calls == 4 and last == 'missing_after_exit':
            raise ValueError('runtime process RSS unavailable')
        return {str(pid): 0 if calls == 4 else 4096}
    monkeypatch.setattr(campaign, 'process_rss', read)
    if last in ('live_zero', 'nonzero_exit', 'nonzero_before_waitpid'):
        with pytest.raises(ValueError, match='runtime/guard/counter failure'):
            campaign.observe(['test-process'], tmp_path, {}, RESOURCES)
    else:
        campaign.observe(['test-process'], tmp_path, {}, RESOURCES)
    result = json.loads((tmp_path / 'os.json').read_text())
    assert len(result['samples']) == 3
    if last == 'live_zero':
        assert result['counter_errors'] and result['result'] == 'UNVERIFIED'
        assert result['failed_observations'][0]['members'] == {'123': 0}
    else:
        assert result['terminal_observations'][0]['returncode'] == code
        assert not result['counter_errors']
        if last == 'zero_after_exit':
            assert result['terminal_observations'][0]['process_tree_rss_bytes'] == 0


def observations(cap=2, parallel=4):
    def sample(label, count=0, at=0):
        return dict(label=label, unix_ns=at, fd=10 + count, fd_soft_limit=1024,
                    linked_temp_bytes=0, unlinked_file_bytes=0,
                    disk_free_bytes=32 << 30, children=0, baselines=count,
                    physical_pool_connections=0)
    go = dict(result='PASS', cleanup_complete=True, stop_reason='', pid=999,
              cap=cap, parallel=parallel, peak_children=min(cap, parallel),
              peak_physical_pool_connections=2, new_fixture_seconds=.1, fixture_close_seconds=.1,
              guards={k: RESOURCES[k] for k in ('owned_disk_ceiling_bytes', 'min_free_disk_bytes', 'min_fd_headroom')},
              samples=[sample('baseline')] + [s for i in (1, 2, 3) for s in
                       (sample('retained_' + str(i), i, i * 1_000_000_000),
                        sample('retained_end_' + str(i), i, i * 1_000_000_000 + 500_000_000))] + [sample('final')],
              batches=[dict(label=name, elapsed_seconds=.1) for name in
                       ('warmup', 'observed_1', 'observed_2', 'observed_3')],
              cases=[dict(name='TestFixtureCampaign/' + batch + '/' + str(i),
                          admission_seconds=.1, sql_seconds=.1, cleanup_seconds=.1)
                     for batch in ('warmup', 'observed_1', 'observed_2', 'observed_3') for i in range(4)],
              phases=[dict(name=name, seconds=.1) for name in ('start', 'prepare', 'disconnect', 'capture')])
    observed = dict(result='PASS', counter_errors=[], stop_reason=None,
                    samples=[dict(unix_ns=i * 1_000_000_000 + 1, process_tree_rss_bytes=1000,
                                  members={'999': 1000}, available_memory_bytes=16 << 30)
                             for i in (1, 2, 3)])
    return go, observed


def test_complete_mode_has_retention_rss_fd_connection_temp_summary():
    go, observed = observations()
    result = campaign.validate_mode(go, observed, 2, 4, RESOURCES)
    assert result['fd_baseline_peak_final'] == [10, 13, 10]
    assert [r['baselines'] for r in result['retention']] == [1, 2, 3]


@pytest.mark.parametrize('mutation', [
    'stopped', 'cleanup', 'wrong_cap', 'exceeded_children', 'connections', 'warmup',
    'case', 'phase', 'prepare_time', 'fd_baseline', 'fd_headroom', 'unlinked_disk',
    'free_disk', 'retained', 'leaked_backing', 'final_fd', 'os_missing', 'rss',
    'available', 'wrong_pid', 'rss_guard', 'alignment', 'guard_values', 'duplicate_case', 'zero_fd',
])
def test_missing_or_bad_observation_is_rejected(mutation):
    go, observed = observations()
    if mutation == 'stopped': go['stop_reason'] = 'guard fired'
    elif mutation == 'cleanup': go['cleanup_complete'] = False
    elif mutation == 'wrong_cap': go['cap'] = 1
    elif mutation == 'exceeded_children': go['peak_children'] = 3
    elif mutation == 'connections': go['peak_physical_pool_connections'] = 5
    elif mutation == 'warmup': go['batches'].pop(0)
    elif mutation == 'case': go['cases'].pop()
    elif mutation == 'phase': go['cases'][0]['cleanup_seconds'] = 0
    elif mutation == 'prepare_time': go['phases'] = []
    elif mutation == 'fd_baseline': go['samples'][0]['label'] = 'other'
    elif mutation == 'fd_headroom': go['samples'][0]['fd_soft_limit'] = 16
    elif mutation == 'unlinked_disk': go['samples'][1]['unlinked_file_bytes'] = 9 << 30
    elif mutation == 'free_disk': go['samples'][0]['disk_free_bytes'] = 1
    elif mutation == 'retained': go['samples'][3]['baselines'] = 1
    elif mutation == 'leaked_backing': go['samples'][-1]['unlinked_file_bytes'] = 4096
    elif mutation == 'final_fd': go['samples'][-1]['fd'] = 30
    elif mutation == 'os_missing': observed['samples'] = []
    elif mutation == 'rss': observed['samples'][0]['process_tree_rss_bytes'] = None
    elif mutation == 'available': observed['samples'][0]['available_memory_bytes'] = 0
    elif mutation == 'wrong_pid': observed['samples'][0]['members'] = {'1000': 1000}
    elif mutation == 'rss_guard':
        observed['samples'][1]['process_tree_rss_bytes'] += 3 << 30
        observed['samples'][1]['members']['999'] += 3 << 30
    elif mutation == 'alignment': observed['samples'][0]['unix_ns'] = 10_000_000_000
    elif mutation == 'guard_values': go['guards']['min_fd_headroom'] = 1
    elif mutation == 'duplicate_case': go['cases'][0]['name'] = go['cases'][1]['name']
    elif mutation == 'zero_fd': go['samples'][0]['fd'] = 0
    with pytest.raises(ValueError):
        campaign.validate_mode(go, observed, 2, 4, RESOURCES)


def receipt(tmp_path, monkeypatch):
    monkeypatch.setattr(campaign, 'source_identity', lambda root: 'source-inventory')
    report = dict(result='PASS', source_commit='a' * 40, source_inventory_sha256='source-inventory',
                  toolchain='go1.26.10', host=dict(system='Darwin', architecture='arm64', version='15.7'),
                  guard_probe='PRE_ADMISSION_FD_STOP_CONFIRMED',
                  inputs_sha256={p: campaign.digest(ROOT / p) for p in campaign.input_paths(RESOURCES)}, modes=[],
                  three_time_outcomes=dict(first_test_setup=dict(elapsed_seconds=1, authored_lines=30,
                      command=['go', 'test'], steps=['copy', 'test']),
                      second_test_edits=dict(added_lines=10, repeated_lifecycle_lines=0,
                      command=['go', 'test'], steps=['add', 'test']),
                      repeat_batch_elapsed='per-mode warmup plus three observed batches',
                      human_authoring_minutes=None, acquisition_state='unmeasured; existing Go toolchain/module cache'))
    for cap in (1, 2):
        for parallel in (1, 4):
            path = tmp_path / ('cap%d-parallel%d' % (cap, parallel)); path.mkdir()
            go, observed = observations(cap, parallel)
            campaign.write(path / 'go.json', go); campaign.write(path / 'os.json', observed)
            (path / 'stdout.txt').write_text('PASS')
            report['modes'].append(campaign.validate_mode(go, observed, cap, parallel, RESOURCES))
    (tmp_path / 'first-test.txt').write_text('PASS'); (tmp_path / 'second-test.txt').write_text('PASS')
    probe = tmp_path / 'guard-probe'; probe.mkdir()
    campaign.write(probe / 'go.json', dict(result='STOP', stop_reason='FD headroom guard',
        cleanup_complete=True, peak_children=0, new_fixture_seconds=0, phases=[],
        samples=[dict(children=0, baselines=0, physical_pool_connections=0)]))
    campaign.write(probe / 'os.json', {'returncode': 1})
    (probe / 'stdout.txt').write_text('expected STOP')
    campaign.write(tmp_path / 'host.json', report)
    refresh_sums(tmp_path)
    return report


def refresh_sums(path):
    campaign.write(path / 'SHA256SUMS.json', {p.relative_to(path).as_posix(): campaign.digest(p)
                   for p in path.rglob('*') if p.is_file() and p.name != 'SHA256SUMS.json'})


@pytest.mark.parametrize('mutation', ['none', 'source', 'inventory', 'host', 'toolchain', 'missing_modes',
                                    'summary', 'input', 'time', 'lifecycle', 'cold', 'checksum', 'missing_file', 'guard_probe'])
def test_source_bound_receipt_is_complete_and_checked(tmp_path, monkeypatch, mutation):
    report = receipt(tmp_path, monkeypatch)
    if mutation == 'source': report['source_commit'] = 'b' * 40
    elif mutation == 'inventory': report['source_inventory_sha256'] = 'wrong'
    elif mutation == 'host': report['host']['architecture'] = 'x86_64'
    elif mutation == 'toolchain': report['toolchain'] = 'go1.27.3'
    elif mutation == 'missing_modes': report['modes'].pop()
    elif mutation == 'summary': report['modes'][0]['sampled_rss_peak_bytes'] = 1
    elif mutation == 'input': report['inputs_sha256'] = {}
    elif mutation == 'time': report['three_time_outcomes']['second_test_edits']['added_lines'] = 0
    elif mutation == 'lifecycle': report['three_time_outcomes']['second_test_edits']['repeated_lifecycle_lines'] = 2
    elif mutation == 'cold': report['three_time_outcomes']['acquisition_state'] = 'cold'
    elif mutation == 'guard_probe': report['guard_probe'] = 'NOT_RUN'
    campaign.write(tmp_path / 'host.json', report); refresh_sums(tmp_path)
    if mutation == 'checksum': (tmp_path / 'first-test.txt').write_text('changed')
    elif mutation == 'missing_file': (tmp_path / 'cap1-parallel1/go.json').unlink()
    if mutation == 'none':
        assert campaign.validate_host(tmp_path, 'a' * 40, 'macos-15')['result'] == 'PASS'
    else:
        with pytest.raises((ValueError, FileNotFoundError)):
            campaign.validate_host(tmp_path, 'a' * 40, 'macos-15')


def test_guard_probe_rejects_a_source_started_before_stop():
    go = dict(result='STOP', stop_reason='FD headroom guard', cleanup_complete=True,
              peak_children=0, new_fixture_seconds=0, phases=[{'name': 'start'}], samples=[])
    with pytest.raises(ValueError, match='admitted'):
        campaign.validate_guard_probe(go)


def test_ci_runs_both_modes_and_requires_both_host_artifacts():
    text = (ROOT / '.github/workflows/live-host.yml').read_text()
    assert 'os: [macos-15, ubuntu-24.04]' in text
    assert 'scripts/go_fixture_campaign.py --expected-source-commit "$GITHUB_SHA" --output build/live-evidence/g1' in text
    assert 'name: go-fixture-host-${{ matrix.os }}-${{ github.sha }}' in text
    assert '--validate-matrix build/g1-matrix' in text
    assert 'pattern: go-fixture-host-*-${{ github.sha }}' in text
    required = text.split('  required:\n', 1)[1]
    assert '--validate-matrix build/g1-matrix' in required
    assert 'needs: [native-reference, live]' in required
    assert 'needs.scope' not in required


@pytest.mark.parametrize('present', ['macos-15', 'ubuntu-24.04'])
def test_missing_matrix_host_is_not_accepted(tmp_path, monkeypatch, present):
    directory = tmp_path / ('go-fixture-host-' + present + '-' + 'a' * 40)
    directory.mkdir()
    report = receipt(directory, monkeypatch)
    if present == 'ubuntu-24.04':
        report['host'] = dict(system='Linux', architecture='x86_64', version='24.04')
        campaign.write(directory / 'host.json', report); refresh_sums(directory)
    monkeypatch.setattr(sys, 'argv', ['go_fixture_campaign.py', '--expected-source-commit', 'a' * 40,
                                    '--validate-matrix', str(tmp_path)])
    with pytest.raises(FileNotFoundError):
        campaign.main()
