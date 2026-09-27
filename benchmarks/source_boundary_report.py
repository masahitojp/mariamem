"""Fail-closed source-boundary evidence; staging/verification are never free."""
import statistics
from isolation_baseline import percentile
from restore_report import summarize as restore_summary, validate


def inventory(probe, prefix):
    return {f['path'].removeprefix(prefix): f['size_bytes'] for f in probe['files']}


def summarize(pairs):
    result = {}
    for condition, source in (('control', 'host'), ('reuse', 'guest')):
        reports = [p[condition] for p in pairs]
        result[condition] = restore_summary(reports)
        extra = {}
        for report in reports:
            for row in report['samples']:
                if row['case'] != 'fork_first_sql' or row['phase'] != 'measurement':
                    continue
                for db in row['per_db']:
                    g = db['stage_timings']['host']['guest']
                    if g.get('restore_source') != source or g.get('restore_identity_verified') is not True:
                        raise ValueError('missing exact source/destination content verification')
                    v = g['restore_verification']
                    if v['invalid_clock']:
                        raise ValueError('invalid content verification clock')
                    records = {'verification': v}
                    if condition == 'reuse':
                        pre = g['restore_prestage']; validate(pre)
                        if inventory(pre, '/snapshot-in/data/') != inventory(g['restore_copy'], '/restore-source/'):
                            raise ValueError('pre-stage inventory mismatch')
                        records['pre-stage'] = pre
                    for name, value in records.items():
                        for metric in ('wall_ns', 'process_cpu_ns', 'thread_cpu_ns'):
                            extra.setdefault((row['workers'], name, metric), []).append(value[metric])
                        if name == 'pre-stage':
                            extra.setdefault((row['workers'], name, 'bytes'), []).append(value['stages']['read']['bytes'])
        result[condition] += [{'workers': w, 'component': c, 'metric': m, 'count': len(v), 'raw': v,
                              'p50': statistics.median(v), 'p95': percentile(v, .95)}
                             for (w,c,m),v in sorted(extra.items())]
    return result
