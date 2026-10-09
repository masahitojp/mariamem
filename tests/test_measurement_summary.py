"""Current measurement reductions retain tails, resource scope and failed trials."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'benchmarks'))
from measurement_summary import distribution, summarize_resources
def sample(n):
    row = {'group_ready_seconds': .5, 'host_cpu_seconds': .1, 'runtime_cpu_seconds': .2,
           'combined_cpu_seconds': .3, 'incremental_primary_bytes': n*100,
           'average_incremental_bytes': 100, 'group_peak_primary_bytes': 50+n*100,
           'incremental_peak_primary_bytes': n*100}
    for state, value in [('baseline', 50), ('ready', 50+n*100), ('after_close', 55)]:
        row[state] = {'primary_bytes': value, 'rss_bytes': value+10, 'private_bytes': None}
    return {'kind': 'batch', 'workers': n, 'round': 0, 'phase': 'measurement',
            'status': 'pass', 'report': {'samples': [row]}}


def test_distribution_preserves_tail():
    assert distribution(list(range(1, 21))) == {
        'count': 20, 'min': 1, 'p50': 10.5, 'p95': 19.05, 'max': 20}


def test_resources_preserve_failure_and_unavailable_measurements():
    rows = [sample(n) for n in (1, 4, 8)]
    rows.append({'kind': 'batch', 'workers': 16, 'round': 0,
                 'phase': 'measurement', 'status': 'failed', 'report': None})
    result = summarize_resources(rows)
    assert result['groups'][3]['failures'] == 1
    assert result['groups'][3]['group_ready_seconds'] is None
    assert result['groups'][0]['ready_private_bytes'] is None
    assert result['groups'][0]['after_close_minus_baseline_bytes']['p50'] == 5
    assert result['marginal_memory'][2]['bytes_per_added_db'] is None
