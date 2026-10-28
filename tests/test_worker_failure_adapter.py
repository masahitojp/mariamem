"""Fail-closed installation of the worker failure runtime-helper boundary."""
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from runtime_failure import apply


def test_worker_failure_adapter_matches_installed_helpers():
    raw = (ROOT / 'tests/fixtures/pinned-worker-failure.go.txt').read_text()
    current = (ROOT / 'internal/generatedgo/code/base/base.go').read_text()
    fragments = []
    for start, end in [('func AtomicWait(m ', '// threadLaunch allocates'),
                       ('func ThreadLaunch(m ', '// threadSpawn implements'),
                       ('type ThreadPool struct {', '// WaitThreads joins')]:
        begin = current.index(start)
        fragments.append(current[begin:current.index(end, begin)])
    assert ''.join(apply('code/base/base.go', raw).split()) == ''.join(''.join(fragments).split())


@pytest.mark.parametrize('anchor', ['trap   any', 'm.Threads.trap = r',
                                  '<-ch', 'case <-timer.C:', 'body(child, tid)'])
def test_changed_worker_failure_preimage_is_rejected(anchor):
    raw = (ROOT / 'tests/fixtures/pinned-worker-failure.go.txt').read_text()
    assert anchor in raw
    with pytest.raises(ValueError, match='preimage changed'):
        apply('code/base/base.go', raw.replace(anchor, 'changed-preimage', 1))
