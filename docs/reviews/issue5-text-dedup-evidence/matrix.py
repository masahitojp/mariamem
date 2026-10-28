"""Native/guest SQL observations, one guest DB per case, no success relabelling."""
import json
from pathlib import Path
import subprocess
import sys
import time

import pymysql

OUT = Path(__file__).resolve().parent
HOST = str(Path(sys.argv[1]).resolve())
SUFFIX = '-fddup' if 'fddup' in HOST else ''
cases = []
for kind in ['VARCHAR(32)', 'VARCHAR(255)', 'VARBINARY(255)', 'VARCHAR(1000)',
             'VARCHAR(2000)', 'TINYTEXT', 'TEXT', 'MEDIUMTEXT', 'LONGTEXT', 'BLOB']:
    cases.append((kind, kind, [], 'SELECT DISTINCT customer FROM t'))
for label, setup, sql in [
    ('empty', ['DELETE FROM t'], 'SELECT DISTINCT customer FROM t'),
    ('one', ['DELETE FROM t WHERE id=2'], 'SELECT DISTINCT customer FROM t'),
    ('limit', [], 'SELECT DISTINCT customer FROM t LIMIT 1'),
    ('distinct_order', [], 'SELECT DISTINCT customer FROM t ORDER BY customer'),
    ('multi_column', [], 'SELECT DISTINCT id, customer FROM t'),
    ('union', [], 'SELECT customer FROM t UNION SELECT customer FROM t'),
    ('derived', [], 'SELECT * FROM (SELECT DISTINCT customer FROM t) x'),
    ('group', [], 'SELECT customer FROM t GROUP BY customer'),
    ('ctas', [], 'CREATE TABLE cn AS SELECT DISTINCT customer FROM t'),
    ('insert', ['CREATE TABLE dst LIKE t'], 'INSERT INTO dst(customer) SELECT DISTINCT customer FROM t'),
    ('view', ['CREATE VIEW v AS SELECT DISTINCT customer FROM t'], 'SELECT * FROM v'),
    ('index', ['ALTER TABLE t ADD INDEX (customer(10))'], 'SELECT DISTINCT customer FROM t'),
    ('count', [], 'SELECT COUNT(DISTINCT customer) FROM t'),
    ('union_all', [], 'SELECT customer FROM t UNION ALL SELECT customer FROM t'),
    ('big_result', [], 'SELECT SQL_BIG_RESULT DISTINCT customer FROM t'),
    ('cast', [], 'SELECT DISTINCT CAST(customer AS CHAR(255)) FROM t'),
    ('aggregate', [], 'SELECT customer, COUNT(*) FROM t GROUP BY customer'),
    ('order', [], 'SELECT customer FROM t ORDER BY customer'),
]:
    cases.append((label, 'TEXT', setup, sql))

def observe(args, kind, setup, sql):
    conn = pymysql.connect(**args, autocommit=True, read_timeout=5)
    result = {}
    try:
        with conn.cursor() as cur:
            cur.execute('CREATE TABLE t(id INT, customer ' + kind + ')')
            cur.execute("INSERT INTO t VALUES(1,'alice'),(2,'bob')")
            for command in setup:
                cur.execute(command)
            start = time.monotonic()
            try:
                cur.execute(sql)
                result['rows'] = cur.fetchall()
                result['affected'] = cur.rowcount
                result['outcome'] = 'OK'
            except Exception as exc:
                result['outcome'] = 'ERROR'
                result['error'] = str(exc)
            result['elapsed'] = time.monotonic() - start
    finally:
        conn.close()
    return result

results = []
for index, (label, kind, setup, sql) in enumerate(cases):
    record = dict(label=label, type=kind, setup=setup, sql=sql)
    args = dict(host='127.0.0.1', port=33315, user='root')
    conn = pymysql.connect(**args, autocommit=True)
    with conn.cursor() as cur:
        cur.execute('DROP DATABASE IF EXISTS issue5')
        cur.execute('CREATE DATABASE issue5')
        cur.execute('SELECT VERSION()')
        record['native_version'] = cur.fetchone()[0]
    conn.close()
    args['database'] = 'issue5'
    record['native'] = observe(args, kind, setup, sql)
    with (OUT / ('matrix-host' + SUFFIX + '.log')).open('a') as log:
        proc = subprocess.Popen([HOST, '--query-timeout=1s'], stdin=subprocess.PIPE,
                                stdout=subprocess.PIPE, stderr=log, text=True)
        try:
            ready = json.loads(proc.stdout.readline())
            args = {k: ready[k] for k in ('host', 'port', 'user', 'password', 'database')}
            record['guest'] = observe(args, kind, setup, sql)
        finally:
            if proc.poll() is None:
                proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
    # Byte values have an unambiguous tagged JSON representation.
    results.append(record)
    (OUT / ('matrix' + SUFFIX + '.json')).write_text(json.dumps(results, indent=2,
        default=lambda v: {'hex': v.hex()}) + '\n')
    print(index + 1, label, record['native']['outcome'], record['guest']['outcome'], flush=True)
