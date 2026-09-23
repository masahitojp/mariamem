"""MySQL text protocol regression cases, promoted from the initial investigation."""
import datetime
import time
from decimal import Decimal
import pymysql

def exercise(conn, events, api_version=1):
    conn.ping(reconnect=False)
    conn.select_db("test")
    with conn.cursor() as cur:
        cur.execute("SELECT 1 AS one, VERSION() AS version")
        one, version = cur.fetchone()
        assert one == 1 and version == "13.1.0-MariaDB-embedded", (one, version)
        cur.execute("CREATE TABLE wire_probe (id INT PRIMARY KEY AUTO_INCREMENT, "
                    "txt VARCHAR(80), b VARBINARY(16), n INT NULL, amount DECIMAL(10,2), "
                    "dt DATETIME, u BIGINT UNSIGNED) ENGINE=InnoDB")
        values = ("日本語🙂 ' \\", b"\x00\xff\x27\x5c", None, Decimal("123.45"),
                  datetime.datetime(2026, 9, 22, 3, 4, 5), 18446744073709551615)
        assert cur.execute("INSERT INTO wire_probe(txt,b,n,amount,dt,u) VALUES (%s,%s,%s,%s,%s,%s)", values) == 1
        assert cur.rowcount == 1
        if api_version == 2:
            assert cur.lastrowid == 1, cur.lastrowid
            cur.execute("SELECT ROW_COUNT()")
            assert cur.fetchone() == (1,)
        cur.execute("SELECT txt,b,n,amount,dt,u FROM wire_probe WHERE id=%s", (1,))
        row = cur.fetchone()
        assert row == values, (row, values)
        events.append({"check": "typed_values_and_driver_parameters", "passed": True,
                       "types": [type(value).__name__ for value in row]})
        cur.execute("SELECT LAST_INSERT_ID()")
        assert cur.fetchone() == (1,)
        # Test engine semantics; protocol lastrowid is explicitly unsupported.
        cur.execute("SELECT ENGINE FROM information_schema.TABLES WHERE TABLE_SCHEMA='test' AND TABLE_NAME='wire_probe'")
        assert cur.fetchone() == ("InnoDB",)
        cur.execute("SET @wire_marker=9876")
        conn.begin()
        assert conn.server_status & 1
        assert cur.execute("UPDATE wire_probe SET txt='rollback' WHERE id=1") == 1
        conn.rollback()
        assert not conn.server_status & 1
        cur.execute("SELECT txt FROM wire_probe WHERE id=1")
        assert cur.fetchone() == (values[0],)
        conn.autocommit(False)
        assert not conn.get_autocommit()
        cur.execute("INSERT INTO wire_probe(id,txt) VALUES (2,'committed')")
        assert conn.server_status & 1
        conn.commit()
        assert not conn.server_status & 1
        conn.autocommit(True)
        assert conn.get_autocommit()
        events.append({"check": "begin_rollback_commit_autocommit_and_status", "passed": True})
        errors = [("INSERT INTO wire_probe(id) VALUES (1)", 1062), ("SELEC invalid", 1064),
                  ("SELECT 1; SELECT 2", 1064 if api_version == 2 else 1235)]
        if api_version == 1:
            errors.append(("SELECT 1 AS duplicate, 2 AS duplicate", 1235))
        for sql, errno in errors:
            try:
                cur.execute(sql)
                raise AssertionError(f"expected MySQL error {errno}")
            except pymysql.MySQLError as error:
                assert error.args[0] == errno, error
                events.append({"check": "mysql_error", "sql": sql, "errno": errno})
        cur.execute("SELECT @wire_marker, COUNT(*) FROM wire_probe")
        assert cur.fetchone() == (9876, 2)
        cur.execute("SELECT id FROM wire_probe WHERE id=-1")
        assert cur.fetchall() == ()
        assert len(cur.description) == 1
        if api_version == 2:
            cur.execute("SELECT 1 AS duplicate, 2 AS duplicate")
            assert cur.fetchone() == (1, 2)
            assert [d[0] for d in cur.description] == ["duplicate", "duplicate"]
            cur.execute("SELECT %s AS punctuation", ("a;b",))
            assert cur.fetchone() == ("a;b",)
            cur.execute("SELECT amount AS money, txt AS renamed FROM wire_probe AS w WHERE id=1")
            money, renamed = cur._result.fields
            assert money.scale == 2 and money.length == 12, (money.scale, money.length)
            assert (money.db, money.table_name, money.org_table, money.name, money.org_name) == (b"test", "w", "wire_probe", "money", "amount")
            assert renamed.length == 320 and renamed.org_name == "txt", (renamed.length, renamed.org_name)
            cur.execute("SELECT SQL_CALC_FOUND_ROWS id FROM wire_probe LIMIT 1")
            assert len(cur.fetchall()) == 1
            cur.execute("SELECT FOUND_ROWS()")
            assert cur.fetchone() == (2,)
            cur.execute("SELECT CAST('not-a-number' AS UNSIGNED)")
            assert cur.fetchone() == (0,)
            assert cur.warning_count == 1, cur.warning_count
            cur.execute("SHOW WARNINGS")
            assert cur.fetchone()[1] == 1292
            cur.execute("UPDATE wire_probe SET txt='committed' WHERE id=2")
            assert cur.lastrowid == 0, cur.lastrowid
            cur.execute("SELECT ROW_COUNT()")
            assert cur.fetchone() == (0,)
            events.append({"check": "native_insert_id_status_warnings_columns_duplicate_names_row_count_found_rows", "passed": True})
        cur.execute("SELECT %s AS large_value", ("x" * 70000,))
        assert cur.fetchone() == ("x" * 70000,)
        cur.execute("WITH RECURSIVE sequence(n) AS (SELECT 1 UNION ALL SELECT n+1 FROM sequence WHERE n<300) SELECT n FROM sequence")
        assert cur.fetchall() == tuple((n,) for n in range(1, 301))
        events.append({"check": "70kb_request_response_and_300_row_packet_sequence_wrap", "passed": True})
        # PyMySQL sends COM_STMT_PREPARE only through this low-level entry;
        # normal cursor parameters above are client-side escaping + COM_QUERY.
        conn._execute_command(22, "SELECT ?")
        try:
            conn._read_packet()
            raise AssertionError("prepared statements must be explicitly rejected")
        except pymysql.MySQLError as error:
            assert error.args[0] == 1235
        cur.execute("SELECT 7")
        assert cur.fetchone() == (7,)
        events.append({"check": "errors_then_continue_empty_result_and_prepare_rejection", "passed": True})
        start = time.monotonic()
        for _ in range(100):
            cur.execute("SELECT @wire_marker")
            assert cur.fetchone() == (9876,)
        events.append({"check": "100_queries_same_session", "passed": True,
                       "seconds": round(time.monotonic() - start, 4)})
        conn.begin()
        cur.execute("UPDATE wire_probe SET txt='pending-on-disconnect' WHERE id=2")
