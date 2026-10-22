"""Bounded MariaDB Connector/Python replay; never accepts a native failure."""
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import sys

VERSION = '1.1.14'


def value(v):
    if isinstance(v, (bytes, bytearray)):
        return {'type': 'bytes', 'hex': bytes(v).hex()}
    if isinstance(v, (list, tuple)):
        return [value(x) for x in v]
    return v


def error(e):
    return {'type': type(e).__name__, 'errno': getattr(e, 'errno', None),
            'sqlstate': getattr(e, 'sqlstate', None), 'message': str(e)}


def status(c):
    q = c.cursor()
    try:
        q.execute("SHOW GLOBAL STATUS WHERE Variable_name IN ('Com_stmt_prepare','Com_stmt_execute')")
        return {row[0]: int(row[1]) for row in q.fetchall()}
    finally:
        q.close()


def require_binary(before, after):
    for key in ('Com_stmt_prepare', 'Com_stmt_execute'):
        assert key in before and key in after and after[key] > before[key], (key, before, after)


def capture(info, name):
    import mariadb
    r = {'result': 'FAIL', 'cursor_options': {'binary': True}, 'cleanup_errors': []}
    c = q = None
    try:
        r['stage'] = 'connect'
        c = mariadb.connect(**info, connect_timeout=5)
        setup = c.cursor()
        try:
            setup.execute('SELECT VERSION()')
            r['engine_version'] = setup.fetchone()[0]
            assert r['engine_version'].startswith('12.3.3'), r['engine_version']
            if name == 'prepared_call':
                setup.execute('DROP PROCEDURE IF EXISTS test.p5_mariadb_call')
                setup.execute('CREATE PROCEDURE test.p5_mariadb_call(IN x INT) BEGIN SELECT x; SELECT x+1; END')
        finally:
            setup.close()
        r['before'] = status(c)
        q = c.cursor(binary=True)
        r['stage'] = 'execute'
        if name == 'nul_projection':
            q.execute('SELECT ?, HEX(?), OCTET_LENGTH(?), CAST(? AS BINARY)', (b'A\0B',) * 4)
            row = q.fetchone()
            assert row is not None and q.fetchone() is None
            r['row'] = value(row)
            # Preserve returned types in the receipt; assert all three bytes,
            # not whether a driver chooses str or bytes for an untyped column.
            assert row[0] in ('A\0B', b'A\0B'), r['row']
            assert row[1] in ('410042', b'410042') and row[2] == 3, r['row']
            assert bytes(row[3]) == b'A\0B', r['row']
        else:
            q.execute('CALL test.p5_mariadb_call(?)', (7,))
            r['resultsets'] = []
            while True:
                r['stage'] = 'fetchall'
                if q.description:
                    r['resultsets'].append(value(q.fetchall()))
                r['stage'] = 'nextset'
                if not q.nextset():
                    r['terminal_drained'] = True
                    break
            assert r['resultsets'] == [[[7]], [[8]]], r['resultsets']
        r['after'] = status(c)
        require_binary(r['before'], r['after'])
        r['binary_execution_observed'] = True
        r['result'] = 'PASS'
        r.pop('stage', None)
    except Exception as e:
        r['error'] = error(e)
    finally:
        if c:
            # Check even after the primary failure; do not mask that error.
            following = None
            try:
                following = c.cursor()
                following.execute('SELECT 1')
                r['following_query'] = value(following.fetchall())
                assert r['following_query'] == [[1]], r['following_query']
            except Exception as e:
                r['following_query_error'] = error(e)
                r['result'] = 'FAIL'
            finally:
                for handle in (following, q, c):
                    if handle:
                        try:
                            handle.close()
                        except Exception as e:
                            r['cleanup_errors'].append(error(e))
                            r['result'] = 'FAIL'
    return r


def comparable(r):
    return {k: {n: v for n, v in c.items() if n not in ('engine_version', 'before', 'after')}
            for k, c in r['cases'].items()}


def require_nul(row):
    assert len(row) == 4
    assert row[0] in ('A\0B', {'type': 'bytes', 'hex': '410042'}), row
    assert row[1] in ('410042', {'type': 'bytes', 'hex': '343130303432'}), row
    assert row[2] == 3 and row[3] == {'type': 'bytes', 'hex': '410042'}, row


def require_complete(r):
    assert set(r['cases']) == {'nul_projection', 'prepared_call'}, 'missing case'
    assert r['result'] == 'PASS', 'probe failed'
    for c in r['cases'].values():
        assert c['result'] == 'PASS' and c.get('binary_execution_observed') is True
        assert c.get('following_query') == [[1]] and not c.get('cleanup_errors')
    require_nul(r['cases']['nul_projection']['row'])
    assert r['cases']['prepared_call']['resultsets'] == [[[7]], [[8]]]
    assert r['cases']['prepared_call']['terminal_drained'] is True


def main():
    p = argparse.ArgumentParser()
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument('--native-port', type=int)
    g.add_argument('--host', type=Path)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--reference', type=Path)
    a = p.parse_args()
    import mariadb
    assert importlib.metadata.version('mariadb') == VERSION
    import mariadb._mariadb as extension
    r = {'scope': 'two MariaDB driver cases only, not full P5 or adoption', 'result': 'FAIL',
         'environment': {'python': sys.version, 'os': platform.system(), 'architecture': platform.machine(),
                         'driver': VERSION, 'connector_c': mariadb.client_version_info,
                         'extension_sha256': hashlib.sha256(Path(extension.__file__).read_bytes()).hexdigest()},
         'cases': {}}
    if a.host:
        r['host_sha256'] = hashlib.sha256(a.host.read_bytes()).hexdigest()
    try:
        for name in ('nul_projection', 'prepared_call'):
            db = None
            try:
                if a.host:
                    import mariamem
                    db = mariamem.start(host_binary=str(a.host))
                    info = db.connection_info()
                else:
                    info = dict(host='127.0.0.1', port=a.native_port, user='root', database='test')
                r['cases'][name] = capture(info, name)
            except Exception as e:
                r['cases'][name] = {'result': 'FAIL', 'error': error(e)}
            finally:
                if db:
                    try:
                        try:
                            db.wait_disconnected(timeout=10)
                        finally:
                            db.close()
                    except Exception as e:
                        r['cases'][name].update(result='FAIL', host_cleanup_error=error(e))
        if all(c['result'] == 'PASS' for c in r['cases'].values()):
            r['result'] = 'PASS'
        require_complete(r)
        if a.reference:
            native = json.loads(a.reference.read_text())
            require_complete(native)
            assert comparable(r) == comparable(native), 'native/guest values or lifecycle differ'
            r['native_matching'] = 'PASS'
    except Exception as e:
        r.update(result='FAIL', error=error(e))
    finally:
        a.output.parent.mkdir(parents=True, exist_ok=True)
        a.output.write_text(json.dumps(r, indent=2) + '\n')
    if r['result'] != 'PASS':
        raise SystemExit(1)


if __name__ == '__main__':
    main()
