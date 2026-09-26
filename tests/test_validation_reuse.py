"""The experiment changes a copy only, with exact source anchors."""
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'benchmarks'))
from validation_reuse import patch


def test_disposable_validation_patch_keeps_integrity_checks(tmp_path):
    paths = ['internal/snapshot/snapshot.go', 'internal/artifacts/artifacts.go',
             'internal/host/server.go', 'mariamem.go']
    original = {name: (ROOT/name).read_bytes() for name in paths}
    for name in paths:
        path = tmp_path/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(original[name])
    hashes = patch(tmp_path)
    assert set(hashes) == set(paths)
    assert 'snapshot.Validate(restore, build)' in (tmp_path/'internal/host/server.go').read_text()
    assert 'hash != m.Hashes[name]' in (tmp_path/'internal/artifacts/artifacts.go').read_text()
    assert 'hash != m.Module' in (tmp_path/'internal/snapshot/snapshot.go').read_text()
    assert all((ROOT/name).read_bytes() == data for name, data in original.items())
    with pytest.raises(ValueError, match='anchor changed'):
        patch(tmp_path)
