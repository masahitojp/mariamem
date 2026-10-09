"""Current public-asset trust boundary, without the retired native import island."""
import hashlib
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from published_assets import verify_downloads


@pytest.fixture
def assets(tmp_path):
    (tmp_path / 'wheel.whl').write_bytes(b'accepted wheel')
    digest = hashlib.sha256(b'accepted wheel').hexdigest()
    sums = f'{digest}  wheel.whl\n'
    (tmp_path / 'SHA256SUMS').write_text(sums)
    return tmp_path, {'wheel.whl': digest, 'SHA256SUMS': hashlib.sha256(sums.encode()).hexdigest()}


def test_exact_published_bytes(assets):
    root, record = assets
    assert verify_downloads(root, record) == record


@pytest.mark.parametrize('change', ['extra', 'missing', 'corrupted', 'wrong-manifest', 'duplicate-manifest'])
def test_changed_or_ambiguous_public_bytes_fail_closed(assets, change):
    root, record = assets
    if change == 'extra':
        (root / 'unexpected').write_bytes(b'x')
    elif change == 'missing':
        (root / 'wheel.whl').unlink()
    elif change == 'corrupted':
        (root / 'wheel.whl').write_bytes(b'changed')
    else:
        sums = root / 'SHA256SUMS'
        sums.write_text('0' * 64 + '  wheel.whl\n' if change == 'wrong-manifest' else sums.read_text() * 2)
        record['SHA256SUMS'] = hashlib.sha256(sums.read_bytes()).hexdigest()
    with pytest.raises(ValueError):
        verify_downloads(root, record)


def test_current_smoke_uses_live_shared_helper():
    path = Path(__file__).resolve().parents[1] / 'scripts/release_generated_ci.py'
    assert 'from published_assets import verify_downloads' in path.read_text()
    assert 'from ci_release_public_smoke import' not in path.read_text()
