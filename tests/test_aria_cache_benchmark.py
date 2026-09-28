"""Metric correctness and unavailable counters must not become apparent savings."""
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'benchmarks'))
import aria_cache_ab as ab


def rows():
    result = []
    for n in (1, 4, 8):
        for mode in ('128', '16'):
            incremental = n * (100 if mode == '128' else 30)
            result.append({'case': 'fork', 'phase': 'measurement', 'round': 0, 'condition': mode, 'workers': n,
                           'per_db': [{'latency_seconds': .5} for _ in range(n)], 'group_ready_seconds': .6,
                           'host_cpu_seconds': .1*n, 'runtime_cpu_seconds': .2*n, 'combined_cpu_seconds': .3*n,
                           'incremental_primary_bytes': incremental, 'average_incremental_bytes': incremental/n,
                           'group_peak_primary_bytes': 1000+incremental, 'incremental_peak_primary_bytes': incremental,
                           'baseline': {'primary_bytes': 1000, 'rss_bytes': 2000, 'private_bytes': None},
                           'ready': {'primary_bytes': 1000+incremental, 'rss_bytes': 3000, 'private_bytes': None},
                           'after_close': {'primary_bytes': 1000, 'rss_bytes': 2000, 'private_bytes': None}})
    return result


def test_incremental_marginal_and_cpu_scopes():
    report = ab.summarize(rows(), 1)
    assert report['paired_differences'][0]['control_minus_experiment']['average_incremental_bytes']['p50'] == 70
    assert report['marginal_memory'][0]['marginal_bytes_per_db']['p50'] == 100
    assert report['cpu_amplification'][0]['x8_cpu_amplification']['p50'] == pytest.approx(1)
    assert report['summary'][0]['combined_cpu_seconds_per_db']['p50'] == pytest.approx(.3)
    assert report['summary'][0]['ready_private_bytes'] is None


def test_missing_or_duplicate_pairs_fail():
    with pytest.raises(ValueError, match='missing balanced'):
        ab.summarize(rows()[:-1], 1)
    with pytest.raises(ValueError, match='duplicate'):
        ab.summarize(rows()+rows()[:1], 1)


def test_unavailable_metrics_are_not_zero_savings():
    with pytest.raises(ValueError, match='missing/nonfinite'):
        ab.distribution([])
    with pytest.raises(ValueError, match='missing/nonfinite'):
        ab.distribution([float('nan')])
