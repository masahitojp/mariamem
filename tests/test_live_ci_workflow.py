"""Keep real Live browser/native coverage selected on maintained branches."""
from pathlib import Path
import re
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / '.github/workflows/live-host.yml'
sys.path.insert(0, str(ROOT/'scripts'))
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
        assert 'paths:' not in block and 'paths-ignore:' not in block
    assert 'pull_request_target:' not in text
    assert 'permissions:\n  contents: read' in text
    assert 'pull_request.head.sha' not in text and 'ref:' not in text
    assert 'os: [macos-15, ubuntu-24.04]' in text
    assert "python: ['3.11', '3.14']" in text
    assert '--expected-source-commit "$GITHUB_SHA"' in text
    assert 'needs: [scope, native-reference]' in text
    assert 'name: Live required gate' in text
    assert 'if: always()' in text
    assert 'needs: [scope, native-reference, live]' in text
    assert 'python scripts/live_ci.py gate' in text
    assert 'python scripts/live_ci.py scope' in text
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
    ('needs: [scope, native-reference]', 'needs: []'),
    ('    branches: [main]','    branches: [main]\n    paths: [docs/**]'),
    ('name: Live required gate','name: optional'),
    ('if: always()', "if: success()"),
    ('needs: [scope, native-reference, live]', 'needs: [scope]'),
    ('--expected-source-commit "$GITHUB_SHA"', '--unbound'),
    ('go test -race ./internal/live ./internal/control .', 'go test ./internal/live'),
])
def test_live_ci_regressions_are_detected(before, after):
    text = WORKFLOW.read_text()
    assert before in text
    with pytest.raises(AssertionError):
        validate(text.replace(before, after))


def test_dependency_selector_covers_all_prior_paths():
    import sys
    sys.path.insert(0, str(ROOT/'scripts'))
    from live_ci import required
    for path in DEPENDENCIES:
        assert required([path], 'local changed-input classification'), path


@pytest.mark.parametrize('paths,reason,expected', [
    (['README.md', 'docs/development.md'], 'local changed-input classification', False),
    (['docs/decisions/prepared-consumer-exceptions.md'], 'local changed-input classification', True),
    (['unknown.input'], 'local changed-input classification', True),
    ([], 'local changed-input classification', True),
    (['README.md'], 'event base unavailable; full verification', True),
])
def test_selector_fails_closed(paths, reason, expected):
    from live_ci import required
    assert required(paths, reason) is expected


@pytest.mark.parametrize('selected', ['true', 'false'])
@pytest.mark.parametrize('job', ['scope', 'native-reference', 'live'])
@pytest.mark.parametrize('result', ['failure', 'cancelled', 'skipped', 'success'])
def test_aggregate_rejects_incomplete_or_unselected_jobs(selected, job, result):
    from live_ci import verify_gate
    needs = {'scope': {'result': 'success', 'outputs': {'run_live': selected}},
             'native-reference': {'result': 'success' if selected == 'true' else 'skipped'},
             'live': {'result': 'success' if selected == 'true' else 'skipped'}}
    needs[job]['result'] = result
    expected = 'success' if job == 'scope' or selected == 'true' else 'skipped'
    if result == expected:
        verify_gate(needs)
    else:
        with pytest.raises(AssertionError):
            verify_gate(needs)


def test_aggregate_rejects_missing_or_undefined_scope():
    from live_ci import verify_gate
    for needs in [{}, {'scope': {'result': 'success', 'outputs': {}},
                       'native-reference': {'result': 'skipped'}, 'live': {'result': 'skipped'}}]:
        with pytest.raises(AssertionError):
            verify_gate(needs)
