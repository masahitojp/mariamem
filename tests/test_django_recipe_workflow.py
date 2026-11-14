"""Both interpreter campaigns share one exact-source host, without hiding failure."""
import os
from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT/'.github/workflows/django-lifecycle.yml'


def step_script(text, name):
    from workflow_model import parse, step_named
    return step_named(parse(text), name)['run']



def test_single_host_retains_both_source_bound_python_campaigns():
    text = WORKFLOW.read_text()
    from workflow_model import parse, action
    recipe = parse(text)['jobs']['recipe']
    recipe_steps = recipe['steps']
    script = '\n'.join(step.get('run', '') for step in recipe_steps)
    assert 'python' not in recipe.get('strategy', {}).get('matrix', {})
    assert 'go build ' not in script
    assert any(step.get('with', {}).get('name') == 'release-runtime-${{ matrix.os }}-${{ inputs.source_commit }}' for step in recipe_steps)
    assert script.index('scripts/release_runtime.py') < script.index('tests/django_lifecycle/ci.py')
    assert any(action(step, 'actions/checkout') and step['with']['fetch-depth'] == 0 for step in recipe_steps)
    for minor in ['3.11', '3.14']:
        assert any(action(step, 'actions/setup-python') and step['with']['python-version'] == minor for step in recipe_steps)
        assert any(step.get('with', {}).get('name') == 'django-native-'+minor+'-${{ inputs.source_commit }}' and step['with']['path'] == 'build/django-reference/py'+minor for step in recipe_steps)
    acceptance = step_script(text, 'Standard runner and prepared entry on both interpreters')
    assert 'for py in "$PY311" "$PY314"' in acceptance
    assert '--host build/mariamem-host' in acceptance
    assert '--reference "build/django-reference/py$version/reference"' in acceptance
    assert '--output "build/django-evidence/py$version/acceptance"' in acceptance
    assert '--expected-source-commit "$SOURCE_COMMIT"' in acceptance
    assert any(step.get('with', {}).get('name') == 'django-${{ matrix.os }}-${{ inputs.source_commit }}' for step in recipe_steps)
    ci = (ROOT/'tests/django_lifecycle/ci.py').read_text()
    assert 'base.verify_go_binary(ROOT, args.host.resolve(), args.expected_source_commit)' in ci
    assert 'check_reference(reference, args.expected_source_commit, current_inputs, minor)' in ci


@pytest.mark.parametrize('failed_minor,failed_kind', [('', ''),
    ('3.11', 'standard'), ('3.14', 'standard'),
    ('3.11', 'units'), ('3.14', 'units'),
    ('3.11', 'prepared'), ('3.14', 'prepared'),
    ('3.11', 'parallel'), ('3.14', 'parallel')])
def test_both_interpreters_execute_and_either_failure_fails_job(tmp_path, failed_minor, failed_kind):
    # Execute the actual workflow shell; mock only Python entrypoints, not the
    # status aggregation. Failure in any campaign must fail the complete job.
    script = step_script(WORKFLOW.read_text(),
                         'Standard runner and prepared entry on both interpreters')
    paths = {}
    for minor in ['3.11', '3.14']:
        executable = tmp_path/('python'+minor)
        executable.write_text('#!/bin/sh\n'
                              'if [ "$1" = "-c" ]; then echo '+minor+'; exit 0; fi\n'
                              'case "$*" in\n'
                              '  *tests/django_lifecycle/ci.py*) kind=standard ;;\n'
                              '  *tests/django_prepared/run.py*) kind=prepared ;;\n'
                              '  *tests/django_prepared/xdist/run.py*) kind=parallel ;;\n'
                              '  "-m pytest "*) kind=units ;;\n'
                              '  "-m pip install "*) kind=install ;;\n'
                              '  *) exit 99 ;;\n'
                              'esac\n'
                              'printf "%s\\n" "'+minor+' $kind $*" >> "$CALLS"\n'
                              'if [ "$FAIL_MINOR" = "'+minor+'" ] && [ "$FAIL_KIND" = "$kind" ]; then exit 1; fi\n')
        executable.chmod(0o755)
        paths[minor] = str(executable)
    calls = tmp_path/'calls'
    env = dict(os.environ, PY311=paths['3.11'], PY314=paths['3.14'], CALLS=str(calls),
               FAIL_MINOR=failed_minor, FAIL_KIND=failed_kind,
               RUNNER_TEMP=str(tmp_path), SOURCE_COMMIT='a'*40)
    result = subprocess.run(['bash', '-e', '-o', 'pipefail', '-c', script], env=env)
    assert result.returncode == (1 if failed_minor else 0)
    observed = calls.read_text().splitlines()
    assert len(observed) == 10
    for index, minor in enumerate(['3.11', '3.14']):
        standard, units, install, prepared, parallel = observed[index*5:index*5+5]
        assert standard.startswith(minor+' standard ')
        assert 'py'+minor+'/reference' in standard and 'py'+minor+'/acceptance' in standard
        assert '--host build/mariamem-host' in standard
        assert units.startswith(minor+' units ')
        assert 'tests/test_django_prepared_owners.py tests/test_django_prepared_api.py' in units
        assert install.startswith(minor+' install -m pip install --no-deps ')
        assert prepared.startswith(minor+' prepared ')
        assert '--installed' in prepared and '--host-source-commit '+('a'*40) in prepared
        assert '--host build/mariamem-host' in prepared
        assert 'py'+minor+'/prepared' in prepared

        assert parallel.startswith(minor+' parallel ')
        assert '--installed' in parallel and '--host-source-commit '+('a'*40) in parallel
        assert 'py'+minor+'/parallel' in parallel
