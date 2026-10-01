#!/usr/bin/env python3
"""Darwin stage/dirty-content characterization; no production architecture edits."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import time
import urllib.request

sys.path.insert(0, str(Path(__file__).parents[1]/'wasm2go'))
from sql_execution import Guest


def get(port, endpoint):
    with urllib.request.urlopen(f'http://127.0.0.1:{port}/{endpoint}', timeout=60) as response:
        b = response.read()
        return json.loads(b) if endpoint == 'sample' else b.decode()


def delta(before, after):
    size = after['page_size']
    pages = sum(h != before['pages'].get(k) for k, h in after['pages'].items())
    files = {f['path']: f for f in before['files']}
    modified, blocks = [], 0
    for f in after['files']:
        old = files.get(f['path'], {'hash': None, 'blocks': []})
        if old['hash'] != f['hash']:
            changed = sum(i >= len(old['blocks']) or b != old['blocks'][i] for i, b in enumerate(f['blocks']))
            blocks += changed
            modified.append({'path': f['path'], 'changed_blocks': changed, 'size': f['size']})
    deleted = sorted(set(files) - {f['path'] for f in after['files']})
    return {'linear_changed_pages': pages, 'linear_changed_content_bytes': pages*size,
            'fs_changed_blocks': blocks, 'fs_changed_content_bytes': blocks*size,
            'fs_modified': modified, 'fs_deleted': deleted}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--binary', type=Path, required=True)
    p.add_argument('--helper', type=Path, required=True)
    p.add_argument('--host', type=Path, required=True)
    p.add_argument('--guest', type=Path, required=True)
    p.add_argument('--output-dir', type=Path, required=True)
    p.add_argument('--runs', type=int, default=3)
    p.add_argument('--os-only', action='store_true')
    p.add_argument('--workloads', nargs='+', default=['read', 'write', 'rollback', 'schema', 'orm'])
    a = p.parse_args()
    out = a.output_dir.resolve(); out.mkdir(parents=True, exist_ok=True)
    results = {'method': 'OS counters before observer; resident-only SHA256 content deltas; not write-history tracking', 'trials': []}
    for run in range(a.runs):
        for mode in a.workloads:
            directory = out/f'{run}-{mode}'; directory.mkdir()
            env = dict(os.environ, COW_CONTROL_DIR=str(directory), COW_PAUSE_INIT='1')
            # Clean images exported only after normal shutdown, never from live hashes.
            if not a.os_only and run == 0 and mode == 'read': env['COW_EXPORT'] = str(out/'prepared-image')
            log = (directory/'guest.log').open('wb')
            adapter = directory/'guest.sh'; adapter.write_text('#!/bin/sh\nexec '+shlex.quote(str(a.binary.resolve()))+' measure\n'); adapter.chmod(0o755)
            started = time.perf_counter()
            if mode == 'orm':
                proc = subprocess.Popen([str(a.host.resolve()), '--runtime', str(adapter), '--module', str(a.guest.resolve())], env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=log)
                g = None
            else:
                g = Guest([str(a.binary.resolve()), 'measure'], log, env=env); proc = g.proc
            row = {'run': run, 'workload': mode, 'samples': {}, 'completed': False}
            try:
                limit = time.monotonic()+30
                while not (directory/'control.json').exists():
                    if proc.poll() is not None or time.monotonic()>limit: raise RuntimeError('control startup failed')
                    time.sleep(.005)
                control = json.loads((directory/'control.json').read_text()); port = control['port']; pid = control['pid']
                def sample(label):
                    counters = json.loads(subprocess.check_output([str(a.helper.resolve()), str(pid)], text=True))[str(pid)]
                    vm = subprocess.run(['vmmap', '-summary', '-wide', str(pid)], capture_output=True, text=True)
                    (directory/f'{label}.vmmap').write_text(vm.stdout+vm.stderr)
                    s = {'page_size': 16384, 'pages': {}, 'files': [], 'content_observer_disabled': True} if a.os_only else get(port, 'sample')
                    s['os'] = counters; s['vmmap_exit_code'] = vm.returncode
                    row['samples'][label] = s
                    (out/'results.json').write_text(json.dumps(results, indent=2)+'\n')
                    return s
                results['trials'].append(row)
                sample('initialized'); get(port, 'start')
                if g:
                    assert g.frame()['result']['ready']
                    def q(sql):
                        r = g.call(2, sql); assert r['ok'], (sql, r); return r
                    assert g.call(1)['ok']
                else:
                    info = json.loads(proc.stdout.readline()); assert info['event']=='ready', info
                    import pymysql
                    conn = pymysql.connect(host=info['host'], port=info['port'], user='root', database='test', autocommit=True)
                    def q(sql):
                        with conn.cursor() as c: c.execute(sql); return c.fetchall()
                sample('ready')
                q('CREATE TABLE benchmark_rows(id INT PRIMARY KEY, payload VARCHAR(64)) ENGINE=InnoDB')
                sample('schema')
                q('START TRANSACTION')
                q('INSERT INTO benchmark_rows VALUES '+','.join(f"({i},'{32*'x'}')" for i in range(1000)))
                q('COMMIT'); q('SELECT COUNT(*) FROM benchmark_rows')
                sample('fixture')
                if g: assert g.call(3)['closed']
                else: conn.close()
                # Observe normal background quiescence; no FLUSH/config changes.
                time.sleep(2)
                prepared = sample('prepared')
                if g: assert g.call(1)['ok']
                else: conn = pymysql.connect(host=info['host'], port=info['port'], user='root', database='test', autocommit=True)
                if mode == 'read':
                    q('SELECT COUNT(*) FROM benchmark_rows')
                    for i in range(20): q(f'SELECT payload FROM benchmark_rows WHERE id={i*37}')
                elif mode == 'write':
                    q('START TRANSACTION'); q("INSERT INTO benchmark_rows VALUES (1001,'write')"); q("UPDATE benchmark_rows SET payload='updated' WHERE id=1"); q('COMMIT')
                elif mode == 'rollback':
                    q('START TRANSACTION'); q("INSERT INTO benchmark_rows VALUES (1001,'rollback')"); q("UPDATE benchmark_rows SET payload='rollback' WHERE id=1"); q('ROLLBACK')
                    r=q('SELECT COUNT(*) FROM benchmark_rows'); row['rollback_count_result']=r
                elif mode == 'schema': q('CREATE TABLE scratch(id INT PRIMARY KEY, v VARCHAR(64)) ENGINE=InnoDB')
                elif mode == 'orm':
                    source = Path(__file__).resolve().parents[3]/'tests/consumer/test_sqlalchemy_dogfood.py'
                    spec = importlib.util.spec_from_file_location('cow_dogfood', source); dog = importlib.util.module_from_spec(spec); spec.loader.exec_module(dog)
                    from sqlalchemy import create_engine
                    engine = create_engine(f"mysql+pymysql://root@127.0.0.1:{info['port']}/test")
                    try:
                        dog.prepare(engine)
                    except Exception as error:
                        # Retain the actual schema-discovery failure; no runtime fix.
                        if 'Aria' not in str(error) or '1030' not in str(error): raise
                        row['orm_schema_discovery_failure'] = str(error).split('[SQL:')[0]
                        # Equivalent fixture DDL, with no information_schema probe.
                        dog.Base.metadata.create_all(engine, checkfirst=False)
                        with dog.Session(engine) as session:
                            user = dog.User(name='seed@example.test', fullname=None)
                            user.addresses.append(dog.Address(email_address='seed@example.test'))
                            session.add(user); session.commit()
                        row['orm_setup_workaround'] = 'same SQLAlchemy models and seed; create_all(checkfirst=False) after recorded Aria failure'
                    dog.test_03_update_commit_and_delete((engine, None, {}))
                    row['orm_workload']='prepare + unchanged test_03_update_commit_and_delete'
                changed = sample('after_workload'); row['workload_delta'] = delta(prepared, changed)
                if g: assert g.call(3)['closed']
                else:
                    conn.close(); engine.dispose()
                closed = sample('connection_closed'); row['closed_delta'] = delta(prepared, closed)
                if g: assert g.stop()==0
                else:
                    proc.stdin.close(); assert proc.wait(timeout=30)==0
                row['completed']=True
                if a.os_only:
                    row['workload_delta'] = row['closed_delta'] = None
            finally:
                if proc.poll() is None: proc.kill(); proc.wait()
                log.close()
                row['exit_code']=proc.returncode
                (out/'results.json').write_text(json.dumps(results, indent=2)+'\n')
            print(run, mode, 'complete', flush=True)


if __name__ == '__main__': main()
