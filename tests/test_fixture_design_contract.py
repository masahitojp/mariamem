"""Reject the seven review-gap classes before claiming the design is complete."""
import copy
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from check_fixture_design import CONTRACT, validate


def test_reviewed_contract_authorizes_g1_p1_without_runtime_acceptance():
    assert validate(json.loads(CONTRACT.read_text())) == {
        'result': 'DESIGN_LINT_PASS', 'runtime': 'NOT_RUN', 'authorized_implementation_entries': ['G1', 'P1']}


@pytest.mark.parametrize('mutation', [
    'entry', 'whole_scope', 'unbounded', 'connections', 'timing', 'resources',
    'diagnostic_mismatch', 'core_error_loss', 'consume', 'posthoc_decision',
    'fallback_rationale', 'e2e_stop', 'physical_retirement', 'e2e_parallel',
    'transient_children', 'old_wire', 'wire_commands', 'wire_hash',
    'fixture_hash', 'fake_runtime_pass', 'fake_approval', 'unrecorded_fallback',
    'django_blocking', 'waive_shared', 'drop_browser', 'review_identity',
])
def test_review_gap_mutations_are_rejected(mutation):
    plan = copy.deepcopy(json.loads(CONTRACT.read_text()))
    if mutation == 'entry': plan['entries'].pop()
    elif mutation == 'whole_scope': plan['whole_scope_requires'].remove('EP1')
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
    elif mutation == 'fake_approval': plan['authorized_implementation_entries'].append('D1')
    elif mutation == 'django_blocking': plan['django_policy']['blocking_for_v060'] = True
    elif mutation == 'waive_shared': plan['django_policy']['shared_defects'] = 'IGNORE'
    elif mutation == 'drop_browser': plan['django_policy']['python_e2e'] = 'DEFER'
    elif mutation == 'review_identity': plan['reviewed_design_commit'] = '0' * 40
    elif mutation == 'unrecorded_fallback':
        plan['diagnostics']['selected_profile'] = 'basic-first'
        for row in plan['entries']: row['diagnostic_profile'] = 'basic-first'
    with pytest.raises(ValueError):
        validate(plan)


@pytest.mark.parametrize('mutation', ['scope', 'allowlist', 'identity', 'record', 'env', 'bound', 'truncation', 'unknown', 'admission', 'notices'])
def test_p1_approval_conditions_cannot_be_weakened(mutation):
    plan = copy.deepcopy(json.loads(CONTRACT.read_text()))
    p1 = plan['p1_approval']
    if mutation == 'scope': plan['scope_status'] = 'APPROVED_WITH_DJANGO_NONBLOCKING'
    elif mutation == 'allowlist': plan['authorized_implementation_entries'] = ['G1']
    elif mutation == 'identity': p1['decision_commit'] = '0' * 40
    elif mutation == 'record': p1['decision_record_sha256'] = '0' * 64
    elif mutation == 'env': p1['env_mode'] = 'REPLACE'
    elif mutation == 'bound': p1['output_tail_bytes_per_stream'] = 0
    elif mutation == 'truncation': p1['output_truncation'] = 'SILENT'
    elif mutation == 'unknown': p1['unknown_prepare'] = 'IGNORE'
    elif mutation == 'admission': p1['cleanup_debt'] = 'CONTINUE'
    elif mutation == 'notices': p1['notice_paths'].pop()
    with pytest.raises(ValueError): validate(plan)


@pytest.mark.parametrize('path, removed', [
    ('docs/python.md', 'PrepareCommand'),
    ('docs/python.md', 'same worker'),
    ('docs/python.md', '16 KiB'),
    ('docs/release-notes/unreleased.md', 'PrepareCommand'),
    ('docs/release-notes/unreleased.md', 'same worker'),
    ('docs/release-notes/unreleased.md', '16 KiB'),
])
def test_p1_notice_omissions_are_detected(tmp_path, path, removed):
    from check_fixture_design import validate_p1_notices
    for name in ['docs/python.md', 'docs/release-notes/unreleased.md']:
        target = tmp_path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text((ROOT / name).read_text())
    validate_p1_notices(tmp_path)
    target = tmp_path / path
    target.write_text(target.read_text().replace(removed, 'omitted'))
    with pytest.raises(ValueError, match='notice missing'):
        validate_p1_notices(tmp_path)
