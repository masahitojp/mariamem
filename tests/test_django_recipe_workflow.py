"""Both interpreter campaigns share one exact-source host, without hiding failure."""
import os
from pathlib import Path
import re
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT/'.github/workflows/django-lifecycle.yml'


def step_script(text, name):
    block = re.search(r'      - name: '+re.escape(name)+r'\n(.*?)(?=      - |\Z)', text, re.S)[1]
    return '\n'.join(line[10:] for line in block.split('        run: |\n', 1)[1].splitlines())


def test_single_host_retains_both_source_bound_python_campaigns():
    text = WORKFLOW.read_text()
    recipe = text.split('  recipe:\n', 1)[1]
    assert '        python:' not in recipe
    assert 'go build ' not in recipe
    assert 'release-runtime-${{ matrix.os }}-${{ inputs.source_commit }}' in recipe
    assert recipe.index('scripts/release_runtime.py') < recipe.index('tests/django_lifecycle/ci.py')
    assert 'fetch-depth: 0' in recipe
    for minor in ['3.11', '3.14']:
        assert f"python-version: '{minor}'" in recipe
        assert 'name: django-native-'+minor+'-${{ inputs.source_commit }}' in recipe
        assert 'path: build/django-reference/py'+minor in recipe
    acceptance = step_script(text, 'Standard runner, mixed orders, original errors and owner disposal on both interpreters')
    assert 'for py in "$PY311" "$PY314"' in acceptance
    assert '--host build/mariamem-host' in acceptance
    assert '--reference "build/django-reference/py$version/reference"' in acceptance
    assert '--output "build/django-evidence/py$version/acceptance"' in acceptance
    assert '--expected-source-commit "$SOURCE_COMMIT"' in acceptance
    assert 'name: django-${{ matrix.os }}-${{ inputs.source_commit }}' in recipe
    ci = (ROOT/'tests/django_lifecycle/ci.py').read_text()
    assert 'base.verify_go_binary(ROOT, args.host.resolve(), args.expected_source_commit)' in ci
    assert 'check_reference(reference, args.expected_source_commit, current_inputs, minor)' in ci


@pytest.mark.parametrize('step', [
    'Pure ownership and receipt mutation checks on both interpreters',
    'Standard runner, mixed orders, original errors and owner disposal on both interpreters',
])
@pytest.mark.parametrize('failed_minor', ['', '3.11', '3.14'])
def test_both_interpreters_execute_and_either_failure_fails_job(tmp_path, step, failed_minor):
    # Execute the actual workflow shell, substituting only Python entrypoints.
    script = step_script(WORKFLOW.read_text(), step)
    paths = {}
    for minor in ['3.11', '3.14']:
        executable = tmp_path/('python'+minor)
        executable.write_text('#!/bin/sh\n'
                              'if [ "$1" = "-c" ]; then echo '+minor+'; exit 0; fi\n'
                              'printf "%s\\n" "'+minor+' $*" >> "$CALLS"\n'
                              '[ "$FAIL_MINOR" != "'+minor+'" ]\n')
        executable.chmod(0o755)
        paths[minor] = str(executable)
    calls = tmp_path/'calls'
    env = dict(os.environ, PY311=paths['3.11'], PY314=paths['3.14'], CALLS=str(calls),
               FAIL_MINOR=failed_minor, RUNNER_TEMP=str(tmp_path), SOURCE_COMMIT='a'*40)
    result = subprocess.run(['bash', '-e', '-o', 'pipefail', '-c', script], env=env)
    assert result.returncode == (1 if failed_minor else 0)
    observed = calls.read_text().splitlines()
    assert len(observed) == 2
    assert observed[0].startswith('3.11 ') and observed[1].startswith('3.14 ')
    if step.startswith('Standard'):
        assert 'py3.11/reference' in observed[0] and 'py3.11/acceptance' in observed[0]
        assert 'py3.14/reference' in observed[1] and 'py3.14/acceptance' in observed[1]
        assert all('--host build/mariamem-host' in row for row in observed)
