"""Reject altered native oracles; actual database execution belongs to CI."""
import copy
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('p1_native_control', ROOT/'tests/fixture_entry_acceptance/native.py')
native = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native)


def observation():
    return dict(version='12.3.3-MariaDB-ubu2404',
                users=[[1,'legacy',0],[2,'seed',5]], addresses=[[1,2,'seed@example.test']],
                revision=[['m2_addresses']],
                columns=[['addresses','id','int','NO'],['addresses','user_id','int','NO'],
                         ['addresses','email','varchar','NO'],['users','id','int','NO'],
                         ['users','name','varchar','NO'],['users','rating','int','NO']],
                constraints=[['addresses','FOREIGN KEY'],['addresses','PRIMARY KEY'],
                             ['addresses','UNIQUE'],['users','PRIMARY KEY'],['users','UNIQUE']],
                tables=[[name,'InnoDB','utf8mb4_uca1400_ai_ci'] for name in ['addresses','alembic_version','users']],
                foreign_key_errno=1452, subsequent_select=1,
                distinct_physical_connections=2, pool_checkedout_after=0)


@pytest.mark.parametrize('key,bad', [
    ('version','12.3.2-MariaDB'), ('users',[[1,'legacy',0]]), ('addresses',[]),
    ('revision',[['m1_initial']]), ('columns',[]), ('constraints',[]),
    ('tables',[['users','MyISAM','utf8mb4_general_ci']]),
    ('foreign_key_errno',1146), ('subsequent_select',None),
    ('distinct_physical_connections',1), ('pool_checkedout_after',1),
])
def test_reference_cannot_accept_wrong_data_or_recovery(key,bad):
    original = observation()
    native.validate(original)
    altered = copy.deepcopy(original)
    altered[key] = bad
    with pytest.raises(AssertionError):
        native.validate(altered)


def test_both_native_python_cells_execute_p1_after_acquisition():
    workflow = (ROOT/'.github/workflows/live-host.yml').read_text()
    section = workflow.split('  native-reference:',1)[1].split('  live:',1)[0]
    assert "python: ['3.11', '3.14']" in section
    assert section.index('linux_acquisition.py') < section.index('tests/fixture_entry_acceptance/native.py')
    assert '--acquisition build/live-native/acquisition' in section
    assert '--expected-source-commit "$GITHUB_SHA"' in section
    assert '--disposable-server' in section
    assert '-r tests/preparation_migration_acceptance/requirements.txt' in section
    assert 'P1_NATIVE_REFERENCE="$PWD/build/reference/py$version/p1"' in workflow


@pytest.mark.parametrize('mutation', ['source', 'python', 'cleanup', 'missing_callback', 'input', 'failed'])
def test_guest_reference_admission_rejects_stale_or_incomplete_receipt(mutation):
    import hashlib
    receipt = dict(result='PASS_P1_NATIVE_INPUT', source_commit='a'*40, python='3.11.17',
                   schema_count_after=0, runs=dict(command=observation(),callback=observation()),
                   inputs_sha256={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in native.INPUTS})
    native.validate_reference(receipt, 'a'*40, '3.11')
    if mutation == 'source': receipt['source_commit'] = 'b'*40
    elif mutation == 'python': receipt['python'] = '3.14.9'
    elif mutation == 'cleanup': receipt['schema_count_after'] = 1
    elif mutation == 'missing_callback': del receipt['runs']['callback']
    elif mutation == 'input': receipt['inputs_sha256'][native.INPUTS[0]] = '0'*64
    else: receipt['result'] = 'FAIL'
    with pytest.raises(AssertionError):
        native.validate_reference(receipt, 'a'*40, '3.11')
