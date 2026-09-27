"""Paired interval calculations preserve joint samples and within-call scope."""
from pathlib import Path
import sys
import io
import json
import tarfile
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'benchmarks'))
from prepared_validation_reuse import aggregate, metrics
from prepared_validation_reuse import run


def report(public=100, host=120, restore=200):
    # Synthetic nanosecond timings, retaining independent guest/host clocks.
    h = {'begin': 0, 'metadata_snapshot_validated': host, 'spawn_begin': host,
         'guest_ready': host+restore+100, 'end': host+restore+100}
    c = {'begin': 0, 'database_returned': h['end']+public}
    g = {'restore_begin': 0, 'restore_complete': restore,
         'server_init_begin': restore, 'server_init_complete': restore+50,
         'ready_prepared': restore+50}
    trace = {'caller': [{'name': k, 'offset_ns': v} for k, v in c.items()],
             'host': {'events': [{'name': k, 'offset_ns': v} for k, v in h.items()],
                      'guest': {'events': [{'name': k, 'offset_ns': v} for k, v in g.items()]}}}
    row = {'case': 'fork_first_sql', 'phase': 'measurement', 'workers': 1,
           'latency_seconds': (h['end']+public)/1e9,
           'per_db': [{'latency_seconds': (h['end']+public)/1e9, 'stage_timings': trace}]}
    return {'samples': [row]}


def test_joint_preparation_and_residual():
    value = metrics(report())
    assert value[1, 'public outside host'] == [100/1e9]
    assert value[1, 'host validation'] == [120/1e9]
    assert value[1, 'combined preparation'] == [220/1e9]
    assert value[1, 'restore'] == [200/1e9]
    assert value[1, 'launch envelope residual'] == [50/1e9]


def test_paired_differences_not_difference_of_percentiles():
    pairs = [{'control': report(100, 120), 'reuse': report(40, 70)},
             {'control': report(80, 100), 'reuse': report(30, 60)}]
    with patch('prepared_validation_reuse.summarize_stages', return_value=[]), \
         patch('prepared_validation_reuse.init_summary', return_value=[]):
        summary = aggregate(pairs)
    result = next(x for x in summary['paired_control_minus_reuse'] if x['stage'] == 'combined preparation')
    assert result['raw_seconds'] == pytest.approx([110/1e9, 90/1e9])
    assert result['p50_seconds'] == pytest.approx(100/1e9)


def test_measurement_path_keeps_prepared_keys_and_omits_memory_diagnostics():
    text = (ROOT/'benchmarks/prepared_validation_reuse.py').read_text()
    assert "verify_branches(raw, 'existing-keys') != 14" in text
    assert 'MARIAMEM_AUTH_EXPERIMENT_CHECK' in text
    assert '--memory-diagnostics' not in text
    assert 'changed = patch(root)' in text
    assert 'before != hashes(bundle)' in text
    assert "('reuse', 'control')" in text


def test_orchestration_shares_native_keys_and_alternates_without_rebuild(tmp_path):
    native = tmp_path/'native'
    native.mkdir()
    (native/'provenance.json').write_text('{}')
    calls, builds, checks = [], [], []
    archive = io.BytesIO()
    with tarfile.open(fileobj=archive, mode='w'):
        pass

    def git(args, **kwargs):
        if args[1] == 'archive':
            return archive.getvalue()
        return '' if 'status' in args else 'a'*40

    def command(args, **kwargs):
        if args[:2] == ['go', 'test']:
            checks.append(kwargs['cwd'])
        if args[:2] == ['go', 'build']:
            builds.append(args)
            Path(args[args.index('-o')+1]).write_text('fake benchmark binary')
        if args[0] == 'openssl' and '-out' in args:
            Path(args[args.index('-out')+1]).write_text('public disposable test fixture')
        if '--json' in args:
            calls.append((args, kwargs['env']))
            value = report()
            value['completed'] = True
            Path(args[args.index('--json')+1]).write_text(json.dumps(value))

    empty = {'control': {'waterfall': []}, 'reuse': {'waterfall': []},
             'paired_control_minus_reuse': []}
    with patch('prepared_validation_reuse.subprocess.check_output', side_effect=git), \
         patch('prepared_validation_reuse.subprocess.run', side_effect=command), \
         patch('prepared_validation_reuse.patch', return_value={'source.go': 'b'*64}) as modified, \
         patch('prepared_validation_reuse.verify_branches', return_value=14) as verify, \
         patch('prepared_validation_reuse.tarfile.TarFile.extractall') as extract, \
         patch('prepared_validation_reuse.aggregate', return_value=empty), \
         patch('prepared_validation_reuse.platform.platform', return_value='test-platform'):
        run(native, tmp_path/'results', pairs=2, warmup=0)
    assert len(builds) == len(checks) == 2
    assert modified.call_count == 1
    assert extract.call_count == 2
    assert all(call.kwargs['filter'] == 'data' for call in extract.call_args_list)
    assert [Path(args[0]).name for args, _ in calls] == ['control-go', 'reuse-go', 'reuse-go', 'control-go']
    assert len({args[args.index('--native-dir')+1] for args, _ in calls}) == 1
    assert len({env['MARIAMEM_EXPERIMENT_AUTH_KEYS_DIR'] for _, env in calls}) == 1
    assert all(env['MARIAMEM_AUTH_EXPERIMENT_CHECK'] == '1' for _, env in calls)
    assert all('--memory-diagnostics' not in args for args, _ in calls)
    assert all(call.args[1] == 'existing-keys' for call in verify.call_args_list)
