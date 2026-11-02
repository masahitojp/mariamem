"""Keep the one-off candidate checks exact and separate from publication."""
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[1]


def validate(text):
    assert 'branches: [experiment/buffer-alignment-adoption]' in text
    assert 'contents: read' in text and 'contents: write' not in text
    assert 'build_generated_guest.py --repetitions 2' in text
    assert '--development' not in text
    assert 'test ! -e guest/experimental.patch' in text
    assert 'runner: [macos-15, ubuntu-24.04]' in text and 'needs: guest' in text
    assert "g['source_commit'] == os.environ['GITHUB_SHA']" in text
    assert "len(g['repetitions']) == 2" in text
    assert 'alignment-guest-${{ github.sha }}' in text
    assert 'python scripts/regenerate_release_guest.py' in text
    assert 'python tests/check_prepared_p1_binding.py' in text
    assert 'python tests/routine_thread_fixture.py --output build/alignment-ci/j1 --run' in text
    assert 'python scripts/verify.py integration' in text
    assert 'python scripts/audit_generated_licenses.py' in text
    assert 'check_prepared_build_guards.py --output build/alignment-ci/build-guards.json' in text
    assert 'release_generated_ci.py publish' not in text and 'operation: release' not in text
    assert 'go clean -testcache' in text


def test_candidate_workflow():
    validate((ROOT/'.github/workflows/buffer-alignment-candidate.yml').read_text())


@pytest.mark.parametrize('old,new', [
    ('--repetitions 2', '--repetitions 1'),
    ('test ! -e guest/experimental.patch', 'true'),
    ("g['source_commit'] == os.environ['GITHUB_SHA']", 'True'),
    ('alignment-guest-${{ github.sha }}', 'alignment-guest-latest'),
    ('runner: [macos-15, ubuntu-24.04]', 'runner: [ubuntu-24.04]'),
    ('python scripts/regenerate_release_guest.py', 'true'),
    ('python tests/routine_thread_fixture.py', 'true'),
    ('go clean -testcache', 'true'),
])
def test_weakened_gate_is_rejected(old,new):
    original=(ROOT/'.github/workflows/buffer-alignment-candidate.yml').read_text()
    assert old in original
    with pytest.raises(AssertionError):validate(original.replace(old,new))
