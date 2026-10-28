#!/usr/bin/env python3
"""Fresh native reference / both-host guest parity for the finite issue #5 matrix."""
import argparse
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from git_identity import require_commit, verify_go_binary

TYPES = ('VARCHAR(32)', 'VARCHAR(255)', 'VARBINARY(255)', 'VARCHAR(1000)',
         'VARCHAR(2000)', 'TINYTEXT', 'TEXT', 'MEDIUMTEXT', 'LONGTEXT', 'BLOB')
SHAPES = (
    ('empty', ('DELETE FROM t',), 'SELECT DISTINCT customer FROM t'),
    ('one', ('DELETE FROM t WHERE id=2',), 'SELECT DISTINCT customer FROM t'),
    ('limit', (), 'SELECT DISTINCT customer FROM t LIMIT 1'),
    ('distinct_order', (), 'SELECT DISTINCT customer FROM t ORDER BY customer'),
    ('multi_column', (), 'SELECT DISTINCT id, customer FROM t'),
    ('union', (), 'SELECT customer FROM t UNION SELECT customer FROM t'),
    ('derived', (), 'SELECT * FROM (SELECT DISTINCT customer FROM t) x'),
    ('group', (), 'SELECT customer FROM t GROUP BY customer'),
    ('ctas', (), 'CREATE TABLE cn AS SELECT DISTINCT customer FROM t'),
    ('insert', ('CREATE TABLE dst LIKE t',), 'INSERT INTO dst(customer) SELECT DISTINCT customer FROM t'),
    ('view', ('CREATE VIEW v AS SELECT DISTINCT customer FROM t',), 'SELECT * FROM v'),
    ('index', ('ALTER TABLE t ADD INDEX (customer(10))',), 'SELECT DISTINCT customer FROM t'),
    ('count', (), 'SELECT COUNT(DISTINCT customer) FROM t'),
    ('union_all', (), 'SELECT customer FROM t UNION ALL SELECT customer FROM t'),
    ('big_result', (), 'SELECT SQL_BIG_RESULT DISTINCT customer FROM t'),
    ('cast', (), 'SELECT DISTINCT CAST(customer AS CHAR(255)) FROM t'),
    ('aggregate', (), 'SELECT customer, COUNT(*) FROM t GROUP BY customer'),
    ('order', (), 'SELECT customer FROM t ORDER BY customer'),
)
CASES = [(kind, kind, (), 'SELECT DISTINCT customer FROM t') for kind in TYPES]
CASES += [(name, 'TEXT', setup, sql) for name, setup, sql in SHAPES]


def encoded(value):
    return json.loads(json.dumps(value, default=lambda item: {'hex': item.hex()}))


def observe(args, kind, setup, sql):
    import pymysql
    with pymysql.connect(**args, autocommit=True, read_timeout=5) as connection:
        with connection.cursor() as cursor:
            cursor.execute('CREATE TABLE t(id INT, customer ' + kind + ')')
            cursor.execute("INSERT INTO t VALUES(1,'alice'),(2,'bob')")
            for command in setup:
                cursor.execute(command)
            cursor.execute(sql)
            rows, affected = encoded(cursor.fetchall()), cursor.rowcount
            # DDL/DML must actually produce the intended deduplicated table.
            # Preserve the same independent check on the native reference.
            if sql.startswith('CREATE TABLE cn '):
                cursor.execute('SELECT * FROM cn')
                materialized = encoded(cursor.fetchall())
            elif sql.startswith('INSERT INTO dst'):
                cursor.execute('SELECT customer FROM dst')
                materialized = encoded(cursor.fetchall())
            else:
                materialized = None
            cursor.execute('SELECT 1')
            assert cursor.fetchall() == ((1,),), 'session failed after duplicate removal'
            return {'rows': rows, 'affected': affected, 'materialized': materialized}


def canonical(result):
    def ordered(rows):
        return sorted(json.dumps(row, sort_keys=True) for row in rows) if rows is not None else None
    return result['affected'], ordered(result['rows']), ordered(result['materialized'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('native', 'guest'))
    parser.add_argument('--source-commit', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--port', type=int, default=33315)
    parser.add_argument('--native-image')
    parser.add_argument('--reference', type=Path)
    parser.add_argument('--host', type=Path)
    args = parser.parse_args()
    require_commit(ROOT, args.source_commit)
    if subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip() != args.source_commit:
        parser.error('source_commit is not HEAD')
    if subprocess.check_output(['git', 'status', '--porcelain'], cwd=ROOT, text=True).strip():
        parser.error('requires clean source; put output under ignored build/')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    result = {'source_commit': args.source_commit, 'platform': platform.platform(),
              'case_spec_sha256': hashlib.sha256(json.dumps(CASES).encode()).hexdigest(), 'cases': []}
    if args.mode == 'native':
        import pymysql
        connection_args = dict(host='127.0.0.1', port=args.port, user='root')
        result['native_image'] = args.native_image
        with pymysql.connect(**connection_args, autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute('SELECT VERSION()')
                result['server_version'] = cursor.fetchone()[0]
        if result['server_version'] != '12.3.3-MariaDB-ubu2404':
            raise ValueError('unexpected native server: ' + result['server_version'])
    else:
        if not args.host or not args.reference:
            parser.error('guest mode requires --host and --reference')
        verify_go_binary(ROOT, args.host, args.source_commit)
        reference = json.loads(args.reference.read_text())
        if (reference['source_commit'] != args.source_commit or reference.get('result') != 'PASS'
                or reference['case_spec_sha256'] != result['case_spec_sha256']
                or len(reference['cases']) != len(CASES)):
            raise ValueError('reference identity/spec/completeness differs')
        result['reference_sha256'] = hashlib.sha256(args.reference.read_bytes()).hexdigest()
        result['host_sha256'] = hashlib.sha256(args.host.read_bytes()).hexdigest()
        sys.path.insert(0, str(ROOT / 'python'))
        import mariamem
    try:
        for index, (name, kind, setup, sql) in enumerate(CASES):
            if args.mode == 'native':
                with pymysql.connect(**connection_args, autocommit=True) as connection:
                    with connection.cursor() as cursor:
                        cursor.execute('DROP DATABASE IF EXISTS issue5_acceptance')
                        cursor.execute('CREATE DATABASE issue5_acceptance')
                observation = observe({**connection_args, 'database': 'issue5_acceptance'}, kind, setup, sql)
            else:
                with mariamem.start(host_binary=args.host, query_timeout=1, shutdown_timeout=2) as db:
                    observation = observe(db.connection_info(), kind, setup, sql)
                    db.wait_disconnected()
                expected = reference['cases'][index]
                if expected['name'] != name or canonical(observation) != canonical(expected['observation']):
                    raise AssertionError(f'native/guest mismatch: {name}: {observation} != {expected}')
            result['cases'].append({'name': name, 'observation': observation})
            print(name, 'PASS', flush=True)
        result['result'] = 'PASS'
    except Exception as error:
        result['result'] = 'FAIL'
        result['error'] = str(error)
        raise
    finally:
        args.output.write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    main()
