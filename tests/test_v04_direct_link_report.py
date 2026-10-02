"""Canonical comparisons preserve boundaries, quantiles and slow observations."""
import importlib.util
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'benchmarks'))
spec = importlib.util.spec_from_file_location('direct_link_report', ROOT/'benchmarks/v04_direct_link_report.py')
report = importlib.util.module_from_spec(spec)
spec.loader.exec_module(report)


def test_classification_is_descriptive_and_quantile_specific():
    assert report.classify(100, 50) == 'improved'
    assert report.classify(100, 120) == 'regressed'
    assert report.classify(100, 95) == 'approximately unchanged'
    assert report.classify(100, 105) == 'approximately unchanged'
    assert report.classify(100, 106) == 'regressed'


def test_compaction_preserves_counter_inventory_without_pid_keys():
    value = {'pid': 123, 'members': {'123': {'cpu_seconds': 1, 'primary_bytes': 99},
                                  '456': {'cpu_seconds': 2, 'primary_bytes': 88}}}
    got = report.compact(value)
    assert 'pid' not in got
    assert len(got['members']) == 2
    assert sum(x['primary_bytes'] for x in got['members']) == 187


def test_orm_summary_keeps_slowest_suite():
    suites = []
    for n in (10, 50, 100):
        for mode in ('start', 'fork'):
            for seconds in (1, 2, 100):
                suites.append({'phase': 'measurement', 'tests': n, 'mode': mode,
                               'suite_seconds': seconds, 'setup_seconds': 0,
                               'samples': [{'ready_seconds': .1, 'workload_seconds': .01} for _ in range(n)]})
    got = report.orm_summary({'suites': suites})
    assert len(got) == 6
    assert all(x['suite']['count'] == 3 and x['suite']['max'] == 100 for x in got)
    assert all(x['suite']['p95'] > 90 for x in got)


def test_observations_preserve_slow_canonical_samples():
    samples = [{'case': name, 'latency_seconds': seconds} for name, seconds in
               [('start_first_sql', 1.2), ('start_seeded', 1.3), ('snapshot', 1.4), ('fork_first_sql', 1.5), ('select_1', .01)]]
    got = report.observations([{'round': 0, 'workers': 1, 'status': 'pass', 'report': {'samples': samples}}])
    assert len(got) == 1 and len(got[0]['samples']) == 4
    assert [x['latency_seconds'] for x in got[0]['samples']] == [1.2, 1.3, 1.4, 1.5]
