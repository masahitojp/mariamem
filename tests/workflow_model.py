"""Strict, non-executing workflow reader for test contracts."""
import re
from pathlib import Path
import yaml


class WorkflowLoader(yaml.SafeLoader):
    pass


WorkflowLoader.yaml_implicit_resolvers = {
    key: [(tag, pattern) for tag, pattern in rules
          if tag != 'tag:yaml.org,2002:bool']
    for key, rules in yaml.SafeLoader.yaml_implicit_resolvers.items()
}
WorkflowLoader.add_implicit_resolver('tag:yaml.org,2002:bool',
                                     re.compile(r'^(?:true|false)$', re.I),
                                     list('tTfF'))


def mapping(loader, node):
    result = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node)
        if key in result:
            raise ValueError(f'duplicate workflow key {key!r} at line {key_node.start_mark.line + 1}')
        result[key] = loader.construct_object(value_node)
    return result


WorkflowLoader.add_constructor('tag:yaml.org,2002:map', mapping)


def parse(text, source='<workflow>'):
    try:
        value = yaml.load(text, Loader=WorkflowLoader)
        if not isinstance(value, dict) or not isinstance(value.get('jobs'), dict):
            raise ValueError('expected workflow mapping with jobs mapping')
        for name, job in value['jobs'].items():
            if not isinstance(job, dict):
                raise ValueError(f'jobs.{name}: expected mapping')
            if 'steps' in job and (not isinstance(job['steps'], list) or any(not isinstance(step, dict) for step in job['steps'])):
                raise ValueError(f'jobs.{name}.steps: expected list of mappings')
        return value
    except (yaml.YAMLError, ValueError) as error:
        raise ValueError(f'{source}: {error}') from error


def load(path):
    path = Path(path)
    return parse(path.read_text(), str(path))


def needs(job):
    value = job.get('needs', [])
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list) or any(not isinstance(x, str) for x in value):
        raise ValueError('needs must be a string or list of strings')
    return set(value)


def events(model):
    value = model.get('on', {})
    if isinstance(value, str):
        return {value: None}
    if isinstance(value, list):
        return dict.fromkeys(value)
    if not isinstance(value, dict):
        raise ValueError('on must be a string, list or mapping')
    return value


def steps(model):
    return [step for job in model['jobs'].values() for step in job.get('steps', [])]


def step_named(model, name):
    matches = [step for step in steps(model) if step.get('name') == name]
    assert len(matches) == 1, f'expected one step named {name!r}, found {len(matches)}'
    return matches[0]


def commands(model):
    return '\n'.join(step.get('run', '') for step in steps(model))


def action(step, name):
    return step.get('uses', '').startswith(name + '@')


def local_workflow(root, job):
    reference = job.get('uses', '')
    if not reference.startswith('./.github/workflows/'):
        raise ValueError(f'expected local reusable workflow: {reference!r}')
    path = (Path(root) / reference).resolve()
    directory = (Path(root) / '.github/workflows').resolve()
    if path.parent != directory:
        raise ValueError(f'workflow reference escapes workflow directory: {reference}')
    return load(path)


def manual_platform_commands(path):
    model = load(path)
    assert 'workflow_dispatch' in events(model), str(path)
    assert 'push' not in events(model), str(path)
    assert all('continue-on-error' not in owner for owner in [model, *model['jobs'].values(), *steps(model)]), str(path)
    assert any(job.get('strategy', {}).get('matrix', {}).get('runner') == ['macos-15', 'ubuntu-24.04'] for job in model['jobs'].values()), str(path)
    return commands(model)
