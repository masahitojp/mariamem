"""Routing campaign has one release owner, not a second daily integration."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_routing_release_keeps_compatibility_and_both_platforms():
    text = (ROOT/'.github/workflows/connection-routing.yml').read_text()
    assert '  workflow_call:' in text
    assert '  push:' not in text and '  pull_request:' not in text
    release = (ROOT/'.github/workflows/release-candidate-ready.yml').read_text()
    assert 'tests/test_routing.py tests/test_routing_pytest.py tests/test_routing_receipts.py' in release
    assert 'needs: [resolve, runtime, units]' in release
    assert '  compatibility:' not in text
    assert 'os: [macos-15, ubuntu-24.04]' in text
    assert 'tests/routing_acceptance/run.py' in text
    assert 'ref: ${{ inputs.source_commit }}' in text
    assert '--source-commit "$SOURCE_COMMIT"' in text
    assert 'scripts/verify.py' not in text
    assert 'tests/routing_acceptance/run.py' not in (ROOT/'scripts/verify.py').read_text()
