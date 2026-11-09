"""Candidate gate keeps both page-size platforms, source binding and runtime checks."""
from pathlib import Path


def test_static_image_candidate_boundaries():
    root = Path(__file__).resolve().parents[1]
    text = (root/'.github/workflows/issue123-layout.yml').read_text()
    for contract in (
        'runner: [macos-15, ubuntu-24.04]', 'go-version: \'1.26.10\'',
        'scripts/git_identity.py inspect HEAD', 'os.environ["GITHUB_SHA"]',
        'test -z "$(git status --porcelain)"', 'go clean -testcache',
        './internal/generatedgo/layoutgen -check',
        'scripts/verify_generated_runtime.py', 'tests/test_runtime_static_image.py',
        './internal/generatedgo/image', 'scripts/verify.py integration',
        'if-no-files-found: error', 'SHA256SUMS.json',
    ):
        assert contract in text
    assert 'operation: release' not in text and 'continue-on-error' not in text
    assert '  workflow_dispatch:' in text and '  push:' not in text and '  pull_request:' not in text
