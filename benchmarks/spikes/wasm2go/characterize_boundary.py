#!/usr/bin/env python3
"""Interleave isolated startup boundaries; optionally correlate existing guest traces."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import random
import shlex
import subprocess
import time

from measure_execution import distribution
from sql_execution import Guest


def correlate(path):
    trace = json.loads(path.read_text())
    events = sorted(trace['events'], key=lambda e: e['ns'])
    matches = []
    for index, event in enumerate(events):
        if event['kind'] != 'cleaner-target-after-lock' or event.get('a', 0) != 0 or event.get('b', 0) <= 0:
            continue
        tid = event['tid']
        before = [e for e in events[:index] if e['kind'] == 'cleaner-target-before-lock' and e['tid'] == tid]
        if not before:
            continue
        read = before[-1]
        signals = [e for e in events if read['ns'] <= e['ns'] <= event['ns']
                   and e['kind'] == 'cond-signal' and e['ea'] == 6880136 and e.get('a', 0) == 0]
        waits = [e for e in events[index+1:] if e['tid'] == tid and e['kind'] == 'wait'
                 and e.get('timeout_ns', 0) >= 900_000_000 and e.get('a') == 2]
        if not signals or not waits:
            continue
        wait = waits[0]
        returns = [e for e in events if e['tid'] == tid and e['kind'] == 'return'
                   and e.get('ea') == wait['ea'] and e['ns'] >= wait['ns']]
        if not returns or returns[0].get('b') != 2 or returns[0]['ns'] - wait['ns'] < 900_000_000:
            continue
        ret = returns[0]
        # The pinned symbol map identifies Fn17976=create_log_file and
        # Fn18158=buf_flush_wait. Require the initialization caller chain,
        # rather than labeling an arbitrary later cleaner timeout as startup.
        main_waits = [e for e in events if e['kind'] == 'wait' and e['tid'] == 0
                      and read['ns'] <= e['ns'] <= ret['ns']
                      and any(c.endswith('.Fn17976') for c in e.get('callers', []))
                      and any(c.endswith('.Fn18158') for c in e.get('callers', []))]
        if not main_waits:
            continue
        compact = [read, signals[-1], event, wait]
        compact += [e for e in events if e['tid'] == tid and e.get('ea') == wait['ea']
                    and wait['ns'] <= e['ns'] <= ret['ns'] and e['kind'] in ('park', 'wake', 'timeout')]
        compact.append(ret)
        compact.append(main_waits[0])
        matches.append(compact)
    cleaner = [e for e in events if e['kind'].startswith('cleaner-target-')]
    tids = {e['tid'] for e in cleaner}
    return {'known_race': bool(matches), 'race_timelines': matches,
            'dropped': trace['dropped'], 'event_count': len(events),
            'cleaner_timing': cleaner[:4],
            'cleaner_thread_start': [e for e in events if e['kind'] == 'thread-start' and e['tid'] in tids],
            'startup_trace_sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--driver', type=Path, required=True)
    p.add_argument('--probe', type=Path, required=True)
    p.add_argument('--guest', type=Path, required=True)
    p.add_argument('--output-dir', type=Path, required=True)
    p.add_argument('--variants', nargs='+', default=['python-direct', 'raw', 'raw-verify',
                   'transport', 'transport-verify', 'wire', 'full-no-client', 'full'])
    p.add_argument('--runs', type=int, default=100)
    p.add_argument('--seed', type=int, default=4817)
    p.add_argument('--diagnostic', action='store_true')
    a = p.parse_args()
    out = a.output_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)
    assert not (out/'results.json').exists(), 'use a fresh output directory'
    probe = a.probe.resolve()
    adapter = out/'exec-guest.sh'
    adapter.write_text('#!/bin/sh\nexec '+shlex.quote(str(probe))+' measure\n')
    adapter.chmod(0o755)
    pins = {key: hashlib.sha256(path.read_bytes()).hexdigest()
            for key, path in [('probe', probe), ('adapter', adapter), ('driver', a.driver), ('guest', a.guest)]}
    assert pins['guest'] == '6a2e1a8c00da1953cf0379e6cf5464c0f3f3668de674467673ee701230dd27d3'
    rng = random.Random(a.seed)
    report = {'diagnostic': a.diagnostic, 'seed': a.seed, 'pins': pins, 'trials': [], 'summary': {}}
    for block in range(a.runs):
        order = list(a.variants)
        rng.shuffle(order)
        for variant in order:
            prefix = out/f'{block:03d}-{variant}'
            env = {k: v for k, v in os.environ.items() if k not in
                   ('MARIAMEM_SPIKE_TRACE', 'MARIAMEM_TIMING_DIR', 'MARIAMEM_INIT_DIAGNOSTICS')}
            if a.diagnostic:
                env['MARIAMEM_SPIKE_TRACE'] = str(prefix.with_suffix('.trace.json'))
                env['MARIAMEM_TIMING_DIR'] = str(out)
            if variant == 'python-direct':
                with prefix.with_suffix('.log').open('wb') as log:
                    start = time.perf_counter()
                    g = Guest([str(probe), 'measure'], log, env=env)
                    try:
                        assert g.frame()['result']['ready']
                        ready = time.perf_counter()-start
                        assert g.call(1)['ok'] and g.call(2, 'SELECT 1')['ok']
                        sql = time.perf_counter()-start
                        assert g.call(3)['closed'] and g.stop() == 0
                    finally:
                        if g.proc.poll() is None:
                            g.proc.kill(); g.proc.wait()
                        g.proc.stdin.close(); g.proc.stdout.close()
                row = {'variant': variant, 'ready_seconds': ready, 'sql_seconds': sql, 'clean_shutdown': True}
            else:
                command = [str(a.driver.resolve()), '--variant', variant, '--runtime', str(adapter),
                           '--probe', str(probe), '--probe-hash', pins['probe'], '--runtime-hash', pins['adapter'],
                           '--module', str(a.guest.resolve()), '--guest-log', str(prefix.with_suffix('.log'))]
                result = subprocess.run(command, env=env, capture_output=True, text=True, timeout=40)
                prefix.with_suffix('.host.log').write_text(result.stderr)
                result.check_returncode()
                row = json.loads(result.stdout)
            row['block'] = block
            row['position'] = order.index(variant)
            row['known_page_cleaner_race'] = None
            if a.diagnostic:
                row['correlation'] = correlate(prefix.with_suffix('.trace.json'))
                row['known_page_cleaner_race'] = row['correlation']['known_race']
            report['trials'].append(row)
        for variant in a.variants:
            rows = [r for r in report['trials'] if r['variant'] == variant]
            report['summary'][variant] = {key: distribution([r[key] for r in rows if r[key] is not None])
                                         for key in ('ready_seconds', 'sql_seconds')
                                         if any(r[key] is not None for r in rows)}
            report['summary'][variant].update({
                'ready_ge500ms': sum(r['ready_seconds'] >= .5 for r in rows),
                'ready_ge900ms': sum(r['ready_seconds'] >= .9 for r in rows),
                'known_race_count': sum(r['known_page_cleaner_race'] is True for r in rows) if a.diagnostic else None,
                'slow_without_known_race': sum(r['ready_seconds'] >= .5 and not r['known_page_cleaner_race'] for r in rows) if a.diagnostic else None})
        (out/'results.json').write_text(json.dumps(report, indent=2)+'\n')
        print(f'block {block+1}/{a.runs}', flush=True)


if __name__ == '__main__':
    main()
