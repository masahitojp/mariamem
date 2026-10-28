"""The differential oracle preserves multiplicity, bytes and CTAS/DML effects."""
from copy import deepcopy
from text_dedup_acceptance import CASES, canonical, encoded
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
