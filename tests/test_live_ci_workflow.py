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
    assert 'continue-on-error:' not in development
    assert not re.search(r'^    if:', job('check'), re.M)
    assert 'runs-on: ubuntu-24.04' in job('check')
    assert "python scripts/verify.py check --scope '${{ steps.diff.outputs.check_scope }}'" in job('check')
    assert "if: steps.diff.outputs.integration == 'true'" in job('check')
    assert 'python scripts/verify.py smoke' in job('check')
    assert 'needs: check' in job('integration')
    assert "if: always() && needs.check.outputs.integration == 'true'" in job('integration')
    triggers = development.split('permissions:')[0]
    assert 'pull_request:\n    branches: [main]' in triggers
    assert '  push:' not in triggers
    assert 'paths:' not in triggers and 'paths-ignore:' not in triggers
    assert 'ref:' not in development and 'pull_request.head.sha' not in development
    assert 'python scripts/development_scope.py' in job('check')
    assert development.count('uses: actions/checkout@') == 1
    assert development.count('uses: actions/setup-go@') == 1
    for name in ['integration', 'required']:
        assert 'uses:' not in job(name)



def validate(text):
    triggers = text.split('permissions:')[0]
    assert '  workflow_call:' in triggers
    assert not re.search(r'^  (push|pull_request|pull_request_target|schedule|workflow_run):', triggers, re.M)
    assert 'needs: native-reference' in text
    assert 'needs: [native-reference, live]' in text
    assert 'name: Live full acceptance gate' in text
    assert 'name: Live required gate' not in text
    assert 'os: [macos-15, ubuntu-24.04]' in text
    assert "python: ['3.11', '3.14']" in text
    assert 'needs.scope' not in text
    for command in [
                    'tests/live_acceptance/native.py', 'tests/live_acceptance/run.py',
                    'tests/live_acceptance/installed.py', 'docs/examples/live/verify.py',
                    'scripts/go_fixture_campaign.py', 'scripts/go_fixture_completion.py']:
        assert command in text
    for scenario in ['positive', 'skip-reset', 'restart-app']:
        assert scenario in text
    assert '--expected-source-commit "$SOURCE_COMMIT"' in text


def test_full_acceptance_is_explicit_and_retains_its_oracles():
    validate(WORKFLOW.read_text())
    validate_development_owners(DEVELOPMENT.read_text())


@pytest.mark.parametrize('before,after', [
    ('  workflow_call:', '  pull_request:'),
    ('needs: native-reference', 'needs: []'),
    ('needs: [native-reference, live]', 'needs: []'),
    ('tests/live_acceptance/run.py', 'echo bypass'),
    ('scripts/go_fixture_campaign.py', 'echo bypass'),
    ('name: Live full acceptance gate', 'name: Live required gate'),
    ('--expected-source-commit "$SOURCE_COMMIT"', '--unbound'),
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


def gate_script(name):
    """Exercise the actual checkout-free gate, rather than a second implementation."""
    import textwrap
    text = DEVELOPMENT.read_text()
    block = re.search(r'^  '+name+r':\n(.*?)(?=^  \S|\Z)', text, re.M | re.S)[1]
    return textwrap.dedent(block.split('        run: |\n', 1)[1])


def run_gate(name, **env):
    import json
    import os
    import subprocess
    values = {k: json.dumps(v) if isinstance(v, dict) else v for k, v in env.items()}
    return subprocess.run(['bash', '-e', '-c', gate_script(name)],
                          env=dict(os.environ, **values), capture_output=True).returncode


@pytest.mark.parametrize('selected', ['true', 'false'])
@pytest.mark.parametrize('job', ['check', 'integration'])
@pytest.mark.parametrize('result', ['success', 'failure', 'cancelled', 'skipped'])
def test_daily_gate_requires_all_selected_checks(selected, job, result):
    expected = 'success' if selected == 'true' else 'skipped'
    needs = {'check': {'result': 'success', 'outputs': {'integration': selected, 'smoke_result': expected}},
             'integration': {'result': expected}}
    original = needs[job]['result']; needs[job]['result'] = result
    assert (run_gate('required', NEEDS_JSON=needs) == 0) == (result == original)


@pytest.mark.parametrize('selected', ['true', 'false', '', 'invalid'])
@pytest.mark.parametrize('smoke', ['success', 'failure', 'cancelled', 'skipped', ''])
def test_selected_smoke_cannot_be_omitted_or_substituted(selected, smoke):
    expected = 'success' if selected == 'true' else 'skipped'
    needs = {'check': {'result': 'success', 'outputs': {'integration': selected, 'smoke_result': smoke}},
             'integration': {'result': expected}}
    valid = selected in ('true', 'false') and smoke == expected
    assert (run_gate('required', NEEDS_JSON=needs) == 0) == valid


@pytest.mark.parametrize('check', ['success', 'failure', 'cancelled', 'skipped', ''])
@pytest.mark.parametrize('smoke', ['success', 'failure', 'cancelled', 'skipped', ''])
def test_integration_context_requires_successful_execution(check, smoke):
    assert (run_gate('integration', CHECK_RESULT=check, SMOKE_RESULT=smoke) == 0) == (check == smoke == 'success')


@pytest.mark.parametrize('missing', ['check', 'integration', 'outputs', 'selection', 'smoke'])
def test_missing_gate_evidence_fails(missing):
    needs = {'check': {'result': 'success', 'outputs': {'integration': 'true', 'smoke_result': 'success'}},
             'integration': {'result': 'success'}}
    if missing in ('check', 'integration'): del needs[missing]
    elif missing == 'outputs': del needs['check']['outputs']
    else: del needs['check']['outputs']['integration' if missing == 'selection' else 'smoke_result']
    assert run_gate('required', NEEDS_JSON=needs) != 0


def test_daily_gate_owns_the_existing_protected_context():
    text = DEVELOPMENT.read_text()
    assert 'name: Live required gate' in text
    assert 'needs: [check, integration]' in text
    assert 'smoke_result: ${{ steps.smoke.outcome }}' in text
    assert 'if: always()' in text.split('  required:')[1]
