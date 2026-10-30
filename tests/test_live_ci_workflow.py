"""Full acceptance is explicit; daily protected checks cannot silently skip smoke."""
from pathlib import Path
import re
import sys
import pytest
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
WORKFLOW = ROOT/'.github/workflows/live-host.yml'
DEVELOPMENT = ROOT/'.github/workflows/check.yml'


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



def validate(text):
    triggers = text.split('concurrency:')[0]
    assert '  workflow_dispatch:' in triggers
    assert not re.search(r'^  (push|pull_request|pull_request_target|schedule|workflow_run):', triggers, re.M)
    assert 'needs: native-reference' in text
    assert 'needs: [native-reference, live]' in text
    assert 'name: Live full acceptance gate' in text
    assert 'name: Live required gate' not in text
    assert 'os: [macos-15, ubuntu-24.04]' in text
    assert "python: ['3.11', '3.14']" in text
    assert 'needs.scope' not in text
    for command in ['python scripts/verify.py check', 'python scripts/verify.py integration',
                    'go test -race -count=1 ./internal/live ./internal/control .',
                    'tests/live_acceptance/native.py', 'tests/live_acceptance/run.py',
                    'tests/live_acceptance/installed.py', 'docs/examples/live/verify.py',
                    'scripts/go_fixture_campaign.py', 'scripts/go_fixture_completion.py']:
        assert command in text
    for scenario in ['positive', 'skip-reset', 'restart-app']:
        assert scenario in text
    assert '--expected-source-commit "$GITHUB_SHA"' in text


def test_full_acceptance_is_explicit_and_retains_its_oracles():
    validate(WORKFLOW.read_text())
    validate_development_owners(DEVELOPMENT.read_text())


@pytest.mark.parametrize('before,after', [
    ('  workflow_dispatch:', '  pull_request:'),
    ('needs: native-reference', 'needs: []'),
    ('needs: [native-reference, live]', 'needs: []'),
    ('tests/live_acceptance/run.py', 'echo bypass'),
    ('scripts/go_fixture_campaign.py', 'echo bypass'),
    ('name: Live full acceptance gate', 'name: Live required gate'),
    ('--expected-source-commit "$GITHUB_SHA"', '--unbound'),
])
def test_full_acceptance_regressions_are_detected(before, after):
    with pytest.raises(AssertionError): validate(WORKFLOW.read_text().replace(before, after))


@pytest.mark.parametrize('job', ['native-reference', 'live'])
@pytest.mark.parametrize('result', ['success', 'failure', 'cancelled', 'skipped'])
def test_full_gate_rejects_missing_runtime_acceptance(job, result):
    from live_ci import verify_gate
    needs = {'native-reference': {'result': 'success'}, 'live': {'result': 'success'}}
    needs[job]['result'] = result
    if result == 'success': verify_gate(needs)
    else:
        with pytest.raises(AssertionError): verify_gate(needs)


@pytest.mark.parametrize('selected', ['true', 'false'])
@pytest.mark.parametrize('job', ['scope', 'check', 'integration'])
@pytest.mark.parametrize('result', ['success', 'failure', 'cancelled', 'skipped'])
def test_daily_gate_requires_all_selected_checks(selected, job, result):
    from development_scope import verify_gate
    needs = {'scope': {'result': 'success', 'outputs': {'integration': selected}},
             'check': {'result': 'success'},
             'integration': {'result': 'success' if selected == 'true' else 'skipped'}}
    expected = needs[job]['result']; needs[job]['result'] = result
    if result == expected: verify_gate(needs)
    else:
        with pytest.raises(AssertionError): verify_gate(needs)


def test_daily_gate_owns_the_existing_protected_context():
    text = DEVELOPMENT.read_text()
    assert 'name: Live required gate' in text
    assert 'needs: [scope, check, integration]' in text
    assert 'from development_scope import verify_gate' in text
    assert 'if: always()' in text.split('  required:')[1]
