#!/usr/bin/env python3
"""Small installed-wheel default Start/Fork/resource check, not release benchmarks."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import time

import mariamem
import pymysql


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--trials', type=int, default=20)
    p.add_argument('--counter', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    if args.trials < 1 or os.environ.get('MARIAMEM_NATIVE_DIR') or os.environ.get('MARIAMEM_RUNTIME'):
        p.error('positive trials and no runtime overrides required')
    samples = []

    def counters(*pids):
        return json.loads(subprocess.check_output([str(args.counter.resolve()),*map(str,pids)]))

    def trial(snapshot=None):
        before = counters(os.getpid())
        start = time.perf_counter()
        db = mariamem.start() if snapshot is None else snapshot.fork()
        try:
            with pymysql.connect(**db.connection_info(),autocommit=True) as conn:
                with conn.cursor() as cur:
                    cur.execute('SELECT 1' if snapshot is None else 'SELECT COUNT(*) FROM benchmark_rows')
                    assert cur.fetchone() == ((1,) if snapshot is None else (1000,))
            elapsed = (time.perf_counter()-start)*1000
            db.wait_disconnected()
            ready = counters(os.getpid(),db.diagnostics['host_pid'],db.diagnostics['runtime_pid'])
            samples.append({'case':'start' if snapshot is None else 'fork','latency_ms':elapsed,
                'before':before,'ready':ready,'parent_pid':os.getpid(),'diagnostics':db.diagnostics})
            print(samples[-1]['case'],round(elapsed,3),'ms',flush=True)
        finally:
            db.close()
        samples[-1]['after_close'] = counters(os.getpid())

    for _ in range(args.trials):
        trial()
    db=mariamem.start()
    try:
        with pymysql.connect(**db.connection_info(),autocommit=True) as conn:
            with conn.cursor() as cur:
                cur.execute('CREATE TABLE benchmark_rows(id INT PRIMARY KEY,value INT)')
                cur.executemany('INSERT INTO benchmark_rows VALUES(%s,%s)',[(i,i) for i in range(1000)])
        db.wait_disconnected()
        snapshot=db.snapshot()
    finally:
        db.close()
    try:
        for _ in range(args.trials):
            trial(snapshot)
    finally:
        snapshot.close()
    args.output.write_text(json.dumps({'runtime':'generated-go','boundary':'installed host-only wheel public API to first SQL; manifest verification included',
        'trials':args.trials,'samples':samples},indent=2)+'\n')


if __name__ == '__main__':
    main()
