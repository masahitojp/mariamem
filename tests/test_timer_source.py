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
