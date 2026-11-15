#!/usr/bin/env python3
"""Validate the fixed campaign and recompute pair/diagnostic summaries."""
from collections import Counter
import json
from pathlib import Path
import statistics as st
import sys

CELLS = [(1, 2), (2, 4), (1, 1), (2, 2)]
METRICS = ['batch_drain_ms', 'workers_ms', 'drain_ms', 'batch_cpu_ms', 'process_wall_ms', 'process_cpu_ms', 'peak_rss_bytes']


def analyze(bundle):
    runs = bundle['runs']
    assert Counter(r['phase'] for r in runs) == {'measure': 40, 'warmup': 8, 'diagnostic': 8, 'smoke': 2, 'race': 2}
    for r in runs:
        assert r['children'] == 48 and r['rows'] == 1000
        assert r['exit_status'] == 0 and not r['failures']
        assert r['diagnostic'] == (r['phase'] == 'diagnostic')
        a, b = r['mappings_before'], r['mappings_after']
        for key in ['active_mappings', 'active_reserved_bytes', 'active_rw_bytes']:
            assert a[key] == b[key]
        assert b['creates']-a['creates'] == b['releases']-a['releases'] == 48
        assert b['release_failures'] == a['release_failures']
        assert b['grow_failures'] == a['grow_failures']
    summary, diagnostics = [], []
    for p, cap in CELLS:
        cell = [r for r in runs if (r['p'], r['cap']) == (p, cap)]
        for phase in ['warmup', 'diagnostic']:
            assert Counter(r['mode'] for r in cell if r['phase'] == phase) == {'sync': 1, 'stop': 1}
        pairs = []
        for i in range(5):
            selected = [r for r in cell if r['phase'] == 'measure' and r['pair'] == i]
            assert Counter(r['mode'] for r in selected) == {'sync': 1, 'stop': 1}
            a = {r['mode']: r for r in selected}
            pairs.append({'pair': i, 'batch_ms_delta': a['stop']['batch_drain_ms']-a['sync']['batch_drain_ms'], 'pct': {k: (a['stop'][k]/a['sync'][k]-1)*100 for k in METRICS}})
        summary.append({'p': p, 'cap': cap, 'pairs': pairs,
            'paired_median_pct': {k: st.median(x['pct'][k] for x in pairs) for k in METRICS},
            'paired_median_batch_delta_ms': st.median(x['batch_ms_delta'] for x in pairs),
            'faster_pairs': sum(x['pct']['batch_drain_ms'] < 0 for x in pairs),
            'batch_pct_range': [min(x['pct']['batch_drain_ms'] for x in pairs), max(x['pct']['batch_drain_ms'] for x in pairs)],
            'arm_medians': {mode: {k: st.median(r[k] for r in cell if r['phase'] == 'measure' and r['mode'] == mode) for k in METRICS} for mode in ['sync', 'stop']}})
        for r in cell:
            if r['phase'] != 'diagnostic':
                continue
            events = r['events']
            by = {}
            for e in events:
                assert e['pending_cleanup'] >= 0
                by.setdefault(e['id'], {})[e['kind']] = e
            assert set(by) == set(range(48))
            assert len(events) == 48*7
            for d in by.values():
                assert set(d) == {'fork_request', 'fork_admitted', 'fork_ready', 'close_begin', 'stopped', 'backend_cleanup_end', 'close_return'}
                assert d['fork_request']['ns'] <= d['fork_admitted']['ns'] <= d['fork_ready']['ns'] <= d['close_begin']['ns'] <= d['stopped']['ns']
                assert d['stopped']['ns'] <= d['backend_cleanup_end']['ns']
                assert d['stopped']['ns'] <= d['close_return']['ns']
            closes = [(d['close_return']['ns']-d['close_begin']['ns'])/1e6 for d in by.values()]
            remaining = [(d['backend_cleanup_end']['ns']-d['stopped']['ns'])/1e6 for d in by.values()]
            overlap, admissions = 0, 0
            for worker in range(p):
                sequence = sorted((d for d in by.values() if d['fork_admitted']['worker'] == worker), key=lambda d: d['fork_admitted']['ns'])
                for previous, current in zip(sequence, sequence[1:]):
                    admissions += 1
                    overlap += current['fork_admitted']['ns'] < previous['backend_cleanup_end']['ns']
            if r['mode'] == 'sync' or (p, cap) == (1, 1):
                assert overlap == 0
            assert admissions == 48-p
            assert events[-1]['pending_cleanup'] == 0
            assert r['max_pending_backend_cleanup'] <= cap
            diagnostics.append({'p': p, 'cap': cap, 'mode': r['mode'], 'batch_drain_ms': r['batch_drain_ms'], 'close_p50_ms': st.median(closes), 'close_max_ms': max(closes), 'backend_cleanup_span_max_ms': max((d['backend_cleanup_end']['ns']-d['close_begin']['ns'])/1e6 for d in by.values()), 'close_p95_nearest_rank_ms': sorted(closes)[45], 'after_stop_p50_ms': st.median(remaining), 'after_stop_max_ms': max(remaining), 'early_returns': sum(d['close_return']['ns'] < d['backend_cleanup_end']['ns'] for d in by.values()), 'same_worker_next_admission_overlaps': overlap, 'next_admissions': admissions, 'max_pending_backend_cleanup': r['max_pending_backend_cleanup'], 'max_sampled_active_mappings': r['max_sampled_active_mappings'], 'peak_logical_rw_bytes_process': r['mappings_after']['peak_total_rw_bytes']})
    return {'counts': dict(Counter(r['phase'] for r in runs)), 'failures': 0, 'measurement_children': 40*48, 'all_phase_children': len(runs)*48, 'summary': summary, 'diagnostics': diagnostics}


if __name__ == '__main__':
    print(json.dumps(analyze(json.loads(Path(sys.argv[1]).read_text())), indent=2))
