"""Workflow-model users must have PyYAML in their actual execution venv."""
from pathlib import Path
import pytest
from workflow_model import load, step_named

ROOT = Path(__file__).resolve().parents[1]


def validate(p1_requirements, timer, uca):
    assert '-r ../workflow-requirements.txt' in p1_requirements.splitlines()
    for name, text in [('timer-product', timer), ('uca-canonical', uca)]:
        model = __import__('workflow_model').parse(text, name)
        install = step_named(model, 'Exact clean source and source input controls')['run']
        assert '-r tests/workflow-requirements.txt' in install, name
        timer_step = step_named(model, 'Canonical timer source regression and mutations')['run']
        assert 'pytest tests/test_timer_source.py' in timer_step, name
    model = load(ROOT/'.github/workflows/live-host.yml')
    run = step_named(model, 'P1 real prepared command and callback on both Python minors')['run']
    assert '-r tests/preparation_migration_acceptance/requirements.txt' in run
    assert 'tests/test_p1_pytest_entry.py' in run


def inputs():
    return [(ROOT/'tests/preparation_migration_acceptance/requirements.txt').read_text(),
            (ROOT/'.github/workflows/timer-product.yml').read_text(),
            (ROOT/'.github/workflows/uca-canonical.yml').read_text()]


def test_all_independent_venvs_install_parser():
    validate(*inputs())


@pytest.mark.parametrize('index', [0, 1, 2])
def test_missing_parser_install_is_rejected(index):
    values = inputs()
    value = '-r ../workflow-requirements.txt' if index == 0 else '-r tests/workflow-requirements.txt'
    assert value in values[index]
    values[index] = values[index].replace(value, '')
    with pytest.raises(AssertionError):
        validate(*values)
