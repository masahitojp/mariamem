import pytest
from workflow_model import parse, needs


def test_on_and_boolean_types():
    model = parse('on: workflow_dispatch\njobs:\n  check:\n    continue-on-error: false\n')
    assert model['on'] == 'workflow_dispatch'
    assert model['jobs']['check']['continue-on-error'] is False


def test_layout_and_needs_equivalence():
    first = parse('on: workflow_dispatch\njobs:\n  gate:\n    needs: check\n')
    second = parse('# comment\njobs: {gate: {needs: [check]}}\non: workflow_dispatch\n')
    assert needs(first['jobs']['gate']) == needs(second['jobs']['gate'])
    assert needs({'needs': []}) != needs(first['jobs']['gate'])


@pytest.mark.parametrize('text', [
    'jobs: {}\njobs: {}',
    'jobs: {check: {permissions: read-all, permissions: write-all}}',
    'jobs: [check]',
    'jobs: {check: false}',
    'jobs: {check: {steps: [false]}}',
    'jobs: [',
])
def test_invalid_or_ambiguous_input_rejected(text):
    with pytest.raises(ValueError, match='candidate.yml'):
        parse(text, 'candidate.yml')


def test_safe_loader_is_not_modified():
    import yaml
    assert True in yaml.safe_load('on: workflow_dispatch')
    assert 'on' in parse('on: workflow_dispatch\njobs: {}')


def test_local_reference_cannot_escape(tmp_path):
    from workflow_model import local_workflow
    with pytest.raises(ValueError, match='escapes'):
        local_workflow(tmp_path, {'uses': './.github/workflows/../../outside.yml'})


def test_real_validators_accept_yaml_formatting():
    from pathlib import Path
    import yaml
    from workflow_model import WorkflowLoader
    from test_ci_efficiency import validate_cancellation, validate_caches, validate_release_workflow
    from test_live_ci_workflow import validate, validate_development_owners
    root = Path(__file__).resolve().parents[1]
    for name in ('check', 'live-host', 'dump-import-productization', 'django-lifecycle'):
        text = (root / '.github/workflows' / (name + '.yml')).read_text()
        formatted = '# harmless comment\n' + yaml.safe_dump(yaml.load(text, Loader=WorkflowLoader), sort_keys=True, indent=4)
        validate_caches(formatted, name)
        if name == 'check':
            validate_cancellation(formatted)
            validate_development_owners(formatted)
        if name == 'live-host':
            validate(formatted)
            validate_release_workflow(formatted, '--expected-source-commit')


@pytest.mark.parametrize('mutation', ['workflow_permission', 'job_permission', 'trigger', 'dependency', 'step_order'])
def test_real_contract_mutations(mutation):
    from pathlib import Path
    import yaml
    from test_ci_efficiency import validate_caches, validate_release_workflow
    from test_live_ci_workflow import validate
    root = Path(__file__).resolve().parents[1]
    model = parse((root / '.github/workflows/live-host.yml').read_text())
    validator = lambda text: validate_caches(text, 'live-host')
    if mutation == 'workflow_permission':
        model['permissions']['contents'] = 'write'
    elif mutation == 'job_permission':
        model['jobs']['live']['permissions'] = {'contents': 'write'}
    elif mutation == 'trigger':
        model['on']['pull_request_target'] = {}
        validator = lambda text: validate_release_workflow(text, '--expected-source-commit')
    elif mutation == 'dependency':
        model['jobs']['live']['needs'] = []
        validator = validate
    else:
        owner = model['jobs']['live']['steps']
        setup = next(i for i, step in enumerate(owner) if step.get('uses', '').startswith('actions/setup-go@'))
        clean = next(i for i, step in enumerate(owner) if 'go clean -testcache' in step.get('run', ''))
        owner[setup], owner[clean] = owner[clean], owner[setup]
    with pytest.raises(AssertionError):
        validator(yaml.safe_dump(model))
