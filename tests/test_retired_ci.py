"""Historical experiments cannot accidentally trigger normal product CI."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def test_only_development_is_automatic_and_runtime_reuse_owner_remains():
    for path in (ROOT/'.github/workflows').glob('*.yml'):
        triggers = path.read_text().split('permissions:', 1)[0]
        assert not re.search(r'^  (push|schedule|workflow_run):', triggers, re.M), path
        if '  pull_request:' in triggers:
            assert path.name == 'check.yml'
    from runtime_validation import WORKFLOW
    assert WORKFLOW == '.github/workflows/v044-product-validation.yml'
    assert '  workflow_dispatch:' in (ROOT/WORKFLOW).read_text()
