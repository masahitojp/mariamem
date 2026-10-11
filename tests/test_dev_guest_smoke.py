"""Small real-guest dev route gate, explicitly selected after bound compilation."""
import os
import json
from pathlib import Path
import shutil
import mariamem
import pymysql
import pytest

HOST = os.environ.get('MARIAMEM_TEST_HOST')
pytestmark = pytest.mark.skipif(not HOST, reason='requires explicit compiled development host')


def test_dev_fresh_transactions_snapshot_children_and_close():
    children = []
    with mariamem.start(host_binary=HOST) as db:
        children.append(db)
        with pymysql.connect(**db.connection_info()) as c:
            with c.cursor() as q:
                q.execute('SELECT 1')
                assert q.fetchone() == (1,)
                q.execute('SELECT VERSION()')
                version = q.fetchone()[0]
                expected = os.environ.get('MARIAMEM_DEV_EXPECTED_VERSION')
                if expected:
                    assert version.startswith(expected), version
                handshake = os.environ.get('MARIAMEM_DEV_EXPECTED_HANDSHAKE_VERSION')
                if handshake:
                    assert c.get_server_info().startswith(handshake), c.get_server_info()
                evidence = os.environ.get('MARIAMEM_DEV_SQL_VERSION_EVIDENCE')
                if evidence:
                    Path(evidence).write_text(json.dumps({'sql_version': version,
                        'wire_handshake_version': c.get_server_info()}) + '\n')
                q.execute('CREATE TABLE dev_items(id INT PRIMARY KEY) ENGINE=InnoDB')
                q.execute('INSERT INTO dev_items VALUES(1)')
                c.commit()
                q.execute('INSERT INTO dev_items VALUES(2)')
                c.rollback()
                q.execute('SELECT id FROM dev_items ORDER BY id')
                assert q.fetchall() == ((1,),)
        with db.snapshot() as baseline:
            for index in range(3):
                with baseline.fork(host_binary=HOST) as child:
                    children.append(child)
                    with pymysql.connect(**child.connection_info(), autocommit=True) as c:
                        with c.cursor() as q:
                            q.execute('SELECT id FROM dev_items')
                            assert q.fetchall() == ((1,),)
                            q.execute('INSERT INTO dev_items VALUES(%s)', (index+10,))
        assert db._closed
    for child in children:
        assert child._process.poll() is not None
        assert child._process.stdin.closed and child._process.stdout.closed and child._log.closed
        assert not child._reader.is_alive()


def test_dev_persist_load_source_detach_and_child_baselines(tmp_path):
    path = tmp_path / 'prepared'
    with mariamem.start(host_binary=HOST) as db:
        with pymysql.connect(**db.connection_info(), autocommit=True) as c:
            with c.cursor() as q:
                q.execute('CREATE TABLE origin(id INT PRIMARY KEY) ENGINE=InnoDB')
                q.execute('INSERT INTO origin VALUES(1)')
        with db.snapshot_to(path):
            pass
    with mariamem.load_snapshot(path, host_binary=HOST) as original:
        shutil.rmtree(path)
        with original.fork(host_binary=HOST) as changed:
            with pymysql.connect(**changed.connection_info(), autocommit=True) as c:
                with c.cursor() as q:
                    q.execute('INSERT INTO origin VALUES(2)')
            with changed.snapshot() as new:
                with new.fork(host_binary=HOST) as child:
                    with pymysql.connect(**child.connection_info(), autocommit=True) as c:
                        with c.cursor() as q:
                            q.execute('SELECT id FROM origin ORDER BY id')
                            assert q.fetchall() == ((1,), (2,))
        with original.fork(host_binary=HOST) as sibling:
            with pymysql.connect(**sibling.connection_info(), autocommit=True) as c:
                with c.cursor() as q:
                    q.execute('SELECT id FROM origin ORDER BY id')
                    assert q.fetchall() == ((1,),)
