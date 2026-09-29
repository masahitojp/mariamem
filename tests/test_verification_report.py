import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'benchmarks'))
from verification_report import render


def sample(wall, cpu, files=3):
    return {'case': 'native_hashes', 'workers': 2, 'phase': 'measurement',
            'latency_seconds': wall, 'cpu_seconds': cpu, 'files_hashed': files,
            'content_bytes_hashed': 1024**2, 'heap_total_allocated_bytes': 1024}


def test_summary_keeps_slow_trials_and_distinguishes_wall_from_cpu():
    report = {'completed': True, 'samples': [sample(.01, .02), sample(.1, .2)]}
    result = render(report)
    assert '55.000/95.500' in result and '110.000/191.000' in result
    assert 'not parallel full validators' in result


def test_incomplete_or_inconsistent_work_cannot_be_a_comparison():
    with pytest.raises(ValueError):
        render({'completed': False})
    with pytest.raises(AssertionError):
        render({'completed': True, 'samples': [sample(.1, .2), sample(.1, .2, files=2)]})
