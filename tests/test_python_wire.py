"""Canonical current-runtime MySQL text-protocol and reconnect regressions.

Opt in through verify.py integration; forced process-containment experiments
remain diagnostics, not promises of the normal test database contract.
"""
import os
from pathlib import Path
import time

import mariamem
import pymysql
import pytest
from pymysql.constants import CLIENT
from support import wire_acceptance


@pytest.fixture
def wire_host():
    host = os.environ.get("MARIAMEM_TEST_HOST")
    if not host or os.environ.get("MARIAMEM_TEST_DEFAULT") != "1":
        pytest.skip("requires current generated-Go integration host")
    return host


@pytest.fixture
def wire_db(wire_host):
    with mariamem.start(host_binary=wire_host) as db:
        yield db


def connect(db, **options):
    return pymysql.connect(**db.connection_info(), charset="utf8mb4",
                           autocommit=True, binary_prefix=True,
                           read_timeout=5, write_timeout=5, **options)


def execute(conn, sql):
    with conn.cursor() as cur:
        cur.execute(sql)
        return cur.fetchall()


def test_dump_statement_at_text_wire_limit(wire_db, tmp_path):
    # Exercise the real 1 MiB budget through import_dump, wire and guest, rather
    # than only a parser constant or a mocked connection.
    corpus = Path(__file__).parent/'dump_import_acceptance/input/application.sql'
    prefix = b"INSERT INTO `dump_boundary` VALUES ('"
    suffix = b"')"
    value_size = 1024 * 1024 - len(prefix) - len(suffix)
    statement = prefix + b'x' * value_size + suffix
    path = tmp_path/'boundary.sql'
    path.write_bytes(corpus.read_bytes() +
        b'\nCREATE TABLE `dump_boundary` (`value` MEDIUMTEXT) ENGINE=InnoDB;' +
        statement + b';')
    assert mariamem.import_dump(wire_db, path) == 92
    with connect(wire_db) as connection:
        assert execute(connection, 'SELECT OCTET_LENGTH(value) FROM app.dump_boundary') == ((value_size,),)
    wire_db.wait_disconnected()


@pytest.mark.parametrize("kind", ["VARCHAR(1000)", "TEXT", "BLOB"])
def test_text_blob_duplicate_removal_returns_and_preserves_sessions(kind):
    host = os.environ.get("MARIAMEM_TEST_HOST")
    if not host or os.environ.get("MARIAMEM_TEST_DEFAULT") != "1":
        pytest.skip("requires current generated-Go integration host")
    # A broken worker must fail this regression quickly, with bounded teardown.
    with mariamem.start(host_binary=host, query_timeout=1) as db:
        with connect(db) as conn, connect(db) as sibling:
            execute(conn, f"CREATE TABLE dedup_probe(value {kind})")
            execute(conn, "INSERT INTO dedup_probe VALUES('alice'),('bob'),('alice')")
            expected = ((b"alice",), (b"bob",)) if kind == "BLOB" else (("alice",), ("bob",))
            assert tuple(sorted(execute(conn, "SELECT DISTINCT value FROM dedup_probe"))) == expected
            assert tuple(sorted(execute(conn, "SELECT value FROM dedup_probe UNION SELECT value FROM dedup_probe"))) == expected
            assert tuple(sorted(execute(conn, "SELECT value FROM dedup_probe GROUP BY value"))) == expected
            execute(conn, "CREATE TABLE dedup_copy AS SELECT DISTINCT value FROM dedup_probe")
            assert tuple(sorted(execute(conn, "SELECT value FROM dedup_copy"))) == expected
            assert execute(conn, "SELECT 1") == ((1,),)
            assert execute(sibling, "SELECT 2") == ((2,),)


@pytest.mark.parametrize("user,password", [
    ("root", ""), ("test", "test"), ("root", "root"), ("test", ""),
    ("application", "synthetic-test-secret"),
])
def test_placeholder_credentials_accept_normal_queries(wire_db, user, password):
    info = wire_db.connection_info()
    assert info["user"] == "root" and info["password"] == ""
    info.update(user=user, password=password)
    with pymysql.connect(**info, autocommit=True, read_timeout=5, write_timeout=5) as conn:
        assert execute(conn, "SELECT 1") == ((1,),)
        execute(conn, "CREATE TABLE credential_probe(id INT PRIMARY KEY)")
        execute(conn, "INSERT INTO credential_probe VALUES(42)")
        assert execute(conn, "SELECT id FROM credential_probe") == ((42,),)
    wire_db.wait_disconnected()


def test_handshake_identity_matches_guest_across_sessions(wire_db):
    def check(conn):
        ((connection_id, version),) = execute(conn, "SELECT CONNECTION_ID(), VERSION()")
        assert conn.thread_id() == connection_id
        assert conn.get_server_info() == version
        return connection_id

    with connect(wire_db) as first, connect(wire_db) as second:
        assert check(first) != check(second)
    wire_db.wait_disconnected()
    with connect(wire_db) as reconnected:
        check(reconnected)
    wire_db.wait_disconnected()


def test_text_protocol_values_metadata_flags_and_error_recovery(wire_db):
    events = []
    with connect(wire_db) as conn:
        wire_acceptance.exercise(conn, events, api_version=2, prepared=True)
        conn.rollback()
    wire_acceptance.exercise_found_rows(wire_db.connection_info(), events)
    wire_db.wait_disconnected()
    # The shared oracle checks actual PREPARE metadata, RESET/CLOSE and then
    # proves that the same session remains usable; no SQL-only substitute.
    assert {e["check"] for e in events} >= {
        "typed_values_and_driver_parameters",
        "schema_discovery_enumeration_wildcard_create_drop",
        "begin_rollback_commit_autocommit_and_status",
        "native_insert_id_status_warnings_columns_duplicate_names_row_count_found_rows",
        "70kb_request_response_and_300_row_packet_sequence_wrap",
        "errors_then_continue_empty_result_and_prepare_lifecycle",
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


def _recv_exact(sock, n):
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        assert chunk, f"unexpected EOF after {len(buf)}/{n} bytes"
        buf.extend(chunk)
    return bytes(buf)


def _read_mysql_packet(sock):
    hdr = _recv_exact(sock, 4)
    length = hdr[0] | (hdr[1] << 8) | (hdr[2] << 16)
    seq = hdr[3]
    return seq, _recv_exact(sock, length)


def test_unsupported_handshake_flags_are_rejected_without_poisoning_host(wire_db):
    import socket, struct
    info = wire_db.connection_info()
    # Send an actual SSLRequest packet (CLIENT_SSL=0x0800); MariaDB 12.3.4 without
    # TLS rejects it with 1043/08S01 Bad handshake without poisoning the instance.
    with socket.create_connection((info["host"], info["port"]), timeout=5) as sock:
        sock.settimeout(5)
        _, greeting = _read_mysql_packet(sock)
        assert greeting
        body = struct.pack("<IIB23s", 0x0000A200 | int(CLIENT.SSL), 16 * 1024 * 1024, 45, b"\x00" * 23)
        sock.sendall(struct.pack("<I", len(body))[:3] + b"\x01" + body)
        _, resp = _read_mysql_packet(sock)
        assert len(resp) >= 3 and resp[0] == 0xFF
        assert int.from_bytes(resp[1:3], "little") == 1043
    wire_db.wait_disconnected()
    with connect(wire_db) as conn:
        assert execute(conn, "SELECT 1") == ((1,),)
    wire_db.wait_disconnected()


def test_same_connection_rejects_one_mib_plus_one_after_accepting_one_mib(wire_db):
    """P1-5: After expanding net->buff for an exact 1 MiB SQL, the same connection
    must still reject 1 MiB + 1 byte with 1153/08S01 before receiving the body."""
    import socket, struct
    info = wire_db.connection_info()
    with socket.create_connection((info["host"], info["port"]), timeout=5) as sock:
        sock.settimeout(5)
        _, greeting = _read_mysql_packet(sock)
        assert greeting
        # HandshakeResponse41 (no password, root@test)
        flags = 1 | 8 | 512 | 32768 | 524288
        auth = struct.pack("<IIB23s", flags, 16 * 1024 * 1024, 45, b"\x00" * 23) + b"root\x00\x00test\x00mysql_native_password\x00"
        sock.sendall(struct.pack("<I", len(auth))[:3] + b"\x01" + auth)
        _, ok = _read_mysql_packet(sock)
        assert ok and ok[0] == 0x00

        # 1. Exact 1 MiB SQL body (1,048,576 B) -> packet length 1,048,577 -> accepted.
        prefix = b"SELECT '"
        suffix = b"'"
        sql_1m = prefix + b"a" * (1048576 - len(prefix) - len(suffix)) + suffix
        assert len(sql_1m) == 1048576
        payload = b"\x03" + sql_1m
        sock.sendall(struct.pack("<I", len(payload))[:3] + b"\x00" + payload)
        # Drain result set (col count, col def, EOF, row, EOF).
        _, first = _read_mysql_packet(sock)
        assert first and first[0] != 0xFF
        eofs = 0
        while eofs < 2:
            _, pkt = _read_mysql_packet(sock)
            assert pkt and pkt[0] != 0xFF
            if pkt[0] == 0xFE and len(pkt) < 9:
                eofs += 1

        # 2. On the EXACT SAME connection, send ONLY the 4-byte header for 1 MiB + 1 B
        #    SQL (packet length 1,048,578) WITHOUT sending the body -> must get 1153.
        over_len = 1 + 1048576 + 1
        sock.sendall(struct.pack("<I", over_len)[:3] + b"\x00")
        _, err_pkt = _read_mysql_packet(sock)
        assert len(err_pkt) >= 9 and err_pkt[0] == 0xFF
        assert int.from_bytes(err_pkt[1:3], "little") == 1153
        assert err_pkt[3:9] == b"#08S01"
    wire_db.wait_disconnected()
    with connect(wire_db) as conn:
        assert execute(conn, "SELECT 1") == ((1,),)
    wire_db.wait_disconnected()


def test_compressed_multi_command_enforces_query_timeout_on_second_command(wire_host):
    """P1-4: A second command extracted from CLIENT_COMPRESS net->remain_in_buf
    must still go through admit() so query_timeout is armed and enforced."""
    import socket, struct, zlib
    with mariamem.start(host_binary=wire_host, query_timeout=0.25, shutdown_timeout=2) as db:
        info = db.connection_info()
        with socket.create_connection((info["host"], info["port"]), timeout=5) as sock:
            sock.settimeout(5)
            _, greeting = _read_mysql_packet(sock)
            assert greeting
            # HandshakeResponse41 with CLIENT_COMPRESS (0x0020)
            flags = 1 | 8 | 32 | 512 | 32768 | 524288
            auth = struct.pack("<IIB23s", flags, 16 * 1024 * 1024, 45, b"\x00" * 23) + b"root\x00\x00test\x00mysql_native_password\x00"
            sock.sendall(struct.pack("<I", len(auth))[:3] + b"\x01" + auth)
            _, ok = _read_mysql_packet(sock)
            assert ok and ok[0] == 0x00

            # Pack COM_STMT_CLOSE (no server reply, so net_flush does not overwrite
            # net->buff) + COM_QUERY(SELECT SLEEP(5)) into ONE compressed frame.
            # MariaDB extracts the 2nd command from net->remain_in_buf without
            # calling VIO readCb; EXECUTE_START must still invoke admit() and arm
            # query_timeout.
            stmt_close_body = b"\x19" + struct.pack("<I", 999)
            cmd1 = struct.pack("<I", len(stmt_close_body))[:3] + b"\x00" + stmt_close_body
            raw = cmd1 + _pipeline_frame("SELECT SLEEP(5)")
            comp = zlib.compress(raw)
            comp_hdr = (
                struct.pack("<I", len(comp))[:3]
                + b"\x00"
                + struct.pack("<I", len(raw))[:3]
            )
            t0 = time.monotonic()
            sock.sendall(comp_hdr + comp)
            # 2nd command must be poisoned by query_timeout (~0.25s), well before 5s.
            _wait_for_unusable(db)
            elapsed = time.monotonic() - t0
            assert elapsed < 3.0, f"2nd compressed command escaped query_timeout (elapsed={elapsed:.2f}s)"


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
        wire_db._session._process.stdin.close()
        assert wire_db._session._process.wait(timeout=5) == 0
    finally:
        conn._force_close()
        wire_db._dispose()
    assert wire_db._session._process.stdout.closed and wire_db._session._stderr.closed
    assert not wire_db._session._reader.is_alive()


def _pipeline_frame(statement):
    body = b"\x03" + statement.encode()
    size = len(body)
    return bytes((size & 255, size >> 8 & 255, size >> 16 & 255, 0)) + body


def _wait_for_active_query(db):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        if db.status()["busy"]:
            return
        time.sleep(0.005)
    raise AssertionError("query never became active")


def _wait_for_unusable(db):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        try:
            db.status()
        except mariamem.HostError as error:
            assert error.code == "unusable" and error.closed
            return
        time.sleep(0.01)
    raise AssertionError("failed instance remained usable")


def test_pipelined_commands_preserve_response_and_effect_order(wire_db):
    with connect(wire_db) as conn:
        execute(conn, "CREATE TABLE pipeline_order(value INT)")
        execute(conn, "INSERT INTO pipeline_order VALUES(0)")
        conn._write_bytes(
            _pipeline_frame("UPDATE pipeline_order SET value=value+1+SLEEP(0.1)") +
            _pipeline_frame("SELECT value FROM pipeline_order"))
        conn._next_seq_id = 1
        conn._read_query_result()
        assert conn._result.affected_rows == 1
        conn._next_seq_id = 1
        conn._read_query_result()
        assert conn._result.rows == ((1,),)
        assert execute(conn, "SELECT 11") == ((11,),)


def test_pipelined_malformed_frame_is_rejected_after_current_response(wire_db):
    with connect(wire_db) as conn:
        bad = bytearray(_pipeline_frame("SELECT 999"))
        bad[3] = 9  # Each command must start at sequence0.
        conn._write_bytes(_pipeline_frame("SELECT SLEEP(0.1)") + bad)
        conn._next_seq_id = 1
        conn._read_query_result()
        assert conn._result.rows == ((0,),)
        conn._next_seq_id = 1
        with pytest.raises(pymysql.Error):
            conn._read_query_result()
        conn._force_close()
    with connect(wire_db) as fresh:
        assert execute(fresh, "SELECT 2") == ((2,),)


@pytest.mark.parametrize("failure", ["disconnect", "overflow", "close", "timeout"])
def test_pipelined_fatal_paths_preserve_independent_root(wire_host, failure):
    with mariamem.start(host_binary=wire_host) as independent:
        query_timeout = 0.1 if failure == "timeout" else 10
        with mariamem.start(host_binary=wire_host, query_timeout=query_timeout, shutdown_timeout=1) as db:
            conn = connect(db)
            try:
                # Keep this a cooperative close control, not a forced-reclamation test.
                conn._execute_command(3, b"SELECT SLEEP(0.5)")
                _wait_for_active_query(db)
                if failure == "overflow":
                    # Per approved 1B=A contract, pending input overflow terminates only
                    # the offending connection while preserving peer connections and db.
                    conn._write_bytes(b"x" * 1048582)  # Accepted queue limit +1.
                    with pytest.raises(pymysql.Error):
                        conn._read_query_result()
                    conn._force_close()
                    db.wait_disconnected()
                    with connect(db) as survivor:
                        assert execute(survivor, "SELECT 1") == ((1,),)
                else:
                    conn._write_bytes(_pipeline_frame("SELECT 999"))
                    if failure == "disconnect":
                        conn._force_close()
                        _wait_for_unusable(db)  # Before the10s query deadline.
                    elif failure == "timeout":
                        with pytest.raises(pymysql.Error):
                            conn._read_query_result()
                        _wait_for_unusable(db)
                    else:
                        db.close()
                        assert db.closed
                with connect(independent) as good:
                    assert execute(good, "SELECT 2") == ((2,),)
            finally:
                conn._force_close()
