"""Regression contracts for compiler reuse and superseded-PR cancellation."""
import json
import os
from pathlib import Path
import subprocess

import pytest
from workflow_model import parse, events, steps, commands, action, local_workflow

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ['check', 'live-host', 'dump-import-productization', 'django-lifecycle']


def validate_cancellation(text):
    concurrency = parse(text)['concurrency']
    assert concurrency['group'] == '${{ github.workflow }}-${{ github.event_name }}-${{ github.event.pull_request.number || github.run_id }}'
    assert concurrency['cancel-in-progress'] == "${{ github.event_name == 'pull_request' }}"


def validate_caches(text, name):
    model = parse(text)
    assert model.get('permissions') == {'contents': 'read'}, f'{name}: workflow permissions must be contents:read'
    assert all(job.get('permissions', {'contents': 'read'}) == {'contents': 'read'} for job in model['jobs'].values()), f'{name}: job permissions expanded'
    found = 0
    namespaces = []
    for job, block in model['jobs'].items():
        job_steps = block.get('steps', [])
        setups = [(i, step) for i, step in enumerate(job_steps) if action(step, 'actions/setup-go')]
        if not setups:
            continue
        found += 1
        execution = '\n'.join(step.get('run', '') for step in job_steps)
        if name in ('dump-import-productization', 'django-lifecycle'):
            assert all(step['with']['cache'] is False for _, step in setups)
            assert 'go build ' not in execution
            assert 'scripts/release_runtime.py' in execution
            continue
        for _, setup in setups:
            assert setup['with']['cache'] is True
            paths = tuple(setup['with']['cache-dependency-path'].split())
            assert paths == ('go.mod', 'go.sum')
            namespaces.append(paths)
        assert 'cache-hit' not in str(block)
        assert 'echo "GOCACHE=$(go env GOCACHE)" >> "$GITHUB_ENV"' in execution
        assert 'go clean -testcache' in execution
        clean = next(i for i, step in enumerate(job_steps) if 'go clean -testcache' in step.get('run', ''))
        assert all(i < clean for i, _ in setups)
        consumers = [i for i, step in enumerate(job_steps) if any(value in step.get('run', '') for value in
            ('python scripts/verify.py', 'go test ', 'go build ', 'scripts/build_alpha.py', 'tests/live_acceptance/installed.py'))]
        assert consumers and clean <= min(consumers)
        if clean == min(consumers):
            script = job_steps[clean]['run']
            assert script.index('go clean -testcache') < min(script.index(value) for value in
                ('python scripts/verify.py', 'go test ', 'go build ', 'scripts/build_alpha.py', 'tests/live_acceptance/installed.py') if value in script)
        assert 'GOCACHE=$RUNNER_TEMP/' not in execution
        if name == 'check' and job == 'check':
            assert sum(step.get('if') == "steps.diff.outputs.check_scope == 'full'" for step in job_steps[:clean+1]) == 2
    if name in ('check', 'dump-import-productization'):
        assert len(namespaces) == len(set(namespaces))
    assert found == {'check': 1, 'live-host': 2, 'dump-import-productization': 1, 'django-lifecycle': 1}[name]


@pytest.mark.parametrize('name', WORKFLOWS)
def test_normal_ci_keeps_fresh_tests_and_pr_isolation(name):
    text = (ROOT/'.github/workflows'/f'{name}.yml').read_text()
    if name == 'check':
        validate_cancellation(text)
    validate_caches(text, name)


@pytest.mark.parametrize('before,after', [
    ('github.workflow', 'github.repository'),
    ('github.event.pull_request.number || github.run_id', 'github.ref'),
    ("github.event_name == 'pull_request'", 'true'),
])
def test_cancellation_cannot_include_other_workflows_or_non_pr_runs(before, after):
    text = (ROOT/'.github/workflows/check.yml').read_text()
    with pytest.raises(AssertionError):
        validate_cancellation(text.replace(before, after))


@pytest.mark.parametrize('before,after', [
    ('cache: true', 'cache: false'),
    ('go clean -testcache', 'echo reused-results'),
    ('GOCACHE=$(go env GOCACHE)', 'IGNORED=$(go env GOCACHE)'),
    ('            go.mod\n', '            .github/workflows/live-host.yml\n'),
])
def test_cache_regressions_are_detected(before, after):
    text = (ROOT/'.github/workflows/live-host.yml').read_text()
    with pytest.raises(AssertionError):
        validate_caches(text.replace(before, after), 'live-host')


def test_cache_export_preserves_paths_with_spaces_and_invalidates_results(tmp_path):
    text = (ROOT/'.github/workflows/live-host.yml').read_text()
    script = next(step['run'] for step in steps(parse(text)) if 'echo "GOCACHE=' in step.get('run', '') and 'go clean -testcache' in step['run'])
    commands = script
    tools = tmp_path/'bin'
    tools.mkdir()
    go = tools/'go'
    go.write_text('#!/bin/sh\nif [ "$1 $2" = "env GOCACHE" ]; then\n  printf "%s\\n" "$CACHE_PATH"\nelif [ "$1 $2" = "clean -testcache" ]; then\n  printf "invalidated\\n" >> "$TEST_LOG"\nelse\n  exit 1\nfi\n')
    go.chmod(0o755)
    output = tmp_path/'github-env'
    log = tmp_path/'test-log'
    cache = str(tmp_path/'compiler cache')
    env = dict(os.environ, PATH=str(tools)+os.pathsep+os.environ['PATH'],
               GITHUB_ENV=str(output), CACHE_PATH=cache, TEST_LOG=str(log))
    subprocess.run(['bash', '-e', '-c', commands], env=env, check=True)
    assert output.read_text() == 'GOCACHE='+cache+'\n'
    assert log.read_text() == 'invalidated\n'
    # build_alpha's existing setdefault must retain the exported compiler path.
    import ast
    tree = ast.parse((ROOT/'scripts/build_alpha.py').read_text())
    statement = next(node for node in tree.body if isinstance(node, ast.Expr)
                     and isinstance(node.value, ast.Call)
                     and ast.unparse(node.value.func) == 'build_env.setdefault')
    inherited = {'GOCACHE': cache}
    exec(compile(ast.Module(body=[statement], type_ignores=[]), 'build_alpha cache', 'exec'),
         {'build_env': inherited, 'ROOT': ROOT})
    assert inherited['GOCACHE'] == cache


def test_pr_does_not_start_macos_acceptance_jobs():
    def runners(model, seen):
        for block in model['jobs'].values():
            if 'uses' in block:
                reference = block['uses']
                assert reference not in seen, 'recursive reusable workflow'
                yield from runners(local_workflow(ROOT, block), seen | {reference})
                continue
            runner = block['runs-on']
            matrix = block.get('strategy', {}).get('matrix', {})
            if isinstance(runner, str) and runner.startswith('${{ matrix.'):
                axis = runner.removeprefix('${{ matrix.').removesuffix(' }}')
                values = matrix.get(axis, [])
                if not values:
                    values = [entry[axis] for entry in matrix.get('include', [])]
                assert values, 'runner matrix is empty'
                yield from values
            else:
                yield runner
    for name in WORKFLOWS:
        model = parse((ROOT/'.github/workflows'/f'{name}.yml').read_text())
        if 'pull_request' in events(model):
            if name in ('check', 'django-lifecycle', 'dump-import-productization'):
                assert all(job.get('runs-on') != '${{ matrix.os }}' for job in model['jobs'].values())
            assert all(not str(value).startswith('macos-') for value in runners(model, set()))


def test_daily_checks_and_smoke_share_one_checkout_and_compiler_cache():
    model = parse((ROOT/'.github/workflows/check.yml').read_text())
    all_steps = steps(model)
    assert sum(action(step, 'actions/checkout') for step in all_steps) == 1
    assert sum(action(step, 'actions/setup-go') for step in all_steps) == 1
    check = model['jobs']['check']
    script = '\n'.join(step.get('uses', '') + '\n' + step.get('run', '') for step in check['steps'])
    assert script.count('go clean -testcache') == 1
    order = ['scripts/development_scope.py', 'actions/setup-go@', 'go clean -testcache',
             'scripts/verify.py check', 'scripts/verify.py smoke']
    assert [script.index(item) for item in order] == sorted(script.index(item) for item in order)
    conditions = [step.get('if') for step in check['steps']]
    assert "steps.diff.outputs.check_scope == 'full'" in conditions
    assert "steps.diff.outputs.integration == 'true'" in conditions
    assert 'cache-hit' not in str(check)
    assert 'continue-on-error' not in check and all('continue-on-error' not in step for step in check['steps'])
    assert not any(action(step, name) for step in check['steps'] for name in ('actions/upload-artifact', 'actions/download-artifact'))
    assert 'GOCACHE=' in script and 'go clean -cache' not in script


def validate_release_workflow(text, source_argument):
    model = parse(text)
    assert set(events(model)) == {'workflow_call'}
    checkouts = [step for step in steps(model) if action(step, 'actions/checkout')]
    assert checkouts and all(step.get('with', {}).get('ref') == '${{ inputs.source_commit }}' for step in checkouts)
    assert source_argument+' "$SOURCE_COMMIT"' in commands(model)


RELEASE_WORKFLOWS = {
    'live-host': '--expected-source-commit',
    'dump-import-productization': '--expected-source-commit',
    'django-lifecycle': '--expected-source-commit',
    'connection-routing': '--source-commit',
    'preparation-migration': '--source-commit',
    'worker-failure': '--source-commit',
}


@pytest.mark.parametrize('workflow,source_argument', RELEASE_WORKFLOWS.items())
def test_release_workflows_are_callable_only_and_candidate_bound(workflow, source_argument):
    validate_release_workflow((ROOT/'.github/workflows'/f'{workflow}.yml').read_text(), source_argument)


@pytest.mark.parametrize('before,after', [
    ('  workflow_call:', '  pull_request:'),
    ('ref: ${{ inputs.source_commit }}', 'ref: main'),
    ('--expected-source-commit', '--unbound')])
def test_shared_release_policy_rejects_trigger_and_identity_regressions(before, after):
    text = (ROOT/'.github/workflows/live-host.yml').read_text()
    with pytest.raises(AssertionError):
        validate_release_workflow(text.replace(before, after), '--expected-source-commit')


def test_only_development_is_automatic_and_release_runtime_owner_is_manual():
    release = parse((ROOT/'.github/workflows/release-candidate-ready.yml').read_text())
    called = [Path(job['uses']).stem for job in release['jobs'].values() if 'uses' in job]
    assert set(called) == set(RELEASE_WORKFLOWS) and len(called) == len(RELEASE_WORKFLOWS)
    for path in (ROOT/'.github/workflows').glob('*.yml'):
        triggers = events(parse(path.read_text(), str(path)))
        assert not set(triggers) & {'push', 'schedule', 'workflow_run', 'pull_request_target'}, path
        if 'pull_request' in triggers:
            assert path.name == 'check.yml'
    daily = parse((ROOT/'.github/workflows/check.yml').read_text())
    assert events(daily)['pull_request']['branches'] == ['main']
    assert not set(events(daily)['pull_request']) & {'paths', 'paths-ignore'}
    assert all('ref' not in step.get('with', {}) for step in steps(daily))
    assert 'pull_request.head.sha' not in str(daily)
    from runtime_validation import WORKFLOW
    assert WORKFLOW == '.github/workflows/v044-product-validation.yml'
    assert 'workflow_dispatch' in events(parse((ROOT/WORKFLOW).read_text()))


def development_gate_script():
    model = parse((ROOT/'.github/workflows/check.yml').read_text())
    script = model['jobs']['required']['steps'][0]['run']
    return script.split("<<'PY'\n", 1)[1].rsplit('\nPY', 1)[0]


@pytest.mark.parametrize('smoke', ['true', 'false'])
@pytest.mark.parametrize('linux', ['true', 'false'])
def test_required_gate_rejects_failed_missing_or_skipped_selected_work(smoke, linux, monkeypatch):
    import copy
    script = development_gate_script()
    expected = lambda flag: 'success' if flag == 'true' else 'skipped'
    valid = {'check': {'result': 'success', 'outputs': {
        'integration': smoke, 'linux_wheel': linux, 'smoke_result': expected(smoke)}},
        'integration': {'result': expected(smoke)}, 'linux': {'result': expected(linux)}}
    def evaluate(value):
        monkeypatch.setenv('NEEDS_JSON', json.dumps(value))
        exec(compile(script, 'development required gate', 'exec'), {})
    evaluate(valid)
    for job in valid:
        missing = copy.deepcopy(valid)
        del missing[job]
        with pytest.raises((AssertionError, KeyError)):
            evaluate(missing)
        for result in ('success', 'skipped', 'failure', 'cancelled', ''):
            if result == valid[job]['result']:
                continue
            changed = copy.deepcopy(valid)
            changed[job]['result'] = result
            with pytest.raises(AssertionError):
                evaluate(changed)
    for output in valid['check']['outputs']:
        for value in (None, '', 'invalid', 'failure', 'cancelled', 'true', 'false', 'success', 'skipped'):
            if value == valid['check']['outputs'][output]:
                continue
            changed = copy.deepcopy(valid)
            if value is None:
                del changed['check']['outputs'][output]
            else:
                changed['check']['outputs'][output] = value
            with pytest.raises(AssertionError):
                evaluate(changed)


def test_linux_packaging_inherits_compiler_cache_without_reusing_test_pass():
    model = parse((ROOT/'.github/workflows/linux-wheel.yml').read_text())
    sequence = model['jobs']['wheel']['steps']
    cache = next(i for i, step in enumerate(sequence) if 'go clean -testcache' in step.get('run', ''))
    assert 'echo "GOCACHE=$(go env GOCACHE)" >> "$GITHUB_ENV"' in sequence[cache]['run']
    assert all(i > cache for i, step in enumerate(sequence)
               if 'go test ' in step.get('run', '') or 'scripts/build_alpha.py' in step.get('run', ''))
    assert sum('scripts/build_alpha.py' in step.get('run', '') for step in sequence) == 1
    assert 'cache-hit' not in str(sequence)
