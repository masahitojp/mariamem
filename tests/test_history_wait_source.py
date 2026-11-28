"""Missing ownership/slowpath guards must not silently enter a rebuilt guest."""
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
import check_history_wait_source as guard


def test_canonical_history_wait_source():
    assert guard.source()['history_delta_sha256'] == guard.DELTA_SHA256


def test_preparation_preserves_separate_experimental_overlay(tmp_path):
    target = tmp_path/'guest'
    target.mkdir()
    (target/'source.patch').write_bytes((ROOT/'guest/source.patch').read_bytes())
    (target/'experimental.patch').write_text('separately tracked experiment')
    with pytest.raises(ValueError, match='must be canonical'):
        guard.source(tmp_path)
    assert guard.source(tmp_path, allow_experimental=True)['history_delta_sha256'] == guard.DELTA_SHA256


@pytest.mark.parametrize('old,new', [
    (b'!rseg.latch.rd_lock_try()', b'true'),
    (b'tpool::scoped_wait waiting;', b'/* no notification */'),
    (b'is_long_task()', b'is_executing_task()'),
    (b'is_waiting()', b'is_long_task()'),
    (b'm_waiting_task_count--;', b'/* leaked ownership */'),
    (b'if (m_pool) m_pool->wait_end();', b'/* missing end */'),
])
def test_history_wait_mutations_rejected(tmp_path, old, new):
    patch = (ROOT/'guest/source.patch').read_bytes()
    assert patch.count(old) >= 1
    target = tmp_path/'guest/source.patch'
    target.parent.mkdir()
    target.write_bytes(patch.replace(old, new, 1))
    with pytest.raises(ValueError, match='source changed'):
        guard.source(tmp_path)
