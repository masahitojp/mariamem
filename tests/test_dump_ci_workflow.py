"""Trigger coverage and exact-checkout execution contracts for the dump CI owner."""
from pathlib import Path
import re
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'scripts'))
WORKFLOW = ROOT/'.github/workflows/dump-import-productization.yml'

def selected(path, pattern):
    # GitHub's * does not cross path separators; this workflow uses only * and **.
    expression = re.escape(pattern).replace(r'\*\*', 'DOUBLE_STAR').replace(r'\*', '[^/]*').replace('DOUBLE_STAR', '.*')
    return re.fullmatch(expression, path) is not None


def test_path_selection_does_not_treat_root_go_glob_as_all_runtime_files():
    assert selected('mariamem.go', '*.go')
    assert not selected('internal/guest/guest.go', '*.go')
    assert selected('internal/guest/guest.go', 'internal/**')



def validate(text):
    assert '  workflow_call:' in text
    assert not re.search(r'^  (push|pull_request|workflow_dispatch):', text, re.M)
    assert 'ref: ${{ inputs.source_commit }}' in text
    assert '--expected-source-commit "$SOURCE_COMMIT"' in text
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
    ('  workflow_call:', '  push:'), ('needs: native-reference', 'needs: []'),
    ('ref: ${{ inputs.source_commit }}', 'ref: main'),
    ('tests/dump_import_acceptance/campaign.py', 'echo omitted'),
    ('--expected-source-commit "$SOURCE_COMMIT"', '--unbound'),
])
def test_dump_regressions_are_detected(before, after):
    with pytest.raises(AssertionError): validate(WORKFLOW.read_text().replace(before, after))
