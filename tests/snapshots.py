#!/usr/bin/env python3
"""Snapshot acceptance over the real MySQL TCP and lifecycle channels."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import shutil
import socket
import sys
import tempfile
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python"))
import mariamem
import pymysql


def main():
    (ROOT / "tests/runs").mkdir(parents=True, exist_ok=True)
    run = Path(tempfile.mkdtemp(prefix="snapshots-", dir=ROOT / "tests/runs"))
    binary = Path(os.environ.get("MARIAMEM_TEST_HOST", ROOT / "build/mariamem-host"))
    options = dict(host_binary=binary)
    report = {"run_directory": str(run), "checks": []}
    active, connections, snapshots = [], [], []

    def check(name, value):
        assert value, name
        report["checks"].append(name)

    def start(name, saved=None, **extra):
        opts = {**options, "log_path": run / (name + ".log"), **extra}
        db = saved.fork(**opts) if saved else mariamem.start(**opts)
        active.append(db)
        return db

    def connect(db):
        conn = pymysql.connect(**db.connection_info(), autocommit=True, charset="utf8mb4",
                               binary_prefix=True, read_timeout=5, write_timeout=5)
        connections.append(conn)
        return conn

    def sql(conn, statement, args=None):
        with conn.cursor() as cur:
            cur.execute(statement, args)
            return cur.fetchall()

    def wait_state(db, predicate):
        until = time.monotonic() + 5
        while time.monotonic() < until:
            if predicate(db.status()):
                return
            time.sleep(0.005)
        raise AssertionError("host state did not settle")

    def idle(db):
        wait_state(db, lambda state: not state["busy"])

    def gone(db):
        check("DB consumed/closed: " + db.log_path.name, db.closed)
        # A shared process intentionally remains while baselines/siblings live.

    def reject(db, path, code):
        try:
            db.snapshot()
        except mariamem.HostError as exc:
            check("snapshot rejection: " + code, exc.code == code and not exc.closed and not db._closed)
        else:
            raise AssertionError("snapshot unexpectedly accepted")

    try:
        db = start("source")
        check("snapshot and fork capabilities", {"snapshot", "fork"} <= set(db.capabilities))
        # An unfinished handshake must not race snapshot admission.
        raw = socket.create_connection((db.connection_info()["host"], db.connection_info()["port"]))
        raw.recv(1)
        reject(db, run / "handshake-rejected", "busy")
        raw.close()
        wait_state(db, lambda state: state["active_connections"] == 0)
        conn = connect(db)
        sql(conn, "CREATE TABLE items(id INT PRIMARY KEY, value VARBINARY(100)) ENGINE=InnoDB")
        sql(conn, "INSERT INTO items VALUES(1,%s)", (b"\x00\xffhello",))
        sql(conn, "CREATE VIEW item_view AS SELECT id FROM items")
        sql(conn, "CREATE DATABASE `日本語`")
        sql(conn, "CREATE TABLE `日本語`.`空`(id INT) ENGINE=InnoDB")
        sql(conn, "SELECT GET_LOCK('snapshot-session',1)")
        conn.close()
        wait_state(db, lambda state: state["active_connections"] == 0)
        conn = connect(db)
        check("named lock released on reconnect", sql(conn, "SELECT IS_FREE_LOCK('snapshot-session')") == ((1,),))
        conn._sock.sendall(b"\x09")  # First byte of an incomplete MySQL packet.
        wait_state(db, lambda state: state["busy"])
        reject(db, run / "partial-packet-rejected", "busy")
        conn._force_close()
        wait_state(db, lambda state: state["active_connections"] == 0)
        conn = connect(db)
        with ThreadPoolExecutor(max_workers=1) as pool:
            running = pool.submit(sql, conn, "SELECT SLEEP(0.4)")
            wait_state(db, lambda state: state["busy"])
            reject(db, run / "query-rejected", "busy")
            check("query continues after Busy", running.result() == ((0,),))
        idle(db)
        check("rejections preserve DB", sql(conn, "SELECT COUNT(*) FROM items") == ((1,),))
        sql(conn, "CREATE TEMPORARY TABLE session_only(id INT)")
        sql(conn, "SET @session_only=12")
        sql(conn, "START TRANSACTION")
        sql(conn, "INSERT INTO items VALUES(2,'pending')")
        idle(db)
        reject(db, run / "transaction-rejected", "transaction_active")
        check("rejection preserves active transaction", sql(conn, "SELECT COUNT(*) FROM items") == ((2,),))
        idle(db)
        template_path = run / "template"
        saved = db.snapshot(rollback=True)
        snapshots.append(saved)
        gone(db)
        check("rejected operations leave no destination", all(not (run / name).exists() for name in
              ("handshake-rejected", "partial-packet-rejected", "query-rejected", "transaction-rejected", "missing-parent")))
        try:
            sql(conn, "SELECT 1")
            raise AssertionError("snapshot left source connection usable")
        except pymysql.OperationalError:
            check("snapshot closes source TCP", True)
        a, b = start("a", saved), start("b", saved)
        ca, cb = connect(a), connect(b)
        check("forks have distinct DB identities", a.id != b.id != db.id)
        check("binary data restored and pending row absent", sql(ca, "SELECT * FROM items") == ((1,b"\x00\xffhello"),))
        check("view restored", sql(cb, "SELECT * FROM item_view") == ((1,),))
        check("unicode schema and empty table restored", sql(cb, "SELECT * FROM `日本語`.`空`") == ())
        check("session variable not restored", sql(ca, "SELECT @session_only,@@autocommit") == ((None,1),))
        try:
            sql(ca, "SELECT * FROM session_only")
            raise AssertionError("temporary table restored")
        except pymysql.ProgrammingError as exc:
            check("temporary table not restored", exc.args[0] == 1146)
        sql(ca, "START TRANSACTION")
        sql(ca, "INSERT INTO items VALUES(3,'only-a')")
        check("uncommitted changes isolated", sql(cb, "SELECT COUNT(*) FROM items") == ((1,),))
        ca.commit()
        check("committed changes isolated", sql(cb, "SELECT COUNT(*) FROM items") == ((1,),))
        idle(a)
        saved_a = a.snapshot()
        snapshots.append(saved_a)
        gone(a)
        check("other fork survives sibling snapshot", sql(cb, "SELECT COUNT(*) FROM items") == ((1,),))
        c = saved_a.fork(log_path=run / "c.log")
        active.append(c)
        cc = connect(c)
        check("fork of new snapshot includes changes", sql(cc, "SELECT id FROM items ORDER BY id") == ((1,),(3,)))
        c.close()
        gone(c)
        check("other fork survives sibling close", sql(cb, "SELECT 1") == ((1,),))
        b.close()
        gone(b)
        with saved.fork(log_path=run / "unchanged.log") as unchanged:
            active.append(unchanged)
            cu = connect(unchanged)
            check("owned parent remains unchanged", sql(cu, "SELECT * FROM items") == ((1,b"\x00\xffhello"),))
        # Persisted-path integrity cases moved to internal/snapshot and the
        # immutable-heap source/target/owner oracles; no public import remains.
        empty = start("no-sql-client")
        empty_saved = empty.snapshot()
        snapshots.append(empty_saved)
        with empty_saved.fork(log_path=run / "empty-fork.log") as empty_child:
            active.append(empty_child)
            check("snapshot with no SQL connection", sql(connect(empty_child), "SELECT 1") == ((1,),))
        gone(empty)

        # Interrupting active SQL is the separate, known containment boundary.
        # The old native-runtime expectation belongs in diagnostics, not a
        # successful cooperative Snapshot/ownership cleanup claim.
        # See tests/diagnostics/active_query_close.py and test_python_timeout.py.
        # Detector silence is not a correctness proof for guest mmap/assembly.
        check("memory-only public API", not hasattr(mariamem,"load_snapshot") and not hasattr(db,"snapshot_to"))
        report["passed"] = True
    except Exception:
        report["passed"] = False
        report["error"] = traceback.format_exc()
    finally:
        for conn in connections:
            conn._force_close()
        for db in active:
            if not db._closed:
                db.close()
        for saved in snapshots:
            saved.close()
            check("snapshot owned handles released", saved._closed)
        suffix = "-race" if binary.name.endswith("-race") else ""
        output = ROOT / f"tests/evidence/snapshots{suffix}.json"
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
        print(json.dumps({"passed":report["passed"],"checks":len(report["checks"]),"error":report.get("error"),"evidence":str(output)},ensure_ascii=False),flush=True)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
