from pathlib import Path
import sys
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from live_selection import FAMILIES, select

def plan(paths, event='pull_request', reason='unknown/runtime input'):
    return select(paths, event, reason)

@pytest.mark.parametrize('path', ['guest/source.patch', 'go.mod', 'python/mariamem/__init__.py',
    'internal/guest/guest.go', '.github/workflows/live-host.yml', 'scripts/live_selection.py',
    'unknown/new.py', 'mariamemtest/new_api.go', 'python/mariamem/new_api.py'])
def test_unknown_shared_and_policy_inputs_run_everything(path):
    assert all(plan([path]).values())

@pytest.mark.parametrize('event', ['push', 'workflow_dispatch'])
def test_non_pr_always_full(event):
    assert all(plan(['mariamemtest/fixture.go'], event).values())

def test_unavailable_diff_is_full():
    assert all(plan([]).values())
    assert all(plan(['live.go'], reason='event diff unavailable').values())

def test_g1_keeps_both_host_receipts_without_generic_integration():
    assert {k for k, v in plan(['mariamemtest/fixture.go']).items() if v} == {'g1', 'installed'}

def test_live_keeps_mutations_race_examples_and_installed():
    assert {k for k, v in plan(['live.go']).items() if v} == {'live_runtime', 'examples', 'installed'}

def test_combined_changes_union_and_unknown_overrides():
    result = plan(['live.go', 'mariamemtest/fixture.go'])
    assert result['g1'] and result['live_runtime'] and not result['mac_integration']
    assert all(plan(['live.go', 'guest/source.patch']).values())

def test_python_retains_integration_until_dedicated_campaign_is_adopted():
    assert plan(['python/mariamem/pytest_plugin.py'])['mac_integration']
    assert not plan(['python/mariamem/pytest_plugin.py'])['g1']
    assert plan(['python/mariamem/pytest_plugin.py'])['p1']


@pytest.mark.parametrize('path', [
    'python/mariamem/_prepare.py', 'python/mariamem/_pytest_owner.py',
    'tests/test_prepare_command.py', 'tests/test_p1_pytest_entry.py',
    'tests/test_p1_runtime.py', 'tests/test_p1_native_control.py',
    'tests/fixture_entry_acceptance/native.py',
    'tests/fixture_entry_acceptance/p1_migrate.py',
    'tests/fixture_entry_acceptance/time_campaign.py',
])
def test_p1_specific_inputs_select_its_consumers(path):
    assert {k for k, v in plan([path]).items() if v} == {'p1', 'installed'}


@pytest.mark.parametrize('path', [
    'python/mariamem/routing.py', 'python/mariamem/_routing_drivers.py',
    'python/mariamem/_routing_sqlalchemy.py', 'tests/routing_acceptance/unit-requirements.txt',
    'tests/fixture_entry_acceptance/retained_baselines.sql',
])
def test_p1_shared_dependencies_keep_acceptance(path):
    assert plan([path])['p1']


@pytest.mark.parametrize('path', ['live.go', 'mariamemtest/fixture.go'])
def test_unrelated_live_or_go_helper_does_not_pay_for_p1_wheel(path):
    assert not plan([path])['p1']


def test_mixed_p1_and_live_diff_unions_both_families():
    result = plan(['python/mariamem/_prepare.py', 'live.go'])
    assert result['p1'] and result['live_runtime'] and result['installed']


def test_native_and_installed_p1_steps_share_the_selection():
    text = (Path(__file__).resolve().parents[1]/'.github/workflows/live-host.yml').read_text()
    for name in ['Fresh P1 authored command and callback native control',
                 'P1 real prepared command and callback on both Python minors']:
        step = text.split('- name: ' + name, 1)[1].split('- name:', 1)[0]
        assert "if: needs.scope.outputs.p1 == 'true'" in step

def test_gate_rejects_missing_selection():
    from live_ci import verify_gate
    needs = {'scope': {'result': 'success', 'outputs': {'run_live': 'true', 'pull_request_draft': 'false'}},
             'native-reference': {'result': 'success'}, 'live': {'result': 'success'}}
    with pytest.raises(AssertionError, match='family'):
        verify_gate(needs)

def test_selected_g1_upload_download_and_validator_share_condition():
    text = (Path(__file__).resolve().parents[1]/'.github/workflows/live-host.yml').read_text()
    assert "if: always() && needs.scope.outputs.g1 == 'true'" in text
    assert text.count("if: needs.scope.outputs.run_live == 'true' && needs.scope.outputs.g1 == 'true'") == 2
    for key in FAMILIES:
        assert key + ': ${{ steps.scope.outputs.' + key + ' }}' in text
