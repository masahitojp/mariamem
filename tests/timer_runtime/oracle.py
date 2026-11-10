"""Bounded development oracle, not a benchmark or release acceptance.

Run with the isolated product PYTHONPATH and explicit --host/--output.
SQL matches the earlier Go Pipe probe; this checks reporting over PyMySQL/TCP,
not a before/after transport latency comparison.
"""
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import time

import mariamem
import pymysql


def measure(db, phase, records):
    with pymysql.connect(**db.connection_info(), autocommit=True) as connection:
        with connection.cursor() as query:
            query.execute('SELECT id FROM timer_probe ORDER BY id')
            assert query.fetchall() == ((1,), (2,)), 'baseline changed'
            for pair in range(3):
                for delayed in (False, True):
                    sql = ('ANALYZE FORMAT=JSON SELECT SUM(id + SLEEP(0.01)) FROM timer_probe'
                           if delayed else 'ANALYZE FORMAT=JSON SELECT SUM(id) FROM timer_probe')
                    start = time.perf_counter_ns()
                    query.execute(sql)
                    raw = query.fetchone()[0]
                    wall_ms = (time.perf_counter_ns() - start) / 1e6
                    parsed = json.loads(raw)
                    block = parsed['query_block']
                    table = block['nested_loop'][0]['table']
                    total = block.get('r_total_time_ms')
                    row = dict(phase=phase, pair=pair, delayed=delayed, sql=sql,
                               wall_ms=wall_ms, report=parsed)
                    records.append(row)
                    assert table['r_rows'] == 2 and table['r_loops'] == 1
                    if delayed:
                        assert isinstance(total, (int, float)) and 18 <= total <= wall_ms + 5, row
                    query.execute('SELECT SUM(id) FROM timer_probe')
                    assert query.fetchone() == (3,)
                    row['subsequent_select'] = 'PASS'
    db.wait_disconnected()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = dict(result='FAIL', qualification=False, transport='PyMySQL/TCP',
                  platform=platform.platform(), python=platform.python_version(),
                  pymysql=importlib.metadata.version('PyMySQL'),
                  binary_sha256=hashlib.sha256(args.host.read_bytes()).hexdigest(),
                  observations=[])
    children = []
    session = None
    try:
        with mariamem.start(host_binary=args.host) as db:
            session = db._session
            children.append(db)
            with pymysql.connect(**db.connection_info(), autocommit=True) as connection:
                with connection.cursor() as query:
                    query.execute('CREATE TABLE timer_probe(id INT PRIMARY KEY) ENGINE=InnoDB')
                    query.execute('INSERT INTO timer_probe VALUES(1),(2)')
            db.wait_disconnected()
            measure(db, 'fresh', result['observations'])
            with db.snapshot() as baseline:
                for index in range(2):
                    with baseline.fork(host_binary=args.host) as child:
                        children.append(child)
                        assert child._session is session
                        measure(child, 'child'+str(index+1), result['observations'])
                        with pymysql.connect(**child.connection_info(), autocommit=True) as connection:
                            with connection.cursor() as query:
                                query.execute('INSERT INTO timer_probe VALUES(%s)', (index+10,))
                    assert child.closed and session._process.poll() is None
            assert db.closed
        for child in children:
            assert child.closed and not child.log_path.exists()
        assert session._refs == 0 and session._reaped.is_set()
        assert session._process.poll() == 0
        assert session._process.stdin.closed and session._process.stdout.closed
        assert session._stderr.closed and not session._reader.is_alive()
        assert not session.root.exists()
        result.update(result='PASS', isolated_children=2, cleanup='PASS',
                      host_exit_code=0, remaining_session_refs=0,
                      session_directory_exists=False)
    except BaseException as exc:
        result['error'] = type(exc).__name__+': '+str(exc)
        raise
    finally:
        args.output.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({k:v for k,v in result.items() if k!='observations'}, indent=2))


if __name__ == '__main__':
    main()
