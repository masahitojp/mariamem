"""Deterministic accounting tests; no database, runtime or sampler subprocess."""
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "benchmarks"))
import isolation_baseline as baseline


@pytest.mark.parametrize("clock,expected", [
    ("00:00.25", .25),
    ("02:03.50", 123.5),
    ("01:02:03", 3723),
    ("2-01:02:03.25", 176523.25),
])
def test_ps_cpu_time_forms(clock, expected):
    assert baseline.cpu_seconds(clock) == pytest.approx(expected)


def test_descendants_exclude_parent_sampler_and_unrelated_processes():
    # Deliberately place descendants before their parents to require traversal.
    table = """12 11 30 00:00.50
10 1 100 00:03
11 10 20 00:01
20 1 900 00:20
14 13 700 00:10
13 10 800 00:11
"""
    assert baseline.descendant_values(table, parent=10, excluded=13) == {
        "11": {"rss_bytes": 20 * 1024, "cpu_seconds": 1},
        "12": {"rss_bytes": 30 * 1024, "cpu_seconds": .5},
    }
    assert baseline.descendant_values("", parent=10, excluded=13) == {}


@pytest.mark.parametrize("values,fraction,expected", [
    ([4, 1, 3, 2], .5, 2.5),
    ([4, 1, 3, 2], .95, 3.85),
    ([8], .95, 8),
])
def test_interpolated_percentiles(values, fraction, expected):
    assert baseline.percentile(values, fraction) == pytest.approx(expected)


def test_summary_excludes_warmup_and_preserves_case_worker_boundaries():
    rows = [
        {"case": "fork_first_sql", "workers": 4, "phase": phase,
         "latency_seconds": elapsed}
        for phase, elapsed in [("warmup", 999), ("measurement", 1), ("measurement", 3)]
    ]
    rows.append({"case": "start_first_sql", "workers": 1, "phase": "measurement",
                 "latency_seconds": 10})
    summaries = baseline.summarize(rows)
    expected = [
        {"case": "fork_first_sql", "workers": 4, "count": 2,
         "p50_seconds": 2, "p95_seconds": 2.9},
        {"case": "start_first_sql", "workers": 1, "count": 1,
         "p50_seconds": 10, "p95_seconds": 10},
    ]
    assert len(summaries) == len(expected)
    for summary, fields in zip(summaries, expected):
        assert {key: summary[key] for key in fields} == fields
    assert baseline.summarize(rows[:1]) == []


def sampler(samples, previous=None):
    monitor = object.__new__(baseline.CostSampler)
    monitor.interval = .05
    monitor.samples = samples
    monitor.errors = []
    monitor.baseline = {"rss_bytes": 0, "members": previous or {}}
    return monitor


def test_parallel_summary_preserves_individual_latency_distribution():
    summary = baseline.summarize([
        {"case": "fork_first_sql", "workers": 4, "phase": "warmup",
         "latency_seconds": 999, "per_db": [{"latency_seconds": 999}]},
        {"case": "fork_first_sql", "workers": 4, "phase": "measurement",
         "latency_seconds": 4, "per_db": [{"latency_seconds": value} for value in [1, 2, 3, 4]]},
    ])[0]
    assert summary["p50_seconds"] == 4
    assert summary["per_db_p50_seconds"] == 2.5
    assert summary["per_db_p95_seconds"] == pytest.approx(3.85)


@pytest.mark.parametrize("samples", [[], [
    {"at_seconds": 1, "rss_bytes": 0, "members": {}}
]])
def test_cpu_is_unavailable_without_process_observations(samples):
    result = sampler(samples).result(1)
    assert result["sampled_descendant_cpu_seconds"] is None
    if not samples:
        assert result["sampled_peak_rss_bytes"] is None
        assert result["nearest_ready_sample"] is None


def test_cpu_retains_exited_process_observations_and_subtracts_baseline():
    samples = [
        {"at_seconds": .1, "rss_bytes": 30, "members": {
            "1": {"cpu_seconds": 3}, "2": {"cpu_seconds": .5}}},
        {"at_seconds": .2, "rss_bytes": 20, "members": {
            "1": {"cpu_seconds": 4}}},
    ]
    result = sampler(samples, {"1": {"cpu_seconds": 2}}).result(.19)
    assert result["sampled_descendant_cpu_seconds"] == 2.5
    assert result["sampled_peak_rss_bytes"] == 30
    assert result["nearest_ready_sample"] is samples[1]


def test_stage_summary_separates_nested_scopes_and_worker_counts():
    trace = {'caller': [{'name': 'begin', 'offset_ns': 0}, {'name': 'first_sql', 'offset_ns': 2000000000}],
             'host': {'events': [{'name': 'begin', 'offset_ns': 0}, {'name': 'guest_ready', 'offset_ns': 1000000000}]}}
    rows = [{'phase': 'measurement', 'case': 'fork_first_sql', 'workers': 4,
             'per_db': [{'stage_timings': trace}]},
            {'phase': 'warmup', 'case': 'fork_first_sql', 'workers': 4, 'per_db': [{'stage_timings': trace}]}]
    summary = baseline.summarize_stages(rows)
    assert len(summary) == 2
    assert {r['scope']: r['p50_seconds'] for r in summary} == {'caller': 2, 'host': 1}
    assert all(r['count'] == 1 and r['workers'] == 4 for r in summary)


def test_stage_trace_is_explicit_and_requires_structured_host_record(tmp_path, monkeypatch):
    from types import SimpleNamespace
    import json
    db = SimpleNamespace(database=SimpleNamespace(diagnostics={'host_pid': 123}, _startup_timing=[]), timing_events=[])
    monkeypatch.delenv('MARIAMEM_TIMING_DIR', raising=False)
    assert baseline.stage_timings(db) is None
    monkeypatch.setenv('MARIAMEM_TIMING_DIR', str(tmp_path))
    with pytest.raises(RuntimeError, match='instrumented host'):
        baseline.stage_timings(db)
    (tmp_path / '123-startup-1.json').write_text(json.dumps({'pid': 123, 'operation': 'startup', 'events': []}))
    assert baseline.stage_timings(db)['host']['pid'] == 123
