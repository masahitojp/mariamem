#!/usr/bin/env python3
"""One fresh Python process, public API only; caller pins SDK and host identities."""
import argparse
import json
import os
from pathlib import Path
import resource
import sys
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sdk', type=Path, required=True)
    parser.add_argument('--host', type=Path, required=True)
    parser.add_argument('--scale', choices=('small', 'medium', '100mib'), required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.sdk.resolve()))
    import mariamem
    import pymysql
    rows = {'small': 100, 'medium': 10000, '100mib': 102400}[args.scale]
    forks = 16 if args.scale == '100mib' else 2
    payload = ('0123456789abcdef' * 64)[:256 if args.scale == 'small' else 1024]
    phases, pids = {}, []

    def timed(name, fn):
        at = time.perf_counter_ns()
        value = fn()
        phases[name] = (time.perf_counter_ns()-at)/1e6
        return value

    def query(c, statement, parameters=None):
        with c.cursor() as cursor:
            cursor.execute(statement, parameters)
            return cursor.fetchall()

    def connect(db):
        return pymysql.connect(**db.connection_info(), charset='utf8mb4')

    def disconnect(db, c):
        c.close()
        db.wait_disconnected()

    begin = time.perf_counter_ns()
    with timed('prepare/start', lambda: mariamem.start(host_binary=args.host)) as setup:
        pids.append(setup.diagnostics['host_pid'])

        def prepare():
            c = connect(setup)
            try:
                version = query(c, 'SELECT VERSION()')[0][0]
                assert version.startswith('12.3.3'), version
                query(c, 'CREATE TABLE users(id INT PRIMARY KEY, email VARCHAR(128) NOT NULL UNIQUE, status INT NOT NULL, payload TEXT) ENGINE=InnoDB')
                query(c, 'CREATE TABLE orders(id INT PRIMARY KEY, user_id INT NOT NULL, amount INT NOT NULL, KEY(user_id), FOREIGN KEY(user_id) REFERENCES users(id)) ENGINE=InnoDB')
                with c.cursor() as cursor:
                    for lo in range(1, rows+1, 500):
                        cursor.executemany('INSERT INTO users VALUES(%s,%s,0,%s)', [(i, f'u{i}@example.test', payload) for i in range(lo, min(lo+500, rows+1))])
                        cursor.executemany('INSERT INTO orders VALUES(%s,%s,10)', [(i, i) for i in range(lo, min(lo+500, rows+1))])
                c.commit()
                assert query(c, 'SELECT COUNT(*) FROM users') == ((rows,),)
            finally:
                disconnect(setup, c)

        timed('prepare/migrate-seed', prepare)
        with timed('prepare/snapshot', setup.snapshot) as baseline:
            assert setup.closed
            for index in range(forks):
                with timed(f'child{index}/start', baseline.fork) as child:
                    pids.append(child.diagnostics['host_pid'])
                    c = timed(f'child{index}/connect', lambda: connect(child))

                    def crud():
                        assert query(c, 'SELECT COUNT(*) FROM users') == ((rows,),)
                        assert query(c, 'SELECT status,payload FROM users WHERE id=1') == ((0, payload),)
                        query(c, 'UPDATE users SET status=2 WHERE id=1')
                        c.commit()
                        assert query(c, 'SELECT status FROM users WHERE id=1') == ((2,),)
                        query(c, 'DELETE FROM orders WHERE id=1')
                        c.rollback()
                        assert query(c, 'SELECT amount FROM orders WHERE id=1') == ((10,),)
                        query(c, 'DELETE FROM orders WHERE id=1')
                        c.commit()
                        assert query(c, 'SELECT amount FROM orders WHERE id=1') == ()

                    timed(f'child{index}/crud', crud)
                    timed(f'child{index}/disconnect', lambda: disconnect(child, c))
                    timed(f'child{index}/close', child.close)
            timed('baseline/close', baseline.close)
    whole = (time.perf_counter_ns()-begin)/1e6
    for pid in set(pids):
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            continue
        raise AssertionError(f'unreaped host {pid}')
    assert not list(Path(os.environ['TMPDIR']).iterdir()), 'owned scratch not reclaimed'
    args.output.write_text(json.dumps(dict(result='PASS', scale=args.scale, rows=rows,
        payload_bytes=rows*len(payload), forks=forks, whole_ms=whole,
        times_ms=phases, unique_hosts=len(set(pids)),
        reaped_host_maxrss_raw=resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss), indent=2)+'\n')


if __name__ == '__main__':
    main()
