"""Real canonical guest: child-to-snapshot inheritance and disposal."""
import os
import mariamem
import pymysql
import pytest

pytestmark = pytest.mark.skipif(not os.environ.get("MARIAMEM_TEST_HOST"), reason="requires explicit canonical host")


def test_uca_child_resnapshot_keeps_collation_rows_and_original_parent():
    host = os.environ['MARIAMEM_TEST_HOST']
    def rows(db, sql):
        with pymysql.connect(**db.connection_info(), autocommit=True, charset='utf8mb4') as c:
            with c.cursor() as q:
                q.execute(sql)
                return q.fetchall()
    with mariamem.start(host_binary=host) as db:
        session = db._session
        rows(db, 'CREATE TABLE uca_items(id INT PRIMARY KEY, v VARCHAR(30) CHARACTER SET utf8mb4 COLLATE utf8mb4_uca1400_ai_ci) ENGINE=InnoDB')
        rows(db, "INSERT INTO uca_items VALUES(1,'café')")
        db.wait_disconnected()
        with db.snapshot(max_forks=2) as baseline:
            with baseline.fork(host_binary=host) as child:
                rows(child, "INSERT INTO uca_items VALUES(2,'cafe')")
                child.wait_disconnected()
                with child.snapshot(max_forks=1) as derived:
                    with derived.fork(host_binary=host) as grandchild:
                        assert rows(grandchild, "SELECT COUNT(*) FROM uca_items WHERE v='CAFE'") == ((2,),)
            with baseline.fork(host_binary=host) as pristine:
                assert rows(pristine, 'SELECT id FROM uca_items ORDER BY id') == ((1,),)
    assert session._refs == 0 and session._reaped.is_set()
    assert session._process.poll() == 0 and not session.root.exists()
