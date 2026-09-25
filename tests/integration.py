#!/usr/bin/env python3
"""Real Go host + Python wrapper + PyMySQL + WASIX acceptance checks."""
import json
import os
from pathlib import Path
import signal
import sys
import tempfile
import threading
import time
import traceback

ROOT = Path(__file__).resolve().parents[1]
HOST_BINARY = Path(os.environ.get("MARIAMEM_TEST_HOST", ROOT / "build/mariamem-host"))
sys.path.insert(0, str(ROOT / "python"))
import mariamem
import pymysql
from support import wire_acceptance as acceptance



def main():
    runs = ROOT / "tests/runs"
    runs.mkdir(parents=True, exist_ok=True)
    run = Path(tempfile.mkdtemp(prefix="initial-", dir=runs))
    evidence = {"run_directory": str(run), "checks": [], "wire_checks": [], "instances": []}
    active = []

    def check(name, condition):
        assert condition, name
        evidence["checks"].append(name)

    def start(name, **extra):
        options = dict(host_binary=HOST_BINARY,
                       runtime=ROOT / "build/tools/wasmer/bin/wasmer-headless",
                       module=ROOT / "build/guest/mariamem.wasmu",
                       wasmer_dir=ROOT / "build/wasmer-home", log_path=run / (name + ".log"))
        options.update(extra)
        db = mariamem.start(**options)
        active.append(db)
        return db

    def connect(db):
        return pymysql.connect(**db.connection_info(), charset="utf8mb4", autocommit=True,
                               binary_prefix=True, read_timeout=5, write_timeout=5)

    def sql(conn, statement):
        with conn.cursor() as cur:
            cur.execute(statement)
            return cur.fetchall()

    def idle(db):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            if db.status()["active_connections"] == 0:
                return
            time.sleep(0.01)
        raise AssertionError("session not released")

    def gone(db):
        check("host reaped: " + db.log_path.name, db._process.poll() is not None)
        try:
            os.kill(db.diagnostics["runtime_pid"], 0)
            raise AssertionError("runtime still exists")
        except ProcessLookupError:
            check("runtime reaped: " + db.log_path.name, True)
        check("wrapper handles closed: " + db.log_path.name,
              db._process.stdin.closed and db._process.stdout.closed and db._log.closed and not db._reader.is_alive())

    try:
        db = start("normal")
        check("opaque database identity independent of PID", len(db.id) == 32 and db.id != str(db.diagnostics["host_pid"]))
        conn = connect(db)
        with connect(db) as second:
            check("second connection accepted", sql(second, "SELECT 1") == ((1,),))
            check("first connection remains usable", sql(conn, "SELECT 2") == ((2,),))
        acceptance.exercise(conn, evidence["wire_checks"], api_version=2)
        conn.rollback()
        sql(conn, "CREATE TEMPORARY TABLE gone_on_reconnect(id INT)")
        sql(conn, "START TRANSACTION")
        sql(conn, "UPDATE wire_probe SET txt='pending-again' WHERE id=2")
        conn.close()
        idle(db)
        conn = connect(db)
        check("reconnect resets session variables", sql(conn, "SELECT @wire_marker,@@autocommit") == ((None, 1),))
        check("committed database survives reconnect", sql(conn, "SELECT COUNT(*) FROM wire_probe") == ((2,),))
        check("uncommitted data absent after reconnect", sql(conn, "SELECT txt FROM wire_probe WHERE id=2") == (("committed",),))
        try:
            sql(conn, "SELECT * FROM gone_on_reconnect")
            raise AssertionError("temporary table survived")
        except pymysql.ProgrammingError as exc:
            check("temporary table removed", exc.args[0] == 1146)
        sql(conn, "START TRANSACTION")
        sql(conn, "UPDATE wire_probe SET txt='TCP-drop' WHERE id=2")
        conn._force_close()
        idle(db)
        conn = connect(db)
        check("TCP EOF rolls back", sql(conn, "SELECT txt FROM wire_probe WHERE id=2") == (("committed",),))
        conn.close()
        idle(db)
        try:
            db._request("unimplemented-test-op")
            raise AssertionError("unimplemented operation advertised as working")
        except mariamem.HostError:
            check("unimplemented operation explicitly rejected", db.status()["state"] == "ready")
        db.close()
        db.close()
        gone(db)

        with start("idle", query_timeout=0.3) as db:
            conn = connect(db)
            time.sleep(0.6)
            check("query timeout does not expire idle connection", sql(conn, "SELECT 1") == ((1,),))
            conn.close()
        gone(db)

        for mode in ("stopped-large-write", "guest-killed", "host-sigterm"):
            db = start(mode, query_timeout=0.35, shutdown_timeout=0.4)
            conn = connect(db)
            timer = None
            if mode == "stopped-large-write":
                os.kill(db.diagnostics["runtime_pid"], signal.SIGSTOP)
                query = "SELECT '" + "x" * 262144 + "'"
            else:
                query = "SELECT SLEEP(10)"
                timer = threading.Timer(0.1, lambda: os.kill(
                    db.diagnostics["runtime_pid"] if mode == "guest-killed" else db.diagnostics["host_pid"],
                    signal.SIGKILL if mode == "guest-killed" else signal.SIGTERM))
                timer.start()
            before = time.monotonic()
            try:
                sql(conn, query)
                raise AssertionError("expected connection loss")
            except pymysql.OperationalError as exc:
                elapsed = time.monotonic() - before
                check(mode + ": driver receives bounded failure", exc.args[0] in (2006, 2013) and elapsed < 3)
                evidence[mode + "_seconds"] = round(elapsed, 4)
            finally:
                if timer:
                    timer.cancel()
                    timer.join()
                conn._force_close()
            db._process.wait(timeout=5)
            db._dispose()
            gone(db)
        with start("recovered") as db:
            with connect(db) as conn:
                check("new instance works after failures", sql(conn, "SELECT 2") == ((2,),))
        gone(db)

        db = start("owner-eof")
        conn = connect(db)
        db._process.stdin.close()
        check("owner EOF exits normally", db._process.wait(timeout=5) == 0)
        conn._force_close()
        db._dispose()
        gone(db)
        invalid = run / "invalid.wasmu"
        invalid.write_bytes(b"not a WASM or AOT artifact")
        try:
            start("wrong-guest", module=invalid)
            raise AssertionError("invalid guest accepted")
        except mariamem.HostError:
            check("invalid guest rejected during startup", True)
        check("no Go race detector reports", not any("WARNING: DATA RACE" in p.read_text() for p in run.glob("*.log")))
        evidence["passed"] = True
    except Exception:
        evidence["passed"] = False
        evidence["error"] = traceback.format_exc()
    finally:
        for db in active:
            if not db._closed:
                db._dispose()
            evidence["instances"].append({"id": db.id, **db.diagnostics,
                                          "host_exit": db._process.poll(), "log": str(db.log_path)})
        suffix = "-race" if HOST_BINARY.name.endswith("-race") else ""
        output = ROOT / f"tests/evidence/initial-integration{suffix}.json"
        output.parent.mkdir(exist_ok=True)
        output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n")
        print(json.dumps({"passed": evidence["passed"], "checks": len(evidence["checks"]),
                          "error": evidence.get("error"), "evidence": str(output)}, ensure_ascii=False), flush=True)
    return 0 if evidence["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
