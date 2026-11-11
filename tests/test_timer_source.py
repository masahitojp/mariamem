"""Normal offline check owns SQL selection and calibration regression controls."""
import json
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('name,result,cases,mutations', [
    ('selection', 'SELECTION_UNIT_PASS', 6, 2),
    ('calibration', 'INITIALIZER_UNIT_PASS', 10, 4),
])
def test_canonical_timer_source(tmp_path, name, result, cases, mutations):
    output = tmp_path / 'result.json'
    subprocess.run([sys.executable, ROOT / 'tests/timer_source' / (name + '.py'),
                    '--work', tmp_path / 'work', '--output', output],
                   cwd=ROOT, check=True, timeout=90)
    record = json.loads(output.read_text())
    assert record['result'] == result
    assert len(record['cases']) == cases
    assert len(record['negative_controls']) == mutations


def test_product_candidate_requires_canonical_and_platform_timer_checks():
    workflow = (ROOT / '.github/workflows/timer-product.yml').read_text()
    for required in ['scripts/build_generated_guest.py --repetitions 2',
                     'test ! -e guest/experimental.patch',
                     'runner: [macos-15, ubuntu-24.04]',
                     'scripts/regenerate_release_guest.py',
                     'scripts/check_prepared_build_guards.py',
                     'tests/test_timer_source.py',
                     "-run '^TestAnalyzeTimerFreshAndFork$'",
                     'tests/routine_thread_fixture.py',
                     'tests/lexer_prepared_acceptance.py']:
        assert required in workflow
    assert '  push:' not in workflow
    assert '  workflow_dispatch:' in workflow
    assert 'continue-on-error' not in workflow
    assert 'operation: release' not in workflow
