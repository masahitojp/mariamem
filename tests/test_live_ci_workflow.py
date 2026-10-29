"""Keep real Live browser/native coverage selected on maintained branches."""
from pathlib import Path
import re
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / '.github/workflows/live-host.yml'
DEVELOPMENT = ROOT / '.github/workflows/check.yml'
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
    assert 'go test -race -count=1 ./internal/live ./internal/control .' in text
    validate_canonical_ownership(text, DEVELOPMENT.read_text())
    for owner in ['native.py', 'run.py', 'installed.py']:
        assert 'tests/live_acceptance/'+owner in text
    for scenario in ['positive', 'skip-reset', 'restart-app']:
        assert scenario in text


def validate_development_owners(development):
    def job(name):
        match = re.search(r'^  ' + name + r':\n(.*?)(?=^  \S|\Z)', development, re.M | re.S)
        assert match, name
        return match[1]
    # Delegation is valid only while the other required workflow owns these OSes,
    # commands and scope predicates. No source override or trigger path filtering.
    assert 'continue-on-error:' not in development
    assert 'needs: scope' in job('check') and 'needs: scope' in job('integration')
    assert not re.search(r'^    if:', job('check'), re.M)
    assert 'runs-on: ubuntu-latest' in job('check')
    assert "python scripts/verify.py check --scope '${{ needs.scope.outputs.check_scope }}'" in job('check')
    assert 'runs-on: ubuntu-24.04' in job('integration')
    assert "if: needs.scope.outputs.integration == 'true'" in job('integration')
    assert 'python scripts/verify.py integration' in job('integration')
    triggers = development.split('permissions:')[0]
    assert 'pull_request:\n    branches: [main]' in triggers
    assert 'push:\n    branches: [main]' in triggers
    assert 'paths:' not in triggers and 'paths-ignore:' not in triggers
    assert 'ref:' not in development and 'pull_request.head.sha' not in development
    assert 'python scripts/development_scope.py' in job('scope')


def validate_canonical_ownership(text, development):
    validate_development_owners(development)
    for name, condition, command in [
        ('Canonical check', "(runner.os == 'macOS' && github.event_name != 'pull_request') || (runner.os == 'Linux' && needs.scope.outputs.ubuntu_check != 'false')", 'check'),
        ('Canonical integration', "(runner.os == 'macOS' && needs.scope.outputs.mac_integration == 'true') || (runner.os == 'Linux' && needs.scope.outputs.ubuntu_integration != 'false')", 'integration'),
    ]:
        assert (f'- name: {name}\n        if: {condition}\n'
                f'        run: python scripts/verify.py {command} >') in text
    for output in ['ubuntu_check', 'ubuntu_integration']:
        assert output + ': ${{ steps.scope.outputs.' + output + ' }}' in text
    assert text.count('cache: true') == 2 and 'cache: false' not in text
    assert text.count('          go clean -testcache') == 2
    assert text.count('cache-dependency-path: |\n            go.sum\n            .github/workflows/live-host.yml') == 2
    # The native build must not seed the host's much larger cache namespace.
    assert '            tests/live_acceptance/native.py' in text


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
    ('go test -race -count=1 ./internal/live ./internal/control .', 'go test ./internal/live'),
    ("(runner.os == 'macOS' && github.event_name != 'pull_request') || (runner.os == 'Linux' && needs.scope.outputs.ubuntu_check != 'false')", "runner.os == 'macOS'"),
    ("(runner.os == 'macOS' && needs.scope.outputs.mac_integration == 'true') || (runner.os == 'Linux' && needs.scope.outputs.ubuntu_integration != 'false')", "runner.os == 'Linux'"),
    ('cache: true', 'cache: false'),
    ('go clean -testcache', 'echo reuse-test-results'),
])
def test_live_ci_regressions_are_detected(before, after):
    text = WORKFLOW.read_text()
    assert before in text
    with pytest.raises(AssertionError):
        validate(text.replace(before, after))


@pytest.mark.parametrize('before,after', [
    ('runs-on: ubuntu-latest', 'runs-on: macos-15'),
    ('runs-on: ubuntu-24.04', 'runs-on: macos-15'),
    ('python scripts/verify.py integration', 'echo omitted-integration'),
    ("check --scope '${{ needs.scope.outputs.check_scope }}'", 'check --scope docs'),
    ('    branches: [main]', '    branches: [main]\n    paths: [docs/**]'),
])
def test_delegated_coverage_cannot_silently_move(before, after):
    text = DEVELOPMENT.read_text()
    assert before in text
    with pytest.raises(AssertionError):
        validate_canonical_ownership(WORKFLOW.read_text(), text.replace(before, after))


@pytest.mark.parametrize('event,ref,scope,integration,expected', [
    ('pull_request', 'refs/pull/3/merge', 'full', True, (False, False)),
    ('push', 'refs/heads/main', 'full', True, (False, False)),
    ('pull_request', 'refs/pull/3/merge', 'docs', False, (True, True)),
    ('pull_request', 'refs/pull/3/merge', 'python', False, (True, True)),
    ('workflow_dispatch', 'refs/heads/main', 'full', True, (True, True)),
    ('push', 'refs/heads/experiment/live-main-candidate', 'full', True, (True, True)),
    ('unknown', None, 'full', True, (True, True)),
    ('pull_request', 'refs/pull/3/merge', None, None, (True, True)),
])
def test_canonical_delegation_preserves_each_host(event, ref, scope, integration, expected):
    from live_ci import canonical_plan
    from development_scope import select
    inputs = {'full': ['live.go'], 'python': ['scripts/check_public.py'], 'docs': ['docs/python.md']}
    plan = select(inputs[scope]) if scope else {}
    if scope:
        assert plan['check_scope'] == scope and plan['integration'] is integration
    result = canonical_plan(plan, event, ref)
    assert (result['ubuntu_check'], result['ubuntu_integration']) == expected
    # Both macOS canonical invocations remain selected by these workflow conditions.


def test_uncertain_development_scope_keeps_local_canonical():
    from live_ci import canonical_plan
    result = canonical_plan(dict(check_scope='full', integration=True,
                                 reason='event diff unavailable; full verification'),
                            'pull_request', 'refs/pull/3/merge')
    assert result == dict(ubuntu_check=True, ubuntu_integration=True)


@pytest.mark.parametrize('event,expected', [('pull_request', 'false'), ('workflow_dispatch', 'true')])
def test_scope_exports_canonical_decisions(monkeypatch, tmp_path, event, expected):
    import live_ci
    from development_scope import select
    event_path = tmp_path / 'event.json'
    event_path.write_text('{}')
    output = tmp_path / 'output'
    monkeypatch.setenv('GITHUB_EVENT_PATH', str(event_path))
    monkeypatch.setenv('GITHUB_EVENT_NAME', event)
    monkeypatch.setenv('GITHUB_REF', 'refs/heads/main')
    monkeypatch.setenv('GITHUB_OUTPUT', str(output))
    monkeypatch.setattr(live_ci, 'plan', lambda *args: select(['live.go']))
    monkeypatch.setattr(sys, 'argv', ['live_ci.py', 'scope', '--candidate-sha', 'a' * 40, '--github-output'])
    live_ci.main()
    assert output.read_text().splitlines()[:3] == [
        'run_live=true', 'ubuntu_check=' + expected, 'ubuntu_integration=' + expected]


def test_dependency_selector_covers_all_prior_paths():
    import sys
    sys.path.insert(0, str(ROOT/'scripts'))
    from live_ci import required
    for path in DEPENDENCIES:
        assert required([path], 'local changed-input classification'), path


@pytest.mark.parametrize('paths,reason,expected', [
    (['README.md', 'docs/development.md'], 'local changed-input classification', False),
    (['docs/project-status.md'], 'local changed-input classification', False),
    (['docs/reviews/issue5-text-dedup.md'], 'local changed-input classification', False),
    (['docs/benchmarks/go126-vs-go127-evidence/statistics.csv'], 'local changed-input classification', False),
    (['docs/decisions/prepared-consumer-exceptions.md'], 'local changed-input classification', False),
    (['docs/benchmarks/go126-vs-go127-evidence/runtime.go'], 'local changed-input classification', True),
    (['docs/new-evidence.json'], 'local changed-input classification', True),
    (['docs/project-status.md', 'live.go'], 'local changed-input classification', True),
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
    needs = {'scope': {'result': 'success', 'outputs': {'run_live': selected, **dict.fromkeys(__import__('live_selection').FAMILIES, 'true')}},
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

@pytest.mark.parametrize('event', ['pull_request', 'push', 'workflow_dispatch'])
@pytest.mark.parametrize('os_name', ['macOS', 'Linux'])
@pytest.mark.parametrize('ubuntu_check', ['true', 'false'])
def test_canonical_check_event_platform_ownership(event, os_name, ubuntu_check):
    import re
    expression = re.search(r'- name: Canonical check\n        if: (.*)', WORKFLOW.read_text())[1]
    expression = (expression.replace('runner.os', repr(os_name))
                  .replace('github.event_name', repr(event))
                  .replace('needs.scope.outputs.ubuntu_check', repr(ubuntu_check))
                  .replace('&&', 'and').replace('||', 'or'))
    actual = bool(eval(expression, {'__builtins__': {}}, {}))
    expected = event != 'pull_request' if os_name == 'macOS' else ubuntu_check != 'false'
    assert actual == expected
