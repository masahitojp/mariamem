"""Reject mismatched provenance and misleading SQL comparison receipts."""
import copy
import json
import importlib.util
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('timer_ubuntu', ROOT / 'tests/timer_runtime/ubuntu.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def artifact():
    return dict(id=module.ARTIFACT, expired=False, digest='sha256:' + module.ARCHIVE,
                workflow_run=dict(id=module.RUN, head_sha=module.GUEST_SOURCE))


def test_exact_artifact():
    module.check_artifact(artifact(), module.ARCHIVE)


@pytest.mark.parametrize('field,value', [('id', 1), ('expired', True), ('digest', 'sha256:' + '0'*64)])
def test_bad_artifact(field, value):
    meta = artifact()
    meta[field] = value
    with pytest.raises(ValueError):
        module.check_artifact(meta, module.ARCHIVE)


@pytest.mark.parametrize('field,value', [('id', 1), ('head_sha', '0'*40)])
def test_wrong_artifact_origin(field, value):
    meta = artifact()
    meta['workflow_run'][field] = value
    with pytest.raises(ValueError):
        module.check_artifact(meta, module.ARCHIVE)


def test_bad_archive_bytes():
    with pytest.raises(ValueError):
        module.check_artifact(artifact(), '0'*64)


def sql_record():
    return dict(result='PASS', observations=[
        dict(phase=phase, pair=pair, delayed=delayed, sql='same SQL', wall_ms=25,
             subsequent_select='PASS', report=dict(query_block=dict(r_total_time_ms=24,
                 nested_loop=[dict(table=dict(r_rows=2, r_loops=1))])))
        for phase in ('fresh', 'child1', 'child2') for pair in range(3) for delayed in (False, True)])


def test_native_timing_need_not_equal_guest():
    native, guest = sql_record(), sql_record()
    for row in native['observations']:
        row['report']['query_block']['r_total_time_ms'] = 21
    assert module.semantic_rows(native) == module.semantic_rows(guest)


@pytest.mark.parametrize('mutation', ['zero', 'too_long', 'rows', 'missing', 'phase', 'select'])
def test_sql_oracle_rejects_bad_receipts(mutation):
    record = copy.deepcopy(sql_record())
    row = record['observations'][1]
    if mutation == 'zero':
        row['report']['query_block']['r_total_time_ms'] = 0
    elif mutation == 'too_long':
        row['report']['query_block']['r_total_time_ms'] = 100
    elif mutation == 'rows':
        row['report']['query_block']['nested_loop'][0]['table']['r_rows'] = 1
    elif mutation == 'missing':
        record['observations'].pop()
    elif mutation == 'phase':
        row['phase'] = 'wrong'
    else:
        row['subsequent_select'] = 'FAIL'
    with pytest.raises(ValueError):
        module.semantic_rows(record)


@pytest.mark.parametrize('bad', [False, True])
def test_pipe_timings_are_checked(bad):
    rows = sql_record()['observations'][:6]
    record = dict(subsequent_select='PASS', active_mappings_after=0, rows=[
        dict(repeat=r['pair'], delay=r['delayed'], wall_ms=r['wall_ms'],
             raw=json.dumps(r['report'])) for r in rows])
    if bad:
        value = json.loads(record['rows'][1]['raw'])
        value['query_block']['r_total_time_ms'] = 0
        record['rows'][1]['raw'] = json.dumps(value)
        with pytest.raises(ValueError):
            module.check_pipe(record)
    else:
        module.check_pipe(record)
