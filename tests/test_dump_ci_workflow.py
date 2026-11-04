"""Trigger coverage and exact-checkout execution contracts for the dump CI owner."""
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
WORKFLOW = ROOT/'.github/workflows/dump-import-productization.yml'

def validate(text):
    assert 'needs: native-reference' in text
    assert 'os: [ubuntu-24.04, macos-15]' in text
    assert 'scripts/verify.py' not in text
    for owner in ['producer.py', 'native_reference.py', 'variant.py', 'campaign.py']:
        assert 'tests/dump_import_acceptance/'+owner in text


def test_release_dump_retains_specific_oracles_and_candidate_identity():
    validate(WORKFLOW.read_text())
    for script in ['campaign.py', 'run.py']:
        source = (ROOT/'tests/dump_import_acceptance'/script).read_text()
        assert 'verify_go_binary(' in source and 'source_identity(' in source


@pytest.mark.parametrize('before,after', [
    ('needs: native-reference', 'needs: []'),
    ('tests/dump_import_acceptance/campaign.py', 'echo omitted'),
])
def test_dump_regressions_are_detected(before, after):
    with pytest.raises(AssertionError): validate(WORKFLOW.read_text().replace(before, after))
