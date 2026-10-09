"""Consumer tests: the installed plugin supplies all mariamem fixtures."""
from pathlib import Path
import sys

import mariamem
import pymysql
import pytest


def execute(info, statement):
    with pymysql.connect(**info, autocommit=True) as conn:
        with conn.cursor() as cursor:
            cursor.execute(statement)
            return cursor.fetchall()


def test_defaults_and_cleanup():
    assert Path(mariamem.__file__).is_relative_to(Path(sys.prefix))
    with mariamem.start() as db:
        info = db.connection_info()
        info["port"] = 0
        assert db.connection_info()["port"] != 0
        assert execute(db.connection_info(), "SELECT 1") == ((1,),)
        temporary = db.log_path.parent
    assert db.closed and not temporary.exists()
    assert isinstance(db.logs, str)
    db.close()
    with pytest.raises(mariamem.HostError):
        db.connection_info()


def test_snapshot_defaults():
    with mariamem.start() as db:
        execute(db.connection_info(), "CREATE TABLE items(id INT) ENGINE=InnoDB")
        db.wait_disconnected()
        with db.snapshot() as saved:
            assert db.closed
            with saved.fork() as a, saved.fork() as b:
                execute(a.connection_info(), "INSERT INTO items VALUES(1)")
                a.wait_disconnected()
                assert execute(a.connection_info(), "SELECT COUNT(*) FROM items") == ((1,),)
                assert execute(b.connection_info(), "SELECT COUNT(*) FROM items") == ((0,),)
        with pytest.raises(ValueError, match="closed"):
            saved.fork()


def test_explicit_snapshot_persists(tmp_path):
    path = tmp_path / "saved"
    with mariamem.start() as db:
        with db.snapshot_to(path):
            pass
    with mariamem.load_snapshot(path) as reopened:
        with mariamem.start(snapshot=reopened) as db:
            assert execute(db.connection_info(), "SELECT 7") == ((7,),)
    assert path.exists()


@pytest.mark.parametrize("number", [1, 2])
def test_plugin_isolation(mariamem_connection_info, number):
    with pymysql.connect(**mariamem_connection_info) as conn:
        with conn.cursor() as cur:
            cur.execute("CREATE TABLE isolated(id INT) ENGINE=InnoDB")
            cur.execute("INSERT INTO isolated VALUES(%s)", (number,))
            conn.rollback()
            cur.execute("SELECT COUNT(*) FROM isolated")
            assert cur.fetchone() == (0,)
            cur.execute("INSERT INTO isolated VALUES(%s)", (number,))
            conn.commit()
            cur.execute("SELECT id FROM isolated")
            assert cur.fetchone() == (number,)


class TestIndependent:
    @pytest.mark.parametrize("value", [1, 2])
    def test_each_method_gets_a_database(self, mariamem_connection_info, value):
        # Both parameter instances must begin without a previous test's table.
        execute(mariamem_connection_info, "CREATE TABLE independent(id INT)")
        execute(mariamem_connection_info, f"INSERT INTO independent VALUES({value})")
        assert execute(mariamem_connection_info, "SELECT id FROM independent") == ((value,),)
