"""Canonical current-runtime MySQL text-protocol and reconnect regressions.

Opt in through verify.py integration; forced process-containment experiments
remain diagnostics, not promises of the normal test database contract.
"""
import os
import time

import mariamem
import pymysql
import pytest
from pymysql.constants import CLIENT
from support import wire_acceptance


@pytest.fixture
def wire_db():
    host = os.environ.get("MARIAMEM_TEST_HOST")
    if not host or os.environ.get("MARIAMEM_TEST_DEFAULT") != "1":
        pytest.skip("requires current generated-Go integration host")
    with mariamem.start(host_binary=host) as db:
        yield db


def connect(db, **options):
    return pymysql.connect(**db.connection_info(), charset="utf8mb4",
                           autocommit=True, binary_prefix=True,
                           read_timeout=5, write_timeout=5, **options)


def execute(conn, sql):
    with conn.cursor() as cur:
        cur.execute(sql)
        return cur.fetchall()


def test_text_protocol_values_metadata_flags_and_error_recovery(wire_db):
    events = []
    with connect(wire_db) as conn:
        wire_acceptance.exercise(conn, events, api_version=2)
        conn.rollback()
    wire_acceptance.exercise_found_rows(wire_db.connection_info(), events)
    wire_db.wait_disconnected()
    # The shared oracle also exercises unsupported COM_STMT_PREPARE and then
    # proves that the same session remains usable; no SQL-only substitute.
    assert {e["check"] for e in events} >= {
        "typed_values_and_driver_parameters",
        "schema_discovery_enumeration_wildcard_create_drop",
        "begin_rollback_commit_autocommit_and_status",
        "native_insert_id_status_warnings_columns_duplicate_names_row_count_found_rows",
        "70kb_request_response_and_300_row_packet_sequence_wrap",
        "errors_then_continue_empty_result_and_prepare_rejection",
        "client_found_rows_semantics",
    }


@pytest.mark.parametrize("disconnect", ["quit", "tcp_eof"])
def test_reconnect_discards_uncommitted_and_session_state(wire_db, disconnect):
    conn = connect(wire_db)
    try:
        execute(conn, "CREATE TABLE reconnect_probe(id INT PRIMARY KEY, value INT) ENGINE=InnoDB")
        execute(conn, "INSERT INTO reconnect_probe VALUES(1, 7)")
        execute(conn, "SET @wire_marker=9876")
        execute(conn, "CREATE TEMPORARY TABLE session_only(id INT)")
        conn.begin()
        execute(conn, "UPDATE reconnect_probe SET value=99 WHERE id=1")
    finally:
        if disconnect == "quit":
            conn.close()
        else:
            conn._force_close()  # exercise EOF rather than COM_QUIT
    wire_db.wait_disconnected()
    with connect(wire_db) as fresh:
        assert execute(fresh, "SELECT @wire_marker, @@autocommit") == ((None, 1),)
        assert execute(fresh, "SELECT value FROM reconnect_probe") == ((7,),)
        with pytest.raises(pymysql.ProgrammingError) as error:
            execute(fresh, "SELECT * FROM session_only")
        assert error.value.args[0] == 1146
        assert execute(fresh, "SELECT 1") == ((1,),)
    wire_db.wait_disconnected()


def test_unsupported_host_request_preserves_ready_database(wire_db):
    with pytest.raises(mariamem.HostError):
        wire_db._request("unimplemented-test-op")
    assert wire_db.status()["state"] == "ready"
    with connect(wire_db) as conn:
        assert execute(conn, "SELECT 1") == ((1,),)
    wire_db.wait_disconnected()


def test_unsupported_handshake_flags_are_rejected_without_poisoning_host(wire_db):
    with pytest.raises(pymysql.MySQLError) as error:
        connect(wire_db, client_flag=CLIENT.MULTI_STATEMENTS)
    assert error.value.args[0] == 1235
    wire_db.wait_disconnected()
    with connect(wire_db) as conn:
        assert execute(conn, "SELECT 1") == ((1,),)
    wire_db.wait_disconnected()


def test_idle_connection_does_not_expire_at_query_deadline():
    host = os.environ.get("MARIAMEM_TEST_HOST")
    if not host or os.environ.get("MARIAMEM_TEST_DEFAULT") != "1":
        pytest.skip("requires current generated-Go integration host")
    with mariamem.start(host_binary=host, query_timeout=0.3) as db:
        with connect(db) as conn:
            time.sleep(0.6)
            assert execute(conn, "SELECT 1") == ((1,),)
        db.wait_disconnected()


def test_owner_eof_reaps_host_and_closes_wrapper(wire_db):
    assert len(wire_db.id) == 32
    assert wire_db.id != str(wire_db.diagnostics["host_pid"])
    conn = connect(wire_db)
    try:
        wire_db._process.stdin.close()
        assert wire_db._process.wait(timeout=5) == 0
    finally:
        conn._force_close()
        wire_db._dispose()
    assert wire_db._process.stdout.closed and wire_db._log.closed
    assert not wire_db._reader.is_alive()
