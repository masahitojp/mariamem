"""Active fixture/resource/wire contracts; historical adoption is a manual audit."""
import copy
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from check_fixture_design import CONTRACT, validate_current_contract as validate


def test_current_contract_never_claims_runtime_acceptance_or_new_authorization():
    assert validate(json.loads(CONTRACT.read_text())) == {
        'result': 'FIXTURE_CONTRACT_LINT_PASS', 'runtime': 'NOT_RUN'}


@pytest.mark.parametrize('mutation', [
    'unbounded', 'connections', 'timing', 'resources', 'core_error_loss',
    'consume', 'fallback_rationale', 'e2e_stop', 'physical_retirement',
    'e2e_parallel', 'transient_children', 'wire_commands', 'wire_hash',
    'fixture_hash', 'wire_source_identity', 'fake_runtime_pass', 'unrecorded_fallback'])
def test_current_contract_mutations_are_rejected(mutation):
    plan = copy.deepcopy(json.loads(CONTRACT.read_text()))
    if mutation == 'unbounded':
        plan['resources']['max_forks_default'] = 0
    elif mutation == 'connections':
        plan['resources']['child_pool_max_open'] = 0
    elif mutation == 'timing':
        plan['resources']['time_outcomes'].remove('second_test_edits')
    elif mutation == 'resources':
        plan['resources']['counter_requirements'].remove('fd_baseline_peak_final')
    elif mutation == 'core_error_loss':
        plan['diagnostics']['core_failure_guarantees'].remove('cleanup_error')
    elif mutation == 'consume':
        plan['capture_oracles'].remove('accepted_failure_consumed')
    elif mutation == 'fallback_rationale':
        plan['diagnostics']['fallback_requires'].remove('concrete_obstacle')
    elif mutation == 'e2e_stop':
        plan['e2e']['required_hooks'].remove('StopReap')
    elif mutation == 'physical_retirement':
        plan['e2e']['quiesce_obligations'].remove('retire_physical_connections')
    elif mutation == 'e2e_parallel':
        plan['e2e']['one_case_per_owner'] = False
    elif mutation == 'transient_children':
        plan['e2e']['transient_children_per_live'] = 1
    elif mutation == 'wire_commands':
        plan['wire']['supported_commands'].remove(22)
    elif mutation == 'wire_hash':
        plan['wire']['source_sha256']['internal/mysqlwire/wire.go'] = '0' * 64
    elif mutation == 'wire_source_identity':
        historical = plan['wire']['historical_source_commit']
        assert historical != plan['wire']['source_commit']
        plan['wire']['source_commit'] = historical
    elif mutation == 'fixture_hash':
        plan['resources']['retention_input']['sha256'] = '0' * 64
    elif mutation == 'fake_runtime_pass':
        plan['future_runtime_status'] = 'PASS'
    elif mutation == 'unrecorded_fallback':
        plan['diagnostics']['selected_profile'] = 'basic-first'
        for row in plan['entries']: row['diagnostic_profile'] = 'basic-first'
    with pytest.raises(ValueError):
        validate(plan)


@pytest.mark.parametrize('mutation', ['env', 'bound', 'truncation', 'unknown', 'admission'])
def test_current_preparation_and_admission_contract_cannot_be_weakened(mutation):
    plan = copy.deepcopy(json.loads(CONTRACT.read_text()))
    p1 = plan['p1_approval']
    if mutation == 'env': p1['env_mode'] = 'REPLACE'
    elif mutation == 'bound': p1['output_tail_bytes_per_stream'] = 0
    elif mutation == 'truncation': p1['output_truncation'] = 'SILENT'
    elif mutation == 'unknown': p1['unknown_prepare'] = 'IGNORE'
    elif mutation == 'admission': p1['cleanup_debt'] = 'CONTINUE'
    with pytest.raises(ValueError): validate(plan)


def test_current_lint_does_not_replay_adoption_or_v060_placement():
    plan = copy.deepcopy(json.loads(CONTRACT.read_text()))
    for key in ('source_commit', 'entries', 'whole_scope_requires', 'django_policy',
                'first_delivery', 'delivery_scope', 'scope_status', 'implementation_authorized',
                'authorized_implementation_entries', 'reviewed_design_commit', 'p1_fixed_exit_acceptance'):
        del plan[key]
    for key in ('reviewed_design_commit', 'decision_commit', 'decision_record', 'decision_record_sha256', 'notice_paths'):
        del plan['p1_approval'][key]
    assert validate(plan) == {'result': 'FIXTURE_CONTRACT_LINT_PASS', 'runtime': 'NOT_RUN'}
