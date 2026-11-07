"""Run outside the checkout with the installed UNQUALIFIED candidate wheel."""
import json
from pathlib import Path
import mariamem
import pymysql


def connect(db):
    return pymysql.connect(**db.connection_info(), autocommit=True)


def main():
    db = mariamem.start(query_timeout=0.15)
    peer = mariamem.start()
    session = db._session
    try:
        with connect(db) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT %s + %s", (13, 29))
                assert cursor.fetchone() == (42,)
                try:
                    cursor.execute("SELECT * FROM no_such_public_table")
                except pymysql.err.ProgrammingError:
                    pass
                else:
                    raise AssertionError("ordinary SQL error missing")
                cursor.execute("SELECT 17")
                assert cursor.fetchone() == (17,)
        db.wait_disconnected()
        assert db.status()["state"] == "ready"
        try:
            with connect(db) as connection:
                with connection.cursor() as cursor:
                    cursor.execute("DO SLEEP(2)")
        except pymysql.err.OperationalError as error:
            assert error.args[0] in (2006, 2013), error
        else:
            raise AssertionError("native timeout did not close stream")
        try:
            db.status()
        except mariamem.HostError as error:
            assert error.code == "unusable", error
            assert "deadline" in str(error), error
        else:
            raise AssertionError("owner lost native failure")
        with connect(peer) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 23")
                assert cursor.fetchone() == (23,)
    finally:
        # A fatal source preserves its operation error through cleanup.
        try:
            db.close()
        except mariamem.HostError:
            pass
        peer.close()
    assert session._process.poll() is not None
    assert not session.root.exists()
    print(json.dumps({"result": "PASS_PUBLIC_PYTHON", "module": str(Path(mariamem.__file__).resolve()),
                      "normal_sql_error_survives": True, "fatal_wire_eof": True,
                      "owner_original_cause": True, "independent_instance": True,
                      "managed_host_reaped": True, "temporary_removed": True}))


if __name__ == "__main__":
    main()
