"""Explicit real-guest candidate gate; never substitutes for release acceptance."""
from concurrent.futures import ThreadPoolExecutor
import importlib.util
import os
from pathlib import Path

import mariamem
import pymysql
import pytest

HOST = os.environ.get('MARIAMEM_ROUTINE_HOST')
pytestmark = pytest.mark.skipif(not HOST, reason='requires explicit routine candidate host')


def sql(db, statement):
    with pymysql.connect(**db.connection_info(), autocommit=True) as connection:
        with connection.cursor() as cursor:
            cursor.execute(statement)
            rows = cursor.fetchall()
            while cursor.nextset():
                cursor.fetchall()
    db.wait_disconnected()
    return rows


def function(db, value):
    sql(db, f'CREATE OR REPLACE FUNCTION test.seed_value() RETURNS INT DETERMINISTIC RETURN {value}')


def value(db):
    return sql(db, 'SELECT test.seed_value()')


def test_fresh_context_and_native_matched_routine_cases(monkeypatch):
    # An ambient setting must not select Restore for a new DB.
    monkeypatch.setenv('MARIAMEM_BOOT_MODE', 'restore')
    with mariamem.start(host_binary=HOST) as db:
        context = sql(db, 'SELECT DATABASE(), @@character_set_connection, @@session.sql_mode, @@global.sql_mode')
        assert context[0][0:2] == ('test', 'utf8mb4'), context
        assert context[0][2] == context[0][3], context
        assert sql(db, "SELECT ENGINE FROM information_schema.TABLES WHERE TABLE_SCHEMA='mysql' AND TABLE_NAME='proc'") == (('Aria',),)
        assert sql(db, "SELECT COUNT(*) FROM information_schema.COLUMNS WHERE TABLE_SCHEMA='mysql' AND TABLE_NAME='proc'") == ((22,),)
        path = Path(__file__).resolve().parents[1] / 'tests/routine_cases.py'
        spec = importlib.util.spec_from_file_location('routine_feasibility', path)
        probe = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(probe)
        with pymysql.connect(**db.connection_info(), autocommit=True) as connection:
            with connection.cursor() as cursor:
                cases = probe.routines(cursor)
                assert len(cases) == 6 and all(case['result'] == 'PASS' for case in cases), cases
                event = probe.safe(cursor, 'CREATE EVENT test.candidate_event ON SCHEDULE EVERY 1 DAY DO SELECT 1')
                assert event.get('errno') == 1235, event


def test_routine_rows_child_isolation_recapture_and_owner_close():
    resources = []
    try:
        parent = mariamem.start(host_binary=HOST)
        resources.append(parent)
        function(parent, 7)
        baseline = parent.snapshot()
        resources.append(baseline)
        first, second = baseline.fork(), baseline.fork()
        resources.extend([first, second])
        assert value(first) == value(second) == ((7,),)
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(function, first, 70), pool.submit(function, second, 700)]
            for future in futures:
                future.result(timeout=60)
        assert value(first) == ((70,),) and value(second) == ((700,),)
        with baseline.fork() as third:
            assert value(third) == ((7,),)
        changed = first.snapshot()
        resources.append(changed)
        survivor = changed.fork()
        resources.append(survivor)
        changed.close()
        baseline.close()
        assert value(survivor) == ((70,),) and value(second) == ((700,),)
    finally:
        for resource in reversed(resources):
            resource.close()
    assert parent._session._refs == 0 and parent._session._reaped.is_set()
    assert parent._session._process.poll() == 0


@pytest.mark.parametrize('mutation,reason', [
    ('DROP TABLE mysql.proc', 'columns'),
    ('ALTER TABLE mysql.proc MODIFY comment TEXT COLLATE utf8mb3_bin NULL', 'column'),
    ('ALTER TABLE mysql.proc DROP PRIMARY KEY, ADD PRIMARY KEY(name,db,type)', 'primary'),
])
def test_incompatible_baseline_rejected_without_repair_and_sibling_survives(mutation, reason):
    with mariamem.start(host_binary=HOST) as source:
        function(source, 7)
        with source.snapshot() as good:
            with good.fork() as healthy, good.fork() as damaged:
                sql(damaged, mutation)
                with damaged.snapshot() as bad:
                    refs = bad._session._refs
                    for _ in range(2):
                        with pytest.raises(mariamem.HostError) as caught:
                            bad.fork()
                        message = str(caught.value)
                        assert 'routine_bootstrap' in message and reason in message, message
                        assert bad._session._refs == refs
                        assert value(healthy) == ((7,),)


def test_existing_1728_oracle_is_not_replaced_by_startup_check():
    with mariamem.start(host_binary=HOST) as db:
        sql(db, 'ALTER TABLE mysql.proc MODIFY comment TEXT COLLATE utf8mb3_bin NULL')
        with pytest.raises(pymysql.MySQLError) as caught:
            sql(db, 'CREATE PROCEDURE test.bad_definition() SELECT 1')
        assert caught.value.args[0] == 1728


@pytest.fixture(scope='session', autouse=True)
def record_candidate_environment():
    if not HOST:
        return
    import hashlib
    import importlib.metadata
    import json
    import platform
    import ssl
    import sys
    root = Path(__file__).resolve().parents[1]
    evidence = Path(os.environ.get('MARIAMEM_ROUTINE_EVIDENCE', str(root/'build/routine-ci')))
    evidence.mkdir(parents=True, exist_ok=True)
    record = dict(python=sys.version, system=platform.system(), machine=platform.machine(),
                  openssl=ssl.OPENSSL_VERSION, pymysql=importlib.metadata.version('PyMySQL'),
                  host_sha256=hashlib.sha256(Path(HOST).read_bytes()).hexdigest())
    (evidence/'runtime-environment.json').write_text(json.dumps(record, indent=2)+'\n')


def test_default_connector_python_routine_text_regression():
    """Text routine consumer gate; binary prepared adoption remains separate."""
    import importlib.metadata
    import json
    import ssl
    required = os.environ.get('MARIAMEM_ROUTINE_REQUIRE_CONNECTOR') == '1'
    if not hasattr(ssl, 'PROTOCOL_TLSv1'):
        reason = 'Connector/Python 26.7.0 import requires ssl.PROTOCOL_TLSv1; this OpenSSL build omits it'
        if required:
            pytest.fail(reason)
        pytest.skip(reason)
    if required:
        import mysql.connector as connector
    else:
        connector = pytest.importorskip('mysql.connector')
    assert importlib.metadata.version('mysql-connector-python') == '26.7.0'
    with mariamem.start(host_binary=HOST) as db:
        with connector.connect(**db.connection_info(), autocommit=True) as connection:
            with connection.cursor() as cursor:
                cursor.execute('CREATE FUNCTION test.connector_value() RETURNS INT DETERMINISTIC RETURN 17')
                cursor.execute('CREATE PROCEDURE test.connector_call() BEGIN SELECT 7; SELECT 8; END')
                cursor.execute('CALL test.connector_call()')
                rows = []
                while True:
                    if cursor.with_rows:
                        rows.append(cursor.fetchall())
                    if not cursor.nextset():
                        break
                assert rows == [[(7,)], [(8,)]], rows
            with connection.cursor() as cursor:
                cursor.execute('SELECT test.connector_value()+%s', (3,))
                assert cursor.fetchall() == [(20,)]
            evidence = Path(os.environ.get('MARIAMEM_ROUTINE_EVIDENCE', str(Path(__file__).resolve().parents[1]/'build/routine-ci')))
            evidence.mkdir(parents=True, exist_ok=True)
            (evidence/'connector-regression.json').write_text(json.dumps(dict(result='PASS', version=connector.__version__, default_connection=type(connection).__name__, text_call=rows, text_expression=20), indent=2)+'\n')
