"""Read-only reconciliation of existing evidence; no guest or new measurement."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PROFILE_SOURCE = 'e556c36570e1be023f8a9c8243381c6605079592'
BASELINE = '500020e7dc6d702ef059f0e73a4bab738103b774'
OLD_SOURCE = '260633b8c36078d5830983217ec2ed53a2c61920'

def read_at(commit, path):
    return subprocess.check_output(['git', 'show', commit + ':' + path], cwd=ROOT)

def digest(data):
    return hashlib.sha256(data).hexdigest()

def collect():
    result = {'profile_source_commit': PROFILE_SOURCE, 'profiles': []}
    for index, arm in enumerate(['baseline', 'candidate', 'candidate', 'baseline']):
        path = f'benchmarks/uca-p8-attribution/results/diagnostic-{index}-{arm}-profile.txt'
        data = read_at(PROFILE_SOURCE, path)
        workers = []
        for block in data.decode().split('\n\n'):
            chain = re.findall(r'/code/p\d\.(Fn\d+)\+', block)
            if 'Fn16595' not in chain:
                continue
            count = int(block.split(' @ ')[0])
            workers.append({'count': count, 'chain': chain,
                            'untimed_atomic_wait': 'base.go:1946' in block,
                            'get_task_on_stack': 'Fn16594' in chain,
                            'task_execute_on_stack': 'Fn16586' in chain})
        assert len(workers) == 3 and sum(w['count'] for w in workers) == 3
        assert all(w['untimed_atomic_wait'] and w['task_execute_on_stack']
                   and not w['get_task_on_stack'] for w in workers)
        result['profiles'].append({'path': path, 'sha256': digest(data),
                                   'pool_worker_shaped_stacks': workers})
    bindings = {}
    for package, names in {'p6': ['Fn16595'], 'p7': ['Fn16596', 'Fn16605', 'Fn16606'],
                           'p4': ['Fn16597'], 'p5': ['Fn16603']}.items():
        path = f'internal/generatedgo/code/{package}/{package}_pure.go'
        text = read_at(BASELINE, path).decode()
        for name in names:
            match = re.search(r'^func '+name+r'\(.*?(?=\nfunc |\Z)', text, re.M | re.S)
            assert match
            body = match.group()
            bindings[name] = {'path': path, 'sha256': digest(body.encode())}
            if name == 'Fn16595':
                clear = 'base.AtomicStore32_8(m, l0, int32(408), v25)'
                assert body.index(clear) < body.index('v30 = Fn16594(')
                assert 'Fn16596(' not in body
            if name == 'Fn16597':
                assert 'base.AtomicRmwXchg32_8u(m, l0, int32(408), v81)' in body
    result['baseline_function_binding'] = {'source_commit': BASELINE, 'functions': bindings}
    old_path = 'benchmarks/issue88cappool/results/observations.json'
    old_bytes = read_at(OLD_SOURCE, old_path)
    old = json.loads(old_bytes)
    run = next(x for x in old if x['name'] == 'natural-16-pool8-on')
    observer = next(x for x in run['read_observers'] if x['db_id'] == 'issue68-db-2')
    request = next(x for x in observer['ios'] if x['id'] == 3)
    a = request['initial_admission']
    assert request['submit_return_us'] - request['submit_us'] == 5
    assert a['dequeued_us'] - request['submit_us'] == 389421
    assert a['blocked_count'] == 0
    assert a['last_allowed']['active'] - a['last_allowed']['long'] - a['last_allowed']['waiting'] == 3
    assert a['last_allowed']['concurrency'] == 16
    result['historical_residual'] = {'source_commit': OLD_SOURCE, 'path': old_path,
        'sha256': digest(old_bytes), 'run': run['name'], 'db_id': observer['db_id'],
        'request': request, 'interpretation': 'Historical only; sparse gate snapshots do not prove continuous permission or identify creation outcomes.'}
    return result

if __name__ == '__main__':
    rendered = json.dumps(collect(), indent=2) + '\n'
    if sys.argv[1:] == ['--check']:
        assert (HERE/'reconciliation.json').read_text() == rendered
        print('PASS: four saved profiles, baseline bindings and historical request; no new runtime claim')
    elif not sys.argv[1:]:
        print(rendered, end='')
    else:
        raise SystemExit('usage: replay.py [--check]')
