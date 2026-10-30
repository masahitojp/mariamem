#!/usr/bin/env python3
"""Bounded, explicit dbt replay. Native endpoint must be disposable and exclusive."""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / 'scripts'), str(ROOT / 'python')]
from git_identity import inspect_ref, verify_go_binary


def save(path, value):
    path.write_text(json.dumps(value, indent=2, default=str) + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-commit', required=True)
    parser.add_argument('--host-binary', type=Path, required=True)
    parser.add_argument('--native-port', type=int, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    source = inspect_ref(ROOT, 'HEAD').source_commit
    if source != args.source_commit or subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT):
        raise RuntimeError('exact clean source required')
    binary = verify_go_binary(ROOT, args.host_binary, source)
    args.output.mkdir(parents=True, exist_ok=False)
    result = {'result': 'FAIL', 'source_commit': source, 'host_buildinfo': binary,
              'host_sha256': hashlib.sha256(args.host_binary.read_bytes()).hexdigest(),
              'platform': platform.platform(), 'machine': platform.machine(),
              'python': sys.version, 'runs': [], 'errors': [],
              'snapshot_comparison': 'business columns only; generated validity timestamps/IDs excluded'}
    save(args.output / 'dependencies.json', {
        d.metadata['Name']: d.version for d in importlib.metadata.distributions()})
    import mysql.connector
    import mariamem
    versions = {'dbt-mysql': '1.7.0', 'dbt-core': '1.7.20', 'mysql-connector-python': '26.10.0'}
    for name, version in versions.items():
        if importlib.metadata.version(name) != version:
            raise RuntimeError(f'incorrect fixed dependency: {name}')
    dbt = Path(sys.executable).with_name('dbt')
    native = dict(host='127.0.0.1', port=args.native_port, user='root', password='')
    rows = {}
    try:
        for threads in (1, 4):
            for route in ('native', 'guest'):
                record = {'route': route, 'threads': threads, 'steps': [], 'result': 'FAIL'}
                result['runs'].append(record)
                db = None
                conn = None
                root = None
                try:
                    if route == 'guest':
                        db = mariamem.Database(host_binary=args.host_binary, query_timeout=30)
                        endpoint = db.connection_info()
                        root = db._session.root  # test-only cleanup observation
                        record['host_pid'] = db.diagnostics['host_pid']
                    else:
                        endpoint = native
                    conn = mysql.connector.connect(**endpoint)
                    cur = conn.cursor()
                    cur.execute('SELECT VERSION()')
                    record['server_version'] = cur.fetchone()[0]
                    if not record['server_version'].startswith('12.3.3'):
                        raise RuntimeError('expected native/embedded MariaDB12.3.3')
                    # Exclusive disposable endpoint, never an existing application schema.
                    cur.execute('DROP DATABASE IF EXISTS test')
                    cur.execute('CREATE DATABASE test')
                    cur.execute('USE test')
                    project = args.output / f'{route}-{threads}'
                    shutil.copytree(Path(__file__).parent / 'project', project)
                    profile = {'dbt_feasibility': {'target': 'dev', 'outputs': {'dev': {
                        'type': 'mysql', 'server': endpoint['host'], 'port': endpoint['port'],
                        'username': endpoint['user'], 'password': endpoint['password'],
                        'schema': 'test', 'connect_timeout': 20, 'threads': threads}}}}
                    (project / 'profiles.yml').write_text(json.dumps(profile))
                    env = dict(os.environ, DBT_SEND_ANONYMOUS_USAGE_STATS='false', DBT_USE_COLORS='false',
                               DO_NOT_TRACK='1')
                    commands = [('debug', ['debug'], None), ('seed', ['seed'], 1),
                                ('run', ['run'], 4), ('repeat', ['run'], 4),
                                ('build', ['build'], 10), ('snapshot1', ['snapshot'], 1),
                                ('snapshot2', ['snapshot'], 1), ('docs', ['docs', 'generate'], None),
                                ('refresh', ['run', '--full-refresh'], 4)]
                    for label, command, expected in commands:
                        started = time.monotonic()
                        with (project / f'{label}.log').open('wb') as log:
                            proc = subprocess.run([str(dbt), *command, '--project-dir', str(project),
                                                   '--profiles-dir', str(project)], env=env,
                                                  stdout=log, stderr=subprocess.STDOUT, timeout=120)
                        step = {'step': label, 'exit_code': proc.returncode,
                                'seconds': round(time.monotonic() - started, 3)}
                        record['steps'].append(step)
                        if proc.returncode != 0:
                            raise RuntimeError(f'{route}/{threads}/{label}: exit {proc.returncode}')
                        if expected is not None:
                            artifact = json.loads((project / 'target/run_results.json').read_text())
                            statuses = [x['status'] for x in artifact['results']]
                            step['statuses'] = statuses
                            if len(statuses) != expected or any(x not in ('success', 'pass') for x in statuses):
                                raise RuntimeError(f'incorrect result census: {statuses}')
                            save(project / f'{label}-results.json', artifact)
                    catalog = json.loads((project / 'target/catalog.json').read_text())
                    if len(catalog['nodes']) < 5 or catalog.get('errors'):
                        raise RuntimeError('missing/failed dbt catalog')
                    actual = {}
                    for table, columns in {'orders_seed': '*', 'orders': '*', 'order_events': '*',
                                           'customer_names': '*', 'order_totals': '*',
                                           'orders_snapshot': 'order_id, customer, amount, doubled'}.items():
                        cur.execute(f'SELECT {columns} FROM `{table}`')
                        actual[table] = sorted([list(row) for row in cur.fetchall()], key=str)
                    # Keep the original TEXT DISTINCT path; no CAST or SQL_BIG_RESULT workaround.
                    cur.execute("SELECT DATA_TYPE FROM information_schema.columns WHERE table_schema='test' AND table_name='orders' AND column_name='customer'")
                    record['customer_data_type'] = cur.fetchone()[0]
                    if record['customer_data_type'] not in ('text', 'tinytext', 'mediumtext', 'longtext'):
                        raise RuntimeError('original TEXT path was not exercised')
                    if len(actual['customer_names']) != 3 or len(actual['orders_snapshot']) != 3:
                        raise RuntimeError('wrong DISTINCT/snapshot rows')
                    rows[(route, threads)] = json.loads(json.dumps(actual, default=str))
                    save(project / 'rows.json', actual)
                    cur.execute('INSERT INTO orders SELECT * FROM orders LIMIT 1')
                    conn.commit()
                    with (project / 'expected-failure.log').open('wb') as log:
                        proc = subprocess.run([str(dbt), 'test', '--select', 'orders', '--project-dir', str(project),
                                               '--profiles-dir', str(project)], env=env, stdout=log,
                                              stderr=subprocess.STDOUT, timeout=120)
                    statuses = [x['status'] for x in json.loads((project / 'target/run_results.json').read_text())['results']]
                    record['failure_oracle'] = {'exit_code': proc.returncode, 'statuses': statuses}
                    if proc.returncode != 1 or sorted(statuses) != ['fail', 'pass', 'pass']:
                        raise RuntimeError('expected exactly one generic uniqueness test failure')
                    cur.execute('SELECT 1')
                    if cur.fetchone() != (1,):
                        raise RuntimeError('subsequent SELECT failed')
                    cur.execute('DROP DATABASE test')
                    cur.execute("SELECT COUNT(*) FROM information_schema.schemata WHERE schema_name='test'")
                    record['schema_count_after'] = cur.fetchone()[0]
                    if record['schema_count_after'] != 0:
                        raise RuntimeError('schema cleanup failed')
                    record['result'] = 'PASS'
                finally:
                    if conn is not None:
                        conn.close()
                    if db is not None:
                        try:
                            db.wait_disconnected(timeout=5)
                            record['connections_after'] = db.status()['active_connections']
                        finally:
                            db.close()
                        record['host_reaped'] = db._session._process.poll() is not None
                        record['session_directory_removed'] = not root.exists()
                        if not record['host_reaped'] or not record['session_directory_removed']:
                            raise RuntimeError('guest cleanup incomplete')
        if not all(value == rows[('native', 1)] for value in rows.values()):
            raise RuntimeError('native/guest/threads application rows differ')
        result['exact_application_row_parity'] = True
        result['result'] = 'PASS'
    except BaseException as exc:
        result['errors'].append(f'{type(exc).__name__}: {exc}')
        raise
    finally:
        save(args.output / 'result.json', result)


if __name__ == '__main__':
    main()
