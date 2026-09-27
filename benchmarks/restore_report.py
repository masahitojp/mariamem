"""Bounded restore-copy attribution; logical stdio activity, not physical disk I/O."""
import statistics
from isolation_baseline import percentile


def validate(probe):
    if probe['version'] != 1 or probe['invalid_clock'] or probe['dropped_files']:
        raise ValueError('incomplete restore clock/file evidence')
    if probe['file_count'] != len(probe['files']):
        raise ValueError('restore file inventory mismatch')
    for stage in probe['stages'].values():
        if stage['invalid_clock']:
            raise ValueError('invalid restore stage clock')
    for file in probe['files']:
        if any(stage['invalid_clock'] for stage in file['stages'].values()):
            raise ValueError('invalid per-file restore clock')
    expected = sum(f['size_bytes'] for f in probe['files'])
    for stage in ('read', 'write'):
        if probe['stages'][stage]['bytes'] != expected:
            raise ValueError('restore byte count mismatch')
        if sum(f['stages'][stage]['bytes'] for f in probe['files']) != expected:
            raise ValueError('per-file restore bytes mismatch')
    if sum(s['wall_ns'] for s in probe['stages'].values()) > probe['wall_ns']:
        raise ValueError('restore scopes do not reconcile')


def summarize(reports):
    groups = {}
    def add(workers, component, metric, value):
        groups.setdefault((workers, component, metric), []).append(value)
    for report in reports:
        for row in report['samples']:
            if row['case'] != 'fork_first_sql' or row['phase'] != 'measurement':
                continue
            for db in row['per_db']:
                probe = db['stage_timings']['host']['guest']['restore_copy']
                validate(probe)
                workers = row['workers']
                for metric in ('wall_ns', 'process_cpu_ns', 'thread_cpu_ns', 'file_count', 'directories'):
                    add(workers, 'total', metric, probe[metric])
                residual = probe['wall_ns']-sum(s['wall_ns'] for s in probe['stages'].values())
                add(workers, 'outside timed operations', 'wall_ns', residual)
                for name, stage in probe['stages'].items():
                    for metric in ('wall_ns', 'process_cpu_ns', 'thread_cpu_ns', 'bytes', 'calls'):
                        add(workers, name, metric, stage[metric])
                for f in probe['files']:
                    path = f['path'].removeprefix('/snapshot-in/data/')
                    add(workers, 'file:'+path, 'wall_ns', f['wall_ns'])
                    add(workers, 'file:'+path, 'size_bytes', f['size_bytes'])
                    for name, stage in f['stages'].items():
                        for metric in ('wall_ns', 'process_cpu_ns', 'thread_cpu_ns', 'bytes', 'calls'):
                            add(workers, 'file:'+path+':'+name, metric, stage[metric])
    if not groups:
        raise ValueError('missing measured restore evidence')
    return [{'workers': w, 'component': c, 'metric': m, 'count': len(v),
             'raw': v, 'p50': statistics.median(v), 'p95': percentile(v, .95)}
            for (w, c, m), v in sorted(groups.items())]
