"""Keep real Live browser/native coverage selected on maintained branches."""
from pathlib import Path
import re

import pytest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / '.github/workflows/live-host.yml'
DEPENDENCIES = [
    '.github/workflows/live-host.yml', 'live.go', 'go.mod', 'go.sum',
    'internal/live/endpoint.go', 'internal/control/live.go',
    'internal/host/server.go', 'internal/guest/guest.go',
    'internal/generatedgo/main.go', 'cmd/mariamem-host/main.go',
    'python/mariamem/live.py', 'python/setup.cfg', 'scripts/git_identity.py',
    'tests/live_acceptance/run.py', 'tests/e2e_native_control/goapp/main.go',
    'tests/dump_import_acceptance/linux_acquisition.py',
    'tests/test_live_ci_workflow.py', 'guest/source.patch',
    'release/generated-go-inputs.json',
]


def validate(text):
    for event in ['push', 'pull_request']:
        match = re.search(r'^  '+event+r':\n(.*?)(?=^  \S|^\S)', text, re.M | re.S)
        assert match, event
        block = match[1]
        branches = re.search(r'^    branches: \[([^]]+)\]$', block, re.M)
        assert branches and 'main' in [v.strip() for v in branches[1].split(',')]
        patterns = re.findall(r"^      - '([^']+)'$", block, re.M)
        expressions = [re.escape(p).replace(r'\*\*', 'DOUBLESTAR').replace(r'\*', '[^/]*').replace('DOUBLESTAR', '.*') for p in patterns]
        for path in DEPENDENCIES:
            assert any(re.fullmatch(p, path) for p in expressions), path
    assert 'pull_request_target:' not in text
    assert 'permissions:\n  contents: read' in text
    assert 'pull_request.head.sha' not in text and 'ref:' not in text
    assert 'os: [macos-15, ubuntu-24.04]' in text
    assert "python: ['3.11', '3.14']" in text
    assert '--expected-source-commit "$GITHUB_SHA"' in text
    assert 'needs: native-reference' in text
    assert 'python scripts/verify.py integration' in text
    assert 'go test -race ./internal/live ./internal/control .' in text
    for owner in ['native.py', 'run.py', 'installed.py']:
        assert 'tests/live_acceptance/'+owner in text
    for scenario in ['positive', 'skip-reset', 'restart-app']:
        assert scenario in text


def test_maintained_live_ci_contract():
    validate(WORKFLOW.read_text())


@pytest.mark.parametrize('before,after', [
    ('  pull_request:', '  retired_pull_request:'),
    ('branches: [main]', 'branches: [unused]'),
    ("      - 'internal/**'\n", ''),
    ("      - 'python/**'\n", ''),
    ("      - 'tests/**'\n", ''),
    ("      - 'scripts/**'\n", ''),
    ('needs: native-reference', 'needs: []'),
    ('--expected-source-commit "$GITHUB_SHA"', '--unbound'),
    ('go test -race ./internal/live ./internal/control .', 'go test ./internal/live'),
])
def test_live_ci_regressions_are_detected(before, after):
    text = WORKFLOW.read_text()
    assert before in text
    with pytest.raises(AssertionError):
        validate(text.replace(before, after))
