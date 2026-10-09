#!/usr/bin/env python3
"""Bounded diagnostic for an existing active-SQL interruption limitation.

Not a normal Snapshot/ownership acceptance gate. Compare an exact released host
and a candidate host; Fresh startup uses no prepared backing.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import time

import mariamem
import pymysql


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', required=True)
    parser.add_argument('--label', required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    result = {'label': args.label, 'host_sha256': hashlib.sha256(Path(args.host).read_bytes()).hexdigest(),
              'mode': 'Fresh; no Snapshot/backing', 'shutdown_timeout_seconds': 1,
              'purpose': 'diagnostic, not a correctness PASS gate'}
    with mariamem.start(host_binary=args.host, shutdown_timeout=1) as db:
        with pymysql.connect(**db.connection_info(), autocommit=True, read_timeout=5) as conn:
            def query():
                try:
                    with conn.cursor() as cursor:
                        cursor.execute('SELECT SLEEP(0.2)')
                        return {'rows': cursor.fetchall()}
                except pymysql.Error as error:
                    return {'error': str(error)}
            with ThreadPoolExecutor(max_workers=1) as pool:
                pending = pool.submit(query)
                deadline = time.monotonic() + 5
                while not db.status()['busy']:
                    if time.monotonic() > deadline:
                        raise RuntimeError('active query was not observed')
                    time.sleep(0.005)
                began = time.monotonic()
                try:
                    db.close()
                    result['close_result'] = 'PASS'
                except mariamem.HostError as error:
                    result.update(close_result='FAIL', error=str(error))
                result['close_seconds'] = time.monotonic() - began
                result['query'] = pending.result(timeout=10)
        result.update(process_reaped=db._process.poll() is not None,
                      pipes_closed=db._process.stdin.closed and db._process.stdout.closed,
                      reader_joined=not db._reader.is_alive(), logs=db.logs[-2048:])
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({key: value for key, value in result.items() if key != 'logs'}))


if __name__ == '__main__':
    main()
