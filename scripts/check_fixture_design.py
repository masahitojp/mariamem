#!/usr/bin/env python3
"""Lint the reviewed fixture contract; never grant runtime acceptance."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess

from git_identity import require_commit

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / 'docs/reviews/v06x-fixture-acceptance.json'
ENTRIES = {'P1', 'G1', 'D1', 'EP1', 'EG1'}


def validate_p1_notices(root):
    python = (root / 'docs/python.md').read_text()
    notes = (root / 'docs/release-notes/unreleased.md').read_text()
    for text in (python, notes):
        if not all(value in text for value in ('PrepareCommand', 'same worker', '16 KiB')):
            raise ValueError('P1 public API/admission/output notice missing')
    if not all(value in python for value in ('## Prepared command entry', '## Prepared-entry cleanup failures')):
        raise ValueError('P1 public guide sections missing')


def validate(plan, root=ROOT):
    def need(condition, reason):
        if not condition:
            raise ValueError(reason)
    require_commit(root, plan['source_commit'])
    rows = plan['entries']
    need({v['id'] for v in rows} == ENTRIES and len(rows) == len(ENTRIES), 'named entries incomplete/duplicated')
    p1_entry = next(row for row in rows if row['id'] == 'P1')
    need(p1_entry['status'] == 'FIXED_EXIT_ACCEPTED',
         'P1 status differs from fixed-exit acceptance state')
    acceptance = plan['p1_fixed_exit_acceptance']
    require_commit(root, acceptance['source_commit'])
    receipt_path = root / acceptance['receipt']
    need(receipt_path.is_file(), 'P1 fixed-exit receipt missing')
    receipt = json.loads(receipt_path.read_text())
    need(receipt['result'] == 'PASS_P1_FIXED_EXIT_RUNTIME'
         and receipt['source_commit'] == acceptance['source_commit'],
         'P1 fixed-exit status lacks matching acceptance evidence')
    need(set(plan['whole_scope_requires']) == ENTRIES - {'D1'}, 'required completion set changed')
    need(plan['django_policy'] == {
        'blocking_for_v060': False,
        'if_difficult': 'DEFER_WITH_OBSTACLE_AND_REMAINING_WORK',
        'shared_defects': 'ASSESS_AGAINST_REQUIRED_ENTRY_CONTRACTS',
        'python_e2e': 'KEEP_BROWSER_E2E_REQUIRED_USE_NON_DJANGO_APP_IF_NEEDED',
    }, 'Django exception must not waive shared defects or browser E2E')
    need(plan['first_delivery'] == 'G1', 'first-delivery decision changed')
    diag = plan['diagnostics']
    need(diag['record_timing'] == 'before-first-helper-code', 'diagnostic decision must precede implementation')
    need(diag['decision_status'] in ('PROPOSED', 'APPROVED'), 'diagnostic decision missing')
    need(diag['selected_profile'] in ('readable-owned', 'basic-first'), 'unknown diagnostic profile')
    for row in rows:
        need(row['diagnostic_profile'] == diag['selected_profile'], 'entry/table diagnostic profile mismatch')
        need(row['fallback_allowed'] == (row['id'] in {'G1', 'EP1', 'EG1'}), 'unapproved fallback expansion')
    need(set(diag['core_failure_guarantees']) == {'original_error', 'cleanup_error', 'admission_state', 'cleanup_state'}, 'fallback weakens core guarantees')
    need(set(diag['fallback_requires']) == {'concrete_obstacle', 'user_effect', 'unfinished_fields', 'finite_exit'}, 'fallback rationale incomplete')
    need(diag['fallback_activation'] == 'NOT_SELECTED', 'fallback activation requires a new reviewed decision/contract')
    need(diag['selected_profile'] == 'readable-owned', 'fallback profile selected without its pre-implementation decision')
    delivery = plan['delivery_scope']
    need(delivery == {
        'decision_record': 'docs/decisions/p1-fixed-exit-v060.md',
        'v060_primary': 'WIRE_CONTRACT',
        'detailed_resources_milestone': 'v0.7.x',
        'detailed_resources_block_v060': False,
        'p1_exit': ['compatibility', 'preparation_and_isolation',
                    'failure_diagnostics_and_admission', 'owned_lifecycle_cleanup',
                    'supported_host_consumer_evidence', 'documentation_and_adoption_review'],
        'resource_parameters': 'PRESERVED_INPUTS_NOT_V060_ACCEPTANCE_GATES',
        'lifecycle_and_connection_budgets': 'REQUIRED',
    }, 'fixed P1 exit/resource placement changed without Human decision')
    need((root / delivery['decision_record']).is_file(), 'fixed exit decision missing')
    # Preserve diagnostic inputs, not a requirement to execute the v0.7.x campaign.
    res = plan['resources']
    need(res['max_forks_default'] > 0, 'unbounded child admission')
    need(res['test_child_limits'] == [1, 2] and res['cases_per_batch'] > 2, 'capacity waiting oracle missing')
    need(res['go_parallel'] == [1, 4] and res['go_packages'] == 1 and res['pytest_workers'] == [1, 2], 'worker/package multiplication not bounded')
    need(0 < res['preparation_pool_max_open'] <= res['child_pool_max_open'] < res['wire_sessions_unchanged'] == 16, 'connection budget invalid')
    need(0 <= res['child_pool_max_idle'] <= res['child_pool_max_open'], 'idle budget invalid')
    need(res['retained_baselines'] == [1, 2, 3], 'retained-baseline observation missing')
    for key in ['incremental_rss_ceiling_bytes', 'owned_disk_ceiling_bytes', 'min_free_disk_bytes', 'min_fd_headroom', 'observed_batches']:
        need(res[key] > 0, key + ' missing')
    need(set(res['time_outcomes']) == {'first_test_setup', 'second_test_edits', 'repeat_batch_elapsed'}, 'three-time observation incomplete')
    need(set(res['counter_requirements']) == {'process_tree_rss', 'available_memory', 'fd_baseline_peak_final', 'active_children', 'physical_connections', 'owned_temp_bytes', 'cleanup_state'}, 'resource counter coverage incomplete')
    fixture = res['retention_input']
    need(fixture['path'] == 'tests/fixture_entry_acceptance/retained_baselines.sql', 'unexpected retention input')
    raw = (root / fixture['path']).read_bytes()
    need(hashlib.sha256(raw).hexdigest() == fixture['sha256'], 'retention input changed')
    need(raw.count(b'CREATE TABLE ') == fixture['tables'] == 64, 'retention schema inventory differs')
    need(set(plan['capture_oracles']) == {'rejected_preserved', 'accepted_failure_consumed', 'success_consumed', 'invalid_but_not_disposed', 'partial_backing_unwind', 'original_plus_cleanup_error', 'exactly_once_backend_disposal'}, 'capture consumed/preserved oracle incomplete')
    e2e = plan['e2e']
    need(set(e2e['entries']) == {'EP1', 'EG1'}, 'E2E target missing')
    need(set(e2e['required_hooks']) == {'StartReady', 'QuiesceAndRetire', 'StopReap'}, 'required E2E hook missing')
    need(set(e2e['quiesce_obligations']) == {'stop_new_work', 'join_inflight', 'finish_transactions', 'retire_physical_connections', 'hold_until_admission'}, 'quiescence/retirement contract incomplete')
    need(e2e['on_setup_failure'] == 'NO_BODY_NO_IMPLICIT_RETRY' and e2e['one_case_per_owner'] is True, 'unsafe E2E admission')
    need(e2e['parallel_owners'] == 2 and e2e['transient_children_per_live'] == 2, 'E2E transient budget missing')
    wire = plan['wire']
    need(wire['current_inventory'] != wire['historical_inventory'], 'historical wire inventory used as current')
    need((root / wire['current_inventory']).is_file(), 'current wire inventory missing')
    need(set(wire['source_sha256']) == {'internal/mysqlwire/wire.go', 'internal/mysqlwire/prepared_session.go', 'guest/wire_core.inc', 'guest/resident.inc'}, 'wire source boundary missing')
    require_commit(root, wire['source_commit'])
    for path, digest in wire['source_sha256'].items():
        need(hashlib.sha256((root / path).read_bytes()).hexdigest() == digest, 'wire source drift requires inventory reconciliation: ' + path)
        pinned = subprocess.check_output(['git', 'show', wire['source_commit'] + ':' + path], cwd=root)
        need(hashlib.sha256(pinned).hexdigest() == digest, 'wire baseline is not the inspected source: ' + path)
    source = (root / 'internal/mysqlwire/wire.go').read_text()
    dispatch = source.split('switch request[0] {', 1)[1].split('\n\t\tif e != nil', 1)[0]
    commands = {int(n.strip()) for case in re.findall(r'case ([0-9, ]+):', dispatch) for n in case.split(',')}
    need(commands == set(wire['supported_commands']), 'wire dispatch inventory differs')
    caps = re.search(r'const capabilities uint32 = ([0-9 |]+)', source)[1]
    need({int(n.strip()) for n in caps.split('|')} == set(wire['base_capability_bits']), 'wire capability inventory differs')
    need(set(wire['ledger_fields']) == {'operation', 'client_options', 'observed_command_flags', 'native_result', 'guest_result', 'error', 'cleanup', 'source_client_pin', 'oracle'}, 'wire observation ledger incomplete')
    need(plan['future_runtime_status'] == 'NOT_RUN', 'design lint must not grant runtime PASS')
    need(plan['scope_status'] == 'APPROVED_G1_P1_WITH_DJANGO_NONBLOCKING'
         and plan['implementation_authorized'] is True
         and plan['authorized_implementation_entries'] == ['G1', 'P1'], 'implementation exceeds Human decision')
    need(diag['decision_status'] == 'APPROVED', 'diagnostic profile not approved')
    reviewed = plan['reviewed_design_commit']
    require_commit(root, reviewed)
    need(reviewed == '39f97573fe490ad86f37a4dbb25d762141d9114c', 'reviewed design identity changed')
    ancestor = subprocess.run(['git', 'merge-base', '--is-ancestor', reviewed, 'HEAD'], cwd=root)
    need(ancestor.returncode == 0, 'reviewed design must precede implementation')
    p1 = plan['p1_approval']
    need(p1['reviewed_design_commit'] == 'de860c4fc553907d237ad3a046ca6a6780ce0bb4'
         and p1['decision_commit'] == '746ea5fb6306bb122659917681a2554a6a292e77', 'P1 approval identity changed')
    for commit in (p1['reviewed_design_commit'], p1['decision_commit']):
        require_commit(root, commit)
        need(subprocess.run(['git', 'merge-base', '--is-ancestor', commit, 'HEAD'], cwd=root).returncode == 0,
             'P1 approval must precede implementation')
    need(p1['decision_record'] == 'docs/decisions/p1-prepared-entry-implementation.md', 'P1 decision record changed')
    pinned = subprocess.check_output(['git', 'show', p1['decision_commit'] + ':' + p1['decision_record']], cwd=root)
    need(hashlib.sha256(pinned).hexdigest() == p1['decision_record_sha256']
         == hashlib.sha256((root / p1['decision_record']).read_bytes()).hexdigest(), 'P1 decision record drift')
    need(p1['env_mode'] == 'PARENT_COPY_WITH_OVERLAY_AND_ACTUAL_RESERVED_TARGET'
         and p1['output_tail_bytes_per_stream'] == 16384
         and p1['output_truncation'] == 'FLAGS_AND_DROPPED_BYTE_COUNTS'
         and p1['unknown_prepare'] == 'USAGE_ERROR'
         and p1['cleanup_debt'] == 'STOP_DEPENDENT_ADMISSION_IN_SAME_WORKER'
         and p1['notice_paths'] == ['docs/python.md', 'docs/release-notes/unreleased.md'],
         'P1 conditional approval weakened')
    validate_p1_notices(root)
    return {'result': 'DESIGN_LINT_PASS', 'runtime': 'NOT_RUN', 'authorized_implementation_entries': ['G1', 'P1']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--contract', type=Path, default=CONTRACT)
    args = parser.parse_args()
    print(json.dumps(validate(json.loads(args.contract.read_text())), indent=2))


if __name__ == '__main__':
    main()
