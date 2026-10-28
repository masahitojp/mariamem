"""Bounded standalone-host probe; SIGQUIT deliberately ends the diagnostic case."""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time

import pymysql

ROOT = Path(__file__).resolve().parent
HOST = str(Path(sys.argv[1]).resolve())
SUFFIX = "-diagnostic" if "diagnostic" in HOST else ""

def run(label, setup=(), query="SELECT DISTINCT customer FROM t", stack=False):
    log = (ROOT / (label + SUFFIX + ".log")).open("w")
    proc = subprocess.Popen([HOST, "--query-timeout=4s"], stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, stderr=log, text=True)
    result = {"label": label, "setup": setup, "query": query}
    try:
        ready = json.loads(proc.stdout.readline())
        result["ready"] = ready
        args = {k: ready[k] for k in ("host", "port", "user", "password", "database")}
        conn = pymysql.connect(**args, read_timeout=7, autocommit=True)
        other = pymysql.connect(**args, read_timeout=2, autocommit=True)
        cur = conn.cursor()
        cur.execute("CREATE TABLE t(id INT, customer TEXT)")
        cur.execute("INSERT INTO t VALUES (1,'alice'),(2,'bob'),(3,'alice')")
        for sql in setup:
            cur.execute(sql)
        cur.execute("EXPLAIN " + query)
        result["explain"] = cur.fetchall()
        cur.execute("SHOW SESSION STATUS LIKE 'Created_tmp%'")
        result["before"] = cur.fetchall()
        start = time.monotonic()
        def execute():
            try:
                cur.execute(query)
                result["rows"] = cur.fetchall()
                cur.execute("SHOW SESSION STATUS LIKE 'Created_tmp%'")
                result["after"] = cur.fetchall()
            except Exception as exc:
                result["error"] = str(exc)
            result["elapsed"] = time.monotonic() - start
        thread = threading.Thread(target=execute)
        thread.start()
        thread.join(.4)
        if thread.is_alive():
            try:
                with other.cursor() as c:
                    c.execute("SELECT 1")
                    result["other_session"] = c.fetchall()
            except Exception as exc:
                result["other_session_error"] = str(exc)
            if stack:
                proc.send_signal(signal.SIGQUIT)
        thread.join(8)
        conn.close()
        other.close()
    except Exception as exc:
        result["probe_error"] = str(exc)
    finally:
        if proc.poll() is None:
            proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        log.close()
    print(json.dumps(result), flush=True)
    return result

results = []
for label, setup, query, stack in [
    ("default", [], "SELECT DISTINCT customer FROM t", False),
    ("big_tables", ["SET SESSION big_tables=1"], "SELECT DISTINCT customer FROM t", False),
    ("tiny_tmp", ["SET SESSION tmp_table_size=1024", "SET SESSION max_heap_table_size=16384"], "SELECT DISTINCT customer FROM t", False),
    ("big_result", [], "SELECT SQL_BIG_RESULT DISTINCT customer FROM t", False),
    ("stack", [], "SELECT DISTINCT customer FROM t", True),
]:
    if SUFFIX and label != "default":
        continue
    results.append(run(label, setup, query, stack))
    (ROOT / ("probes" + SUFFIX + ".json")).write_text(json.dumps(results, indent=2) + "\n")
