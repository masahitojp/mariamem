"""Reject the seven review-gap classes before claiming the design is complete."""
import copy
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from check_fixture_design import CONTRACT, require_design_only_tree, validate


def test_proposed_contract_is_not_runtime_or_implementation_acceptance():
    assert validate(json.loads(CONTRACT.read_text())) == {
        'result': 'DESIGN_LINT_PASS', 'runtime': 'NOT_RUN', 'implementation_authorized': False}


def test_helper_code_cannot_enter_the_design_only_tree(tmp_path):
    require_design_only_tree(tmp_path)
    package = tmp_path / 'mariamemtest'
    package.mkdir()
    (package / 'fixture.go').write_text('package mariamemtest\n')
    with pytest.raises(ValueError, match='unapproved proposal'):
        require_design_only_tree(tmp_path)


@pytest.mark.parametrize('mutation', [
    'entry', 'whole_scope', 'unbounded', 'connections', 'timing', 'resources',
    'diagnostic_mismatch', 'core_error_loss', 'consume', 'posthoc_decision',
    'fallback_rationale', 'e2e_stop', 'physical_retirement', 'e2e_parallel',
    'transient_children', 'old_wire', 'wire_commands', 'wire_hash',
    'fixture_hash', 'fake_runtime_pass', 'fake_approval', 'unrecorded_fallback',
])
def test_review_gap_mutations_are_rejected(mutation):
    plan = copy.deepcopy(json.loads(CONTRACT.read_text()))
    if mutation == 'entry': plan['entries'].pop()
    elif mutation == 'whole_scope': plan['whole_scope_requires'].remove('D1')
    elif mutation == 'unbounded': plan['resources']['max_forks_default'] = 0
    elif mutation == 'connections': plan['resources']['child_pool_max_open'] = 0
    elif mutation == 'timing': plan['resources']['time_outcomes'].remove('second_test_edits')
    elif mutation == 'resources': plan['resources']['counter_requirements'].remove('fd_baseline_peak_final')
    elif mutation == 'diagnostic_mismatch': plan['entries'][1]['diagnostic_profile'] = 'basic-first'
    elif mutation == 'core_error_loss': plan['diagnostics']['core_failure_guarantees'].remove('cleanup_error')
    elif mutation == 'consume': plan['capture_oracles'].remove('accepted_failure_consumed')
    elif mutation == 'posthoc_decision': plan['diagnostics']['record_timing'] = 'after-implementation'
    elif mutation == 'fallback_rationale': plan['diagnostics']['fallback_requires'].remove('concrete_obstacle')
    elif mutation == 'e2e_stop': plan['e2e']['required_hooks'].remove('StopReap')
    elif mutation == 'physical_retirement': plan['e2e']['quiesce_obligations'].remove('retire_physical_connections')
    elif mutation == 'e2e_parallel': plan['e2e']['one_case_per_owner'] = False
    elif mutation == 'transient_children': plan['e2e']['transient_children_per_live'] = 1
    elif mutation == 'old_wire': plan['wire']['current_inventory'] = plan['wire']['historical_inventory']
    elif mutation == 'wire_commands': plan['wire']['supported_commands'].remove(22)
    elif mutation == 'wire_hash': plan['wire']['source_sha256']['internal/mysqlwire/wire.go'] = '0' * 64
    elif mutation == 'fixture_hash': plan['resources']['retention_input']['sha256'] = '0' * 64
    elif mutation == 'fake_runtime_pass': plan['future_runtime_status'] = 'PASS'
    elif mutation == 'fake_approval': plan['implementation_authorized'] = True
    elif mutation == 'unrecorded_fallback':
        plan['diagnostics']['selected_profile'] = 'basic-first'
        for row in plan['entries']: row['diagnostic_profile'] = 'basic-first'
    with pytest.raises(ValueError):
        validate(plan)
