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

def test_migrated_consumers_accept_reordered_workflows(monkeypatch):
    """Exercise real contract owners with every YAML mapping reordered."""
    from pathlib import Path
    import importlib
    import yaml
    from workflow_model import WorkflowLoader
    original = Path.read_text
    def reverse(value):
        if isinstance(value, dict):
            return {key: reverse(item) for key, item in reversed(list(value.items()))}
        if isinstance(value, list):
            return [reverse(item) for item in value]
        return value
    def read(path, *args, **kwargs):
        text = original(path, *args, **kwargs)
        if path.suffix == '.yml' and path.parent.name == 'workflows':
            return '# harmless formatting\n' + yaml.safe_dump(reverse(yaml.load(text, Loader=WorkflowLoader)), sort_keys=False, indent=4)
        return text
    monkeypatch.setattr(Path, 'read_text', read)
    owners = {
        'test_runtime_validation': ['test_workflow_requires_proof_before_expensive_work'],
        'test_release_runtime': ['test_release_builds_one_wheel_and_every_feature_uses_it', 'test_candidate_cache_retains_race_compilation_but_never_skips_tests', 'test_both_platforms_share_the_same_step_definitions_and_frozen_proof'],
        'test_pypi_release': ['test_pypi_workflow_has_no_verify_upload_or_build_and_keeps_normal_gates'],
        'test_generated_release': ['test_recovery_workflow_has_no_qualification_or_publication_dependencies'],
        'test_release_features': ['test_workflow_rechecks_original_proof_after_guard_and_retains_publication_boundary', 'test_common_units_have_one_feature_owner_and_preserve_python_boundaries'],
        'test_canonical_toolchain_pins': ['test_release_ci_uses_authoritative_go_pin'],
        'test_static_image_workflow': ['test_static_image_candidate_boundaries'],
        'test_timer_source': ['test_product_candidate_requires_canonical_and_platform_timer_checks'],
        'test_p1_pytest_entry': ['test_required_hosts_run_new_entry_controls_for_both_python_minors'],
        'test_go_fixture_campaign': ['test_ci_runs_both_modes_and_requires_both_host_artifacts'],
        'test_go_fixture_completion': ['test_both_host_workflow_executes_and_requires_completion_receipts'],
        'test_text_dedup_acceptance': ['test_ordinary_ci_preserves_reference_and_enforces_per_host_budget'],
        'test_django_recipe_workflow': ['test_single_host_retains_both_source_bound_python_campaigns'],
        'test_routing_ci_workflow': ['test_routing_release_keeps_compatibility_and_both_platforms'],
        'test_ci_publication_workflow': ['test_publication_job_gate_and_handoff', 'test_heavy_suites_are_release_only_and_use_resolved_candidate'],
    }
    for module, names in owners.items():
        for name in names:
            getattr(importlib.import_module(module), name)()
