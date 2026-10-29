"""The differential oracle preserves multiplicity, bytes and CTAS/DML effects."""
from copy import deepcopy
from text_dedup_acceptance import CASES, EXTRA_CASES, canonical, encoded, require_ordinary_budget, validate_reference
import pytest


def test_matrix_is_complete_and_unique():
    assert len(CASES) == 28
    assert len({case[0] for case in CASES}) == 28


@pytest.mark.parametrize('mutation', ['duplicate', 'blob', 'affected', 'materialized'])
def test_equality_oracle_rejects_real_result_changes(mutation):
    expected = {'rows': encoded(((b'a\x00b',), (b'z',), (b'z',))),
                'affected': 3, 'materialized': [['alice'], ['bob']]}
    actual = deepcopy(expected)
    actual['rows'].reverse()
    assert canonical(actual) == canonical(expected)
    if mutation == 'duplicate':
        actual['rows'].pop()
    elif mutation == 'blob':
        actual['rows'][2][0]['hex'] = '61'
    elif mutation == 'affected':
        actual['affected'] = 0
    else:
        actual['materialized'] = []
    assert canonical(actual) != canonical(expected)


def test_ordinary_matrix_is_separate_complete_and_unique():
    assert {case[0] for case in EXTRA_CASES} == {
        'temporary_filesort', 'alter_rename', 'text_view',
        'information_schema', 'transaction_rollback', 'lock_acquisition'}
    assert not {case[0] for case in CASES} & {case[0] for case in EXTRA_CASES}


def test_ordinary_ci_preserves_reference_and_enforces_per_host_budget():
    from pathlib import Path
    text = (Path(__file__).resolve().parents[1]/'.github/workflows/check.yml').read_text()
    for name, mode in [('Fresh native ordinary SQL reference', 'native'),
                       ('Ordinary SQL native/guest comparison', 'guest')]:
        block = text.split('- name: '+name, 1)[1].split('      - ', 1)[0]
        assert 'timeout-minutes: 1' in block
        assert 'tests/text_dedup_acceptance.py '+mode+' --suite ordinary' in block
        assert '--source-commit "$GITHUB_SHA"' in block
    worker = text.split('  worker-failure:\n', 1)[1]
    assert '    timeout-minutes: 60' in worker
    assert '--reference build/worker-failure/reference/ordinary-native.json' in text
    assert 'build/worker-failure/ordinary-guest.json' in text


@pytest.mark.parametrize('native,guest,valid', [
    (20, 40, True), (20, 40.01, False), (0, 0, True),
    (None, 2, False), (-1, 2, False), (float('nan'), 2, False), (True, 2, False),
])
def test_reference_and_guest_share_one_minute_budget(native, guest, valid):
    if valid:
        require_ordinary_budget(native, guest)
    else:
        with pytest.raises((ValueError, TimeoutError)):
            require_ordinary_budget(native, guest)


@pytest.mark.parametrize('mutation', ['source', 'suite', 'spec', 'missing_case', 'failed'])
def test_ordinary_reference_must_bind_source_suite_and_all_cases(mutation):
    ref = dict(source_commit='a'*40, result='PASS', suite='ordinary',
               case_spec_sha256='b'*64, cases=[{}]*6)
    validate_reference(ref, 'a'*40, 'ordinary', 'b'*64, 6)
    if mutation == 'source': ref['source_commit'] = 'c'*40
    elif mutation == 'suite': ref['suite'] = 'dedup'
    elif mutation == 'spec': ref['case_spec_sha256'] = 'd'*64
    elif mutation == 'missing_case': ref['cases'].pop()
    else: ref['result'] = 'FAIL'
    with pytest.raises(ValueError):
        validate_reference(ref, 'a'*40, 'ordinary', 'b'*64, 6)
