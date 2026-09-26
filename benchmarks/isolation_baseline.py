#!/usr/bin/env python3
"""0.2 baseline: real packaged MariaDB isolation, cost and SQL regression indicators."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
import hashlib
import math
import os
from pathlib import Path
import statistics
import subprocess
import threading
import tempfile
import time

from _common import ROOT, RESULTS, environment, positive, instance, probe, stage_timings
from parallel_databases import batch


def cpu_seconds(value):
    days, _, clock = value.rpartition('-')
    fields = list(map(float, clock.split(':')))
    return (int(days) * 86400 if days else 0) + sum(v * 60 ** i for i, v in enumerate(reversed(fields)))


def descendant_values(stdout, parent, excluded):
    entries = [(int(pid), int(ppid), int(rss) * 1024, cpu_seconds(cpu))
               for pid, ppid, rss, cpu in (line.split() for line in stdout.splitlines() if line.strip())]
    selected = {parent}
    while True:
        children = {pid for pid, ppid, _, _ in entries if ppid in selected and pid != excluded}
        if children <= selected:
            break
        selected.update(children)
    return {str(pid): {'rss_bytes': rss, 'cpu_seconds': cpu}
            for pid, _, rss, cpu in entries if pid in selected and pid not in {parent, excluded}}


class CostSampler:
    """Sample ps on macOS/Ubuntu; retain observations, never claim exact peak/CPU."""
    label = None

    def __init__(self, interval):
        self.interval = interval
        self.samples = []
        self.errors = []
        self.done = threading.Event()
        self.thread = None
        self.baseline = self.read()

    def read(self):
        begin = time.perf_counter()
        with subprocess.Popen(['ps', '-axo', 'pid=,ppid=,rss=,time='], stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, text=True) as proc:
            try:
                stdout, stderr = proc.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.communicate()
                raise
            if proc.returncode:
                raise RuntimeError(stderr)
            members = descendant_values(stdout, os.getpid(), proc.pid)
        return {'rss_bytes': sum(v['rss_bytes'] for v in members.values()), 'members': members,
                'collection_seconds': time.perf_counter() - begin}

    def start(self, started):
        def collect():
            while not self.done.is_set():
                try:
                    row = self.read()
                    row['at_seconds'] = time.perf_counter() - started
                    self.samples.append(row)
                except Exception as exc:
                    self.errors.append(str(exc))
                    break
                self.done.wait(self.interval)
        self.thread = threading.Thread(target=collect, daemon=True)
        self.thread.start()

    def stop(self):
        self.done.set()
        if self.thread:
            self.thread.join()

    def result(self, ready_seconds):
        observed = {}
        for sample in self.samples:
            for pid, value in sample['members'].items():
                observed[pid] = max(observed.get(pid, 0), value['cpu_seconds'])
        cpu = sum(max(0, value - self.baseline['members'].get(pid, {}).get('cpu_seconds', 0))
                  for pid, value in observed.items()) if observed else None
        nearest = min(self.samples, key=lambda row: abs(row['at_seconds'] - ready_seconds)) if self.samples else None
        return {'mechanism': 'ps descendant RSS and cumulative CPU; excludes Python parent and sampling ps',
                'requested_interval_seconds': self.interval, 'baseline': self.baseline,
                'sampled_peak_rss_bytes': max((s['rss_bytes'] for s in self.samples), default=None),
                'nearest_ready_sample': nearest, 'sampled_descendant_cpu_seconds': cpu,
                'samples': self.samples, 'errors': self.errors}


def measured(action, interval):
    monitor = CostSampler(interval)
    cpu = time.process_time()
    started = time.perf_counter()
    monitor.start(started)
    try:
        value = action()
        elapsed = time.perf_counter() - started
    finally:
        monitor.stop()
    return {'wall_seconds': elapsed, 'python_cpu_seconds': time.process_time() - cpu,
            'cost': monitor.result(elapsed), **value}


def percentile(values, fraction):
    values = sorted(values)
    index = (len(values) - 1) * fraction
    low, high = math.floor(index), math.ceil(index)
    return values[low] + (values[high] - values[low]) * (index - low)


def summarize(samples):
    result = []
    keys = sorted({(s['case'], s['workers']) for s in samples if s['phase'] == 'measurement'})
    for case, workers in keys:
        rows = [s for s in samples if s['phase'] == 'measurement' and (s['case'], s['workers']) == (case, workers)]
        times = [s['latency_seconds'] for s in rows]
        per_db = [db['latency_seconds'] for row in rows for db in row.get('per_db', [])]
        result.append({'per_db_p50_seconds': statistics.median(per_db) if per_db else None,
                       'per_db_p95_seconds': percentile(per_db, .95) if per_db else None,
                       'case': case, 'workers': workers, 'count': len(times),
                       'p50_seconds': statistics.median(times), 'p95_seconds': percentile(times, .95)})
    return result


def summarize_stages(samples):
    grouped = {}
    for row in samples:
        if row['phase'] != 'measurement':
            continue
        traces = [d.get('stage_timings') for d in row.get('per_db', [])] or [row.get('stage_timings')]
        for trace in traces:
            if not trace:
                continue
            scopes = {'caller': trace.get('caller', [])} if row['case'] != 'snapshot' else {}
            if row['case'] != 'snapshot':
                scopes['python_startup'] = trace.get('python_startup') or []
            scopes['host'] = trace.get('host', {}).get('events', [])
            if row['case'] != 'snapshot':
                scopes['guest'] = trace.get('host', {}).get('guest', {}).get('events', [])
            if scopes.get('guest'):
                host = {event['name']: event['offset_ns'] for event in scopes['host']}
                guest = scopes['guest']
                if 'spawn_returned' in host and 'guest_ready' in host:
                    # A duration residual, not absolute clock alignment or pure runtime time.
                    residual = host['guest_ready'] - host['spawn_returned'] - (guest[-1]['offset_ns'] - guest[0]['offset_ns'])
                    grouped.setdefault((row['case'], row['workers'], 'startup_envelope', 'outside_recorded_guest_interval'), []).append(residual / 1e9)
            for scope, events in scopes.items():
                for begin, end in zip(events, events[1:]):
                    key = (row['case'], row['workers'], scope, end['name'])
                    grouped.setdefault(key, []).append((end['offset_ns'] - begin['offset_ns']) / 1e9)
    return [{'case': case, 'workers': workers, 'scope': scope, 'stage': stage,
             'count': len(times), 'p50_seconds': statistics.median(times), 'p95_seconds': percentile(times, .95)}
            for (case, workers, scope, stage), times in grouped.items()]


def regression(db, count, clients):
    import pymysql
    connections = []
    try:
        for i in range(clients):
            conn = pymysql.connect(**db.info)
            connections.append(conn)
            with conn.cursor() as cur:
                cur.execute('SET @baseline_session = %s', (i,))
        def queries(index):
            samples = []
            with connections[index].cursor() as cur:
                cur.execute('SELECT @baseline_session')
                assert cur.fetchone() == (index,)
                for _ in range(count):
                    begin = time.perf_counter()
                    cur.execute('SELECT 1')
                    assert cur.fetchone() == (1,)
                    samples.append(time.perf_counter() - begin)
            return samples
        with ThreadPoolExecutor(max_workers=clients) as pool:
            return list(pool.map(queries, range(clients)))
    finally:
        for conn in connections:
            conn.close()


def benchmark(args, report):
    for phase, runs in [('warmup', args.warmup), ('measurement', args.runs)]:
        if not runs:
            continue
        for run in range(runs):
            def fresh():
                start = time.perf_counter()
                with instance('mariamem', args) as db:
                    ready, version = probe(db)
                    stages = stage_timings(db)
                return {'latency_seconds': ready - start, 'server_version': version, 'stage_timings': stages}
            report['samples'].append({'case': 'start_first_sql', 'workers': 1, 'phase': phase, 'run': run,
                                      **measured(fresh, args.interval)})
        # Repeat cold snapshot measurements; retain the last prepared state for forks.
        snapshot = None
        try:
            for run in range(runs):
                with instance('mariamem', args) as db:
                    probe(db, rows=args.rows, seed=True)
                    if run == 0:
                        for clients in [1, args.clients]:
                            for client_index, times in enumerate(regression(db, args.queries, clients)):
                                for query_index, latency in enumerate(times):
                                    report['samples'].append({'case': 'select_1' if clients == 1 else 'multi_connection_select_1',
                                        'workers': clients, 'phase': phase, 'client': client_index,
                                        'query': query_index, 'latency_seconds': latency})
                    db.database.wait_disconnected()
                    start = time.perf_counter()
                    current = db.database.snapshot()
                    report['samples'].append({'case': 'snapshot', 'workers': 1, 'phase': phase, 'run': run,
                        'latency_seconds': time.perf_counter() - start, 'stage_timings': stage_timings(db, 'snapshot'), 'cpu_seconds': None, 'peak_rss_bytes': None})
                if snapshot is not None:
                    snapshot.close()
                snapshot = current
        except BaseException:
            if snapshot is not None:
                snapshot.close()
            raise
        with snapshot:
            for workers in args.workers:
                for run in range(runs):
                    monitor = CostSampler(args.interval)
                    cpu = time.process_time()
                    result = batch('mariamem', args, snapshot, workers, hold=args.hold, monitor=monitor)
                    cost = result.pop('memory')
                    ready = cost['nearest_ready_sample']
                    delta = ready['rss_bytes'] - cost['baseline']['rss_bytes'] if ready else None
                    report['samples'].append({'case': 'fork_first_sql', 'workers': workers, 'phase': phase,
                        'run': run, 'latency_seconds': result['ready_seconds'], 'cost': cost,
                        'incremental_ready_rss_bytes': delta,
                        'incremental_ready_rss_per_db_bytes': delta / workers if delta is not None else None,
                        'python_cpu_seconds': time.process_time() - cpu, **result})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runs', type=positive, default=10)
    parser.add_argument('--warmup', type=int, default=1)
    parser.add_argument('--workers', nargs='+', type=positive, default=[1, 4, 8])
    parser.add_argument('--rows', type=positive, default=1000)
    parser.add_argument('--queries', type=positive, default=100)
    parser.add_argument('--clients', type=positive, default=2)
    parser.add_argument('--interval', type=float, default=.05)
    parser.add_argument('--hold', type=float, default=.1)
    parser.add_argument('--json', type=Path)
    parser.add_argument('--stage-timing', action='store_true', help='opt-in host/Python lifecycle diagnostics; requires instrumented host')
    parser.add_argument('--guest-stage-timing', action='store_true', help='require matching instrumented guest; implies --stage-timing')
    args = parser.parse_args()
    args.stage_timing = args.stage_timing or args.guest_stage_timing
    if args.warmup < 0 or not math.isfinite(args.interval) or args.interval <= 0 or not math.isfinite(args.hold) or args.hold < 0:
        parser.error('warmup/hold must be nonnegative; interval must be positive and finite')
    output = (args.json or RESULTS / f'isolation-baseline-{time.time_ns()}.json').resolve()
    if output.is_relative_to(ROOT) and not output.is_relative_to(RESULTS):
        parser.error('repository-local output must be under benchmarks/results/')
    args.backend = 'mariamem'
    report = {'benchmark': 'isolation_baseline', 'schema_version': 1,
              'started_at': datetime.now(timezone.utc).isoformat(),
              'settings': {k: v for k, v in vars(args).items() if k != 'json'},
              'samples': [], 'completed': False,
              'metric_notes': {
                  'primary': 'Fork to connection and verified first COUNT; group and per-DB wall latency',
                  'rss': 'sampled descendant RSS sum; shared pages may be counted repeatedly',
                  'cpu': 'sampled cumulative descendant CPU delta; incomplete around process startup/exit',
                  'python_cpu': 'parent CPU over full lifecycle including hold/sampling/cleanup',
                  'snapshot_cost': 'CPU and peak RSS unavailable; only isolated Snapshot wall time measured',
                  'sampling': 'ps precision and collection overhead vary; rare PID reuse may alias CPU',
                  'statistics': 'p95 linear interpolation; small run counts are exploratory, no thresholds'}}
    try:
        import mariamem
        origin = Path(mariamem.__file__).resolve()
        if origin.is_relative_to(ROOT / 'python'):
            raise RuntimeError('install a wheel; checkout imports are not the packaged baseline')
        report['environment'] = environment(args)
        report['environment']['package_origin'] = str(origin)
        report['environment']['harness_sha256'] = {name: hashlib.sha256((Path(__file__).parent / name).read_bytes()).hexdigest()
            for name in ['isolation_baseline.py', '_common.py', 'parallel_databases.py']}
        if args.stage_timing:
            with tempfile.TemporaryDirectory(prefix="mariamem-timings-") as timing_dir:
                os.environ["MARIAMEM_TIMING_DIR"] = timing_dir
                if args.guest_stage_timing:
                    os.environ["MARIAMEM_REQUIRE_GUEST_TIMING"] = "1"
                try:
                    benchmark(args, report)
                finally:
                    os.environ.pop("MARIAMEM_TIMING_DIR", None)
                    os.environ.pop("MARIAMEM_REQUIRE_GUEST_TIMING", None)
        else:
            benchmark(args, report)
        report['completed'] = True
    except Exception as exc:
        report['error'] = f'{type(exc).__name__}: {exc}'
        raise
    finally:
        report['summary'] = summarize(report['samples'])
        report['stage_summary'] = summarize_stages(report['samples'])
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps(report['summary'], indent=2))
        print('Stage waterfall (nested scopes overlap; do not add scopes):')
        print(json.dumps(report['stage_summary'], indent=2))
        print(f'Raw results: {output}')


if __name__ == '__main__':
    main()
