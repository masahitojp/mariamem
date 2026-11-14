"""Full acceptance is explicit; daily protected checks cannot silently skip smoke."""
from pathlib import Path
from workflow_model import parse, needs, steps, commands, step_named
import sys
import pytest
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
WORKFLOW = ROOT/'.github/workflows/live-host.yml'
DEVELOPMENT = ROOT/'.github/workflows/check.yml'


def validate_development_owners(development):
    model = parse(development)
    jobs = model['jobs']
    assert 'continue-on-error' not in model
    assert all('continue-on-error' not in owner for owner in [*jobs.values(), *steps(model)])
    check = jobs['check']
    assert 'if' not in check
    assert check['runs-on'] == 'ubuntu-24.04'
    script = '\n'.join(step.get('run', '') for step in check['steps'])
    assert "python scripts/verify.py check --scope '${{ steps.diff.outputs.check_scope }}'" in script
    assert any(step.get('if') == "steps.diff.outputs.integration == 'true'" and 'python scripts/verify.py smoke' in step.get('run', '') for step in check['steps'])
    assert needs(jobs['integration']) == {'check'}
    assert jobs['integration']['if'] == "always() && needs.check.outputs.integration == 'true'"
    assert 'python scripts/development_scope.py' in script
    for name in ['integration', 'required']:
        assert 'uses' not in jobs[name]


def validate(text):
    model = parse(text)
    jobs = model['jobs']
    assert needs(jobs['live']) == {'native-reference'}
    gates = [job for job in jobs.values() if job.get('name') == 'Live full acceptance gate']
    assert len(gates) == 1 and needs(gates[0]) == {'native-reference', 'live'}
    assert all(job.get('name') != 'Live required gate' for job in jobs.values())
    matrix = jobs['live']['strategy']['matrix']
    assert matrix['os'] == ['macos-15', 'ubuntu-24.04']
    assert jobs['native-reference']['strategy']['matrix']['python'] == ['3.11', '3.14']
    assert 'needs.scope' not in str(model)
    script = commands(model)
    for command in ['tests/live_acceptance/native.py', 'tests/live_acceptance/run.py',
                    'tests/live_acceptance/installed.py', 'docs/examples/live/verify.py',
                    'tests/test_forklimit_unit.py', 'tests/test_forklimit_entries.py',
                    'tests/test_forklimit_transport.py', 'tests/test_handoff_failures.py',
                    'tests/test_owned_snapshot.py', 'scripts/go_fixture_campaign.py',
                    'scripts/go_fixture_completion.py']:
        assert command in script, command
    assert 'docs/examples/live/verify.py --host build/mariamem-host --go-app build/go-live-orders' in script
    assert 'scripts/e2e_workflow_timing.py' not in script
    assert '--output build/live-evidence/g1 --profile release' in script
    assert '--validate-matrix build/g1-matrix --profile release' in script
    for scenario in ['positive', 'skip-reset', 'restart-app']:
        assert scenario in script
    installed = step_named(model, 'Installed wheel and external Go module')['run']
    assert 'for py in "$PY311" "$PY314"' in installed
    assert 'build/live-evidence/installed-py$version' in installed


def test_full_acceptance_is_explicit_and_retains_its_oracles():
    validate(WORKFLOW.read_text())
    validate_development_owners(DEVELOPMENT.read_text())


@pytest.mark.parametrize('before,after', [
    ('needs: native-reference', 'needs: []'),
    ('needs: [native-reference, live]', 'needs: []'),
    ('tests/live_acceptance/run.py', 'echo bypass'),
    ('scripts/go_fixture_campaign.py', 'echo bypass'),
    ('--profile release', '--profile measurement'),
    ('tests/test_forklimit_transport.py', 'echo omitted-transport'),
    ('tests/test_owned_snapshot.py', 'echo omitted-runtime'),
    ('build/live-evidence/installed-py$version', 'build/live-evidence/unbound'),
    ('name: Live full acceptance gate', 'name: Live required gate'),
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
    job = parse(DEVELOPMENT.read_text())['jobs'][name]
    scripts = [step['run'] for step in job['steps'] if 'run' in step]
    assert len(scripts) == 1
    return scripts[0]


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
    needs = {'check': {'result': 'success', 'outputs': {'integration': selected, 'smoke_result': expected, 'linux_wheel': selected}},
             'integration': {'result': expected}, 'linux': {'result': expected}}
    original = needs[job]['result']; needs[job]['result'] = result
    assert (run_gate('required', NEEDS_JSON=needs) == 0) == (result == original)


@pytest.mark.parametrize('selected', ['true', 'false'])
@pytest.mark.parametrize('smoke', ['success', 'failure', 'cancelled', 'skipped', ''])
def test_selected_smoke_cannot_be_omitted_or_substituted(selected, smoke):
    expected = 'success' if selected == 'true' else 'skipped'
    needs = {'check': {'result': 'success', 'outputs': {'integration': selected, 'smoke_result': smoke, 'linux_wheel': selected}},
             'integration': {'result': expected}, 'linux': {'result': expected}}
    valid = selected in ('true', 'false') and smoke == expected
    assert (run_gate('required', NEEDS_JSON=needs) == 0) == valid


@pytest.mark.parametrize('check,smoke', [('success', 'success'),
    *[(bad, 'success') for bad in ('failure', 'cancelled', 'skipped', '')],
    *[('success', bad) for bad in ('failure', 'cancelled', 'skipped', '')]])
def test_integration_context_requires_successful_execution(check, smoke):
    # Each independent input must reject failures; their Cartesian product
    # repeats the same early rejection and adds no new branch coverage.
    assert (run_gate('integration', CHECK_RESULT=check, SMOKE_RESULT=smoke) == 0) == (check == smoke == 'success')


@pytest.mark.parametrize('selected', ['', 'invalid'])
def test_unknown_daily_selection_fails(selected):
    needs = {'check': {'result': 'success', 'outputs': {
        'integration': selected, 'smoke_result': 'skipped'}},
        'integration': {'result': 'skipped'}}
    assert run_gate('required', NEEDS_JSON=needs) != 0


@pytest.mark.parametrize('missing', ['check', 'integration', 'outputs', 'selection', 'smoke'])
def test_missing_gate_evidence_fails(missing):
    needs = {'check': {'result': 'success', 'outputs': {'integration': 'true', 'smoke_result': 'success', 'linux_wheel': 'true'}},
             'integration': {'result': 'success'}, 'linux': {'result': 'success'}}
    if missing in ('check', 'integration'): del needs[missing]
    elif missing == 'outputs': del needs['check']['outputs']
    else: del needs['check']['outputs']['integration' if missing == 'selection' else 'smoke_result']
    assert run_gate('required', NEEDS_JSON=needs) != 0


def test_daily_gate_owns_the_existing_protected_context():
    model = parse(DEVELOPMENT.read_text())
    gate = model['jobs']['required']
    assert gate['name'] == 'Live required gate'
    assert needs(gate) == {'check', 'integration', 'linux'}
    assert model['jobs']['check']['outputs']['smoke_result'] == '${{ steps.smoke.outcome }}'
    assert gate['if'] == 'always()'


@pytest.mark.parametrize('name', ['Runnable public documentation examples',
    'Installed wheel and external Go module', 'Installed owned E2E entry outside the source checkout'])
@pytest.mark.parametrize('failed_language', ['', 'python', 'go'])
def test_actual_language_loop_runs_go_once_and_preserves_failures(tmp_path, name, failed_language):
    import os
    import subprocess
    text = WORKFLOW.read_text()
    script = step_named(parse(text), name)['run']
    interpreters = {}
    for minor in ('3.11', '3.14'):
        executable = tmp_path/('py'+minor)
        executable.write_text('#!/bin/sh\n'
            'if [ "$1" = "-c" ]; then echo '+minor+'; exit 0; fi\n'
            'case "$*" in *--skip-go*) go=no ;; *) go=yes ;; esac\n'
            'echo "'+minor+' $go" >> "$CALLS"\n'
            'if [ "$FAIL" = python ]; then exit 1; fi\n'
            'if [ "$FAIL" = go ] && [ "$go" = yes ]; then exit 1; fi\n')
        executable.chmod(0o755);interpreters[minor]=str(executable)
    calls = tmp_path/'calls'
    result = subprocess.run(['bash', '-e', '-o', 'pipefail', '-c', script],
        env=dict(os.environ, PY311=interpreters['3.11'], PY314=interpreters['3.14'],
                 SOURCE_COMMIT='a'*40, CALLS=str(calls), FAIL=failed_language))
    if not failed_language:
        assert result.returncode == 0
        assert calls.read_text().splitlines() == ['3.11 yes', '3.14 no']
    else:
        assert result.returncode != 0



def test_release_e2e_steps_are_unconditional_and_shell_blocks_complete():
    import subprocess
    text = WORKFLOW.read_text()
    assert 'steps.families' not in text and 'scripts/live_selection.py' not in text
    for name in ['Owned E2E entry component and actual application checks',
                 'Installed owned E2E entry outside the source checkout',
                 'P1 real prepared command and callback on both Python minors']:
        step = step_named(parse(text), name)
        assert 'if' not in step, name
        code = step['run']
        assert 'for py in "$PY311" "$PY314"' in code
        subprocess.run(['bash', '-n'], input=code, text=True, check=True)
        assert 'build_alpha.py' not in code


@pytest.mark.parametrize('selected', ['true', 'false'])
@pytest.mark.parametrize('result', ['success', 'failure', 'cancelled', 'skipped', 'missing'])
def test_daily_protected_gate_requires_linux_execution(selected, result):
    needs = {'check': {'result': 'success', 'outputs': {
        'integration': 'false', 'smoke_result': 'skipped', 'linux_wheel': selected}},
        'integration': {'result': 'skipped'}}
    if result != 'missing':
        needs['linux'] = {'result': result}
    assert (run_gate('required', NEEDS_JSON=needs) == 0) == (
        result == ('success' if selected == 'true' else 'skipped'))
