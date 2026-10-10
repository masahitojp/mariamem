#!/usr/bin/env python3
"""Bounded serial two-toolchain runner over the existing ownedprepared fixture."""
import json, os, subprocess, sys, time
from pathlib import Path

root = Path.cwd()
workspace = root.parent
scratch = workspace / 'temp'
evidence = workspace / 'evidence'
sys.path.insert(0, str(root / 'scripts'))
from experiment_disk import DiskGuard, run_guarded

builds = json.loads((evidence / 'builds.json').read_text())
source = builds['source_commit']
out = evidence / 'performance'
out.mkdir(exist_ok=True)
env = dict(os.environ, GOTOOLCHAIN='local', GOMAXPROCS='8', GOGC='100',
           GOMEMLIMIT='off', GODEBUG='', TMPDIR=str(scratch / 'runtime'))
env.pop('GOEXPERIMENT', None)
guard = DiskGuard(workspace, 12, 12)
steps = []


def run(case, mode, trial, version, size, tables, workers, warm=False):
    name = f'{case}-{mode}-{trial:02d}-{version}'
    target = out / (name + '.json')
    if target.exists():
        raise RuntimeError(f'refusing to overwrite or silently reuse {name}')
    args = [scratch / ('bench' + version), '-payload-mib', str(size),
            '-tables', str(tables), '-workers', str(workers), '-forks', '4',
            '-lifecycle', mode, '-workload', 'app-connections', '-toolchain-metrics',
            '-helper', scratch / 'process-cost', '-label', source, '-out', target]
    if case == 'load':
        args.append('-load-roundtrip')
    start = time.monotonic()
    with (out / (name + '.log')).open('w') as log:
        code = run_guarded(list(map(str, args)), guard, cwd=root, env=env,
                           output=log, timeout=240)
    record = dict(case=case, mode=mode, trial=trial, version=version,
                  warmup=warm, returncode=code, seconds=time.monotonic()-start)
    steps.append(record)
    (evidence / 'campaign.json').write_text(json.dumps(dict(
        source_commit=source, env={k: env[k] for k in ['GOTOOLCHAIN', 'GOMAXPROCS',
        'GOGC', 'GOMEMLIMIT', 'GODEBUG']}, steps=steps, disk=guard.check()), indent=2))
    print('DONE', name, code, flush=True)
    if code:
        raise SystemExit(code)
    data = json.loads(target.read_text())
    assert data['go'] == 'go1.' + ('26.8' if version == '1268' else '27.2')
    if data['go_memory']['process_peak_rss_bytes'] > 6 * 2**30:
        raise RuntimeError('6 GiB process RSS budget exceeded; stop campaign')


for case, size, tables, workers, trials in [
    ('light', 0, 1, 1, 30), ('fixture', 10, 8, 1, 30),
    ('parallel', 10, 8, 4, 30), ('large', 100, 8, 1, 6),
    ('load', 0, 1, 1, 30)]:
    modes = ['fork'] if case == 'load' else ['fresh', 'fork']
    for mode in modes:
        for version in ['1268', '1272']:
            run(case, mode, 99, version, size, tables, workers, warm=True)
    for trial in range(trials):
        versions = ['1268', '1272'] if trial % 2 == 0 else ['1272', '1268']
        for mode in modes if trial % 2 == 0 else list(reversed(modes)):
            for version in versions:
                run(case, mode, trial, version, size, tables, workers)
