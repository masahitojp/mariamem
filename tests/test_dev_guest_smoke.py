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
        db.wait_disconnected()
        assert db.status()["active_connections"] == 0
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
    # Since shared-host adoption, Session owns the process, pipes and reader.
    # All root/baseline/child owners have left their scopes at this point.
    for child in children:
        assert child.closed
        session = child._session
        assert session._refs == 0 and session._reaped.is_set()
        assert session._process.poll() == 0
        assert session._process.stdin.closed and session._process.stdout.closed
        assert session._stderr.closed and not session._reader.is_alive()
        assert not session.root.exists()
