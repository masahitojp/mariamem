"""Current latency/resource reducers, independent of historical native CLIs.

Preserve partial failures and warmup boundaries supplied by the caller.
"""
from isolation_baseline import percentile


def distribution(values):
    return {'count': len(values), 'min': min(values), 'p50': percentile(values, .5),
            'p95': percentile(values, .95), 'max': max(values)}



def dist(values):
    return None if not values else {'count': len(values), 'p50': percentile(values, .5), 'p95': percentile(values, .95)}


def summarize_resources(trials):
    groups = []
    for n in (1, 4, 8, 16):
        rows = [t['report']['samples'][0] for t in trials
                if t['kind'] == 'batch' and t['workers'] == n and t['phase'] == 'measurement'
                and t['status'] == 'pass']
        result = {'workers': n, 'successes': len(rows), 'failures': sum(t['status'] == 'failed' for t in trials if t['kind'] == 'batch' and t['workers'] == n)}
        for key in ('group_ready_seconds', 'host_cpu_seconds', 'runtime_cpu_seconds', 'combined_cpu_seconds',
                    'incremental_primary_bytes', 'average_incremental_bytes', 'group_peak_primary_bytes', 'incremental_peak_primary_bytes'):
            result[key] = dist([r[key] for r in rows])
        result['combined_cpu_seconds_per_db'] = dist([r['combined_cpu_seconds']/n for r in rows])
        for state in ('baseline', 'ready', 'after_close'):
            for key in ('primary_bytes', 'rss_bytes', 'private_bytes'):
                result[state+'_'+key] = dist([r[state][key] for r in rows if r[state].get(key) is not None])
        result['after_close_minus_baseline_bytes'] = dist([r['after_close']['primary_bytes']-r['baseline']['primary_bytes'] for r in rows])
        groups.append(result)
    # Match round indices; separate processes/runs, not simultaneous marginals.
    index = {(t['workers'], t['round']): t['report']['samples'][0] for t in trials if t['kind']=='batch' and t['phase']=='measurement' and t['status']=='pass'}
    marginal = []
    for lo, hi in ((1, 4), (4, 8), (8, 16)):
        rounds = sorted(i for n,i in index if n==lo and (hi,i) in index)
        marginal.append({'from':lo,'to':hi,'bytes_per_added_db':dist([(index[hi,i]['incremental_primary_bytes']-index[lo,i]['incremental_primary_bytes'])/(hi-lo) for i in rounds])})
    return {'groups':groups,'marginal_memory':marginal}

