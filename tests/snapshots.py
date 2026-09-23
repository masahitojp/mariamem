#!/usr/bin/env python3
"""Snapshot acceptance over the real MySQL TCP and lifecycle channels."""
from concurrent.futures import ThreadPoolExecutor
import json
import os
from pathlib import Path
import signal
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
    options = dict(host_binary=binary, runtime=ROOT / "build/tools/wasmer/bin/wasmer-headless",
                   module=ROOT / "build/guest/mariamem.wasmu", wasmer_dir=ROOT / "build/wasmer-home")
    report = {"run_directory": str(run), "checks": []}
    active, connections = [], []

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
        check("host reaped: " + db.log_path.name, db._process.poll() is not None)
        try:
            os.kill(db.diagnostics["runtime_pid"], 0)
        except ProcessLookupError:
            pass
        else:
            raise AssertionError("guest remains alive")
        check("runtime and wrapper handles reaped: " + db.log_path.name,
              db._process.stdin.closed and db._process.stdout.closed and db._log.closed and not db._reader.is_alive())

    def reject(db, path, code):
        try:
            db.snapshot(path)
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
        existing = run / "existing"
        existing.mkdir()
        marker = existing / "keep"
        marker.write_text("preserved")
        reject(db, existing, "destination")
        reject(db, run / "missing-parent/saved", "destination")
        check("existing destination untouched", marker.read_text() == "preserved")
        check("rejections preserve DB", sql(conn, "SELECT COUNT(*) FROM items") == ((1,),))
        sql(conn, "CREATE TEMPORARY TABLE session_only(id INT)")
        sql(conn, "SET @session_only=12")
        sql(conn, "START TRANSACTION")
        sql(conn, "INSERT INTO items VALUES(2,'pending')")
        idle(db)
        reject(db, run / "transaction-rejected", "transaction_active")
        check("rejection preserves active transaction", sql(conn, "SELECT COUNT(*) FROM items") == ((2,),))
        idle(db)
        saved = db.snapshot(run / "template", rollback=True)
        gone(db)
        check("rejected operations leave no destination", all(not (run / name).exists() for name in
              ("handshake-rejected", "partial-packet-rejected", "query-rejected", "transaction-rejected", "missing-parent")))
        try:
            sql(conn, "SELECT 1")
            raise AssertionError("snapshot left source connection usable")
        except pymysql.OperationalError:
            check("snapshot closes source TCP", True)
        manifest_before = (saved.path / "manifest.json").read_bytes()
        saved = mariamem.Snapshot.open(saved.path)
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
        saved_a = a.snapshot(run / "saved-a")
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
        saved.validate()
        check("template remains unchanged", (saved.path / "manifest.json").read_bytes() == manifest_before)

        # Alter only test-owned snapshots, restoring each byte before the next case.
        table = saved.path / "data/data/test/items.frm"
        original = table.read_bytes()
        try:
            table.write_bytes(b"corrupt" + original[7:])
            try:
                mariamem.Snapshot.open(saved.path)
                raise AssertionError("corruption accepted")
            except ValueError:
                check("corrupt snapshot rejected", True)
        finally:
            table.write_bytes(original)
        link = saved.path / "data/forbidden-link"
        try:
            link.symlink_to(table)
            try:
                saved.validate()
                raise AssertionError("symlink accepted")
            except ValueError:
                check("symlink rejected", True)
        finally:
            link.unlink()
        try:
            changed = json.loads(manifest_before)
            changed["wasm_sha256"] = "0" * 64
            (saved.path / "manifest.json").write_text(json.dumps(changed))
            try:
                start("wrong-build", mariamem.Snapshot.open(saved.path))
                raise AssertionError("incompatible build accepted")
            except mariamem.HostError:
                check("incompatible WASM build rejected before ready", True)
        finally:
            (saved.path / "manifest.json").write_bytes(manifest_before)

        failed = start("failed-export")
        fc = connect(failed)
        idle(failed)
        os.kill(failed.diagnostics["runtime_pid"], signal.SIGSTOP)
        try:
            failed.snapshot(run / "incomplete", timeout=0.2)
            raise AssertionError("stopped guest exported")
        except mariamem.HostError as exc:
            check("accepted snapshot failure closes source", exc.closed and failed._closed)
        gone(failed)
        check("failed export removes new destination", not (run / "incomplete").exists())
        check("failed export has no completed manifest", not (run / "incomplete/manifest.json").exists())
        try:
            mariamem.Snapshot.open(run / "incomplete")
            raise AssertionError("incomplete snapshot accepted")
        except FileNotFoundError:
            check("removed partial snapshot cannot be opened", True)

        empty = start("no-sql-client")
        empty_saved = empty.snapshot(run / "empty-template")
        check("snapshot with no SQL connection", empty_saved.validate() is empty_saved)
        gone(empty)

        closing = start("close-during-query")
        cx = connect(closing)
        with ThreadPoolExecutor(max_workers=1) as pool:
            running = pool.submit(sql, cx, "SELECT SLEEP(0.2)")
            wait_state(closing, lambda state: state["busy"])
            closing.close()
            try:
                running.result()
            except pymysql.OperationalError:
                pass
        check("explicit close drains query and exits normally", closing._process.returncode == 0)
        gone(closing)
        check("no Go race reports", not any("WARNING: DATA RACE" in p.read_text() for p in run.glob("*.log")))
        report["passed"] = True
    except Exception:
        report["passed"] = False
        report["error"] = traceback.format_exc()
    finally:
        for conn in connections:
            conn._force_close()
        for db in active:
            if not db._closed:
                db._dispose()
        suffix = "-race" if binary.name.endswith("-race") else ""
        output = ROOT / f"tests/evidence/snapshots{suffix}.json"
        output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n")
        print(json.dumps({"passed":report["passed"],"checks":len(report["checks"]),"error":report.get("error"),"evidence":str(output)},ensure_ascii=False),flush=True)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
