"""Small real-guest dev route gate, explicitly selected after bound compilation."""
import os
import mariamem
import pymysql
import pytest

HOST = os.environ.get('MARIAMEM_TEST_HOST')
pytestmark = pytest.mark.skipif(not HOST, reason='requires explicit compiled development host')


def test_dev_fresh_transactions_snapshot_children_and_close():
    children = []
    with mariamem.start(host_binary=HOST) as db:
        session = db._session
        children.append(db)
        with pymysql.connect(**db.connection_info()) as c:
            with c.cursor() as q:
                q.execute('SELECT 1')
                assert q.fetchone() == (1,)
                q.execute('CREATE TABLE dev_items(id INT PRIMARY KEY) ENGINE=InnoDB')
                q.execute('INSERT INTO dev_items VALUES(1)')
                c.commit()
                q.execute('INSERT INTO dev_items VALUES(2)')
                c.rollback()
                q.execute('SELECT id FROM dev_items ORDER BY id')
                assert q.fetchall() == ((1,),)
        # TCP close and server-side cleanup are distinct. Snapshot deliberately
        # rejects a still-active connection; wait through the supported API.
        db.wait_disconnected()
        with db.snapshot() as baseline:
            for index in range(3):
                with baseline.fork(host_binary=HOST) as child:
                    children.append(child)
                    assert child._session is session
                    with pymysql.connect(**child.connection_info(), autocommit=True) as c:
                        with c.cursor() as q:
                            q.execute('SELECT id FROM dev_items')
                            assert q.fetchall() == ((1,),)
                            q.execute('INSERT INTO dev_items VALUES(%s)', (index+10,))
                # The baseline still owns the shared host after each child closes.
                assert child.closed and session._process.poll() is None
        assert db._closed
    for child in children:
        assert child.closed and not child.log_path.exists()
    assert session._refs == 0 and session._reaped.is_set()
    assert session._process.poll() == 0
    assert session._process.stdin.closed and session._process.stdout.closed
    assert session._stderr.closed and not session._reader.is_alive()
    assert not session.root.exists()
