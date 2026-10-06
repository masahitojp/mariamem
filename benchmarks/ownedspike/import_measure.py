"""Same SDK harness for exact baseline and candidate; run in separate processes."""
import argparse
import json
import os
from pathlib import Path
import resource
import subprocess
import time

import mariamem
import pymysql


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifact", required=True)
    parser.add_argument("--host", required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--forks", type=int, default=16)
    parser.add_argument("--helper", required=True)
    args = parser.parse_args()
    operations, resources = [], {}
    def cpu():
        own = resource.getrusage(resource.RUSAGE_SELF)
        child = resource.getrusage(resource.RUSAGE_CHILDREN)
        return own.ru_utime + own.ru_stime + child.ru_utime + child.ru_stime
    def measure(name, fn):
        start, start_cpu = time.perf_counter(), cpu()
        result = fn()
        operations.append(dict(name=name, seconds=time.perf_counter() - start,
                               cpu_seconds=cpu() - start_cpu))
        return result
    def probe(name, *pids):
        resources[name] = json.loads(subprocess.check_output([args.helper, *map(str, pids)]))
    probe("before", os.getpid())
    # Baseline API has no host_binary argument on open; select the same host
    # through the supported override for candidate's explicit identity gate.
    # Both snapshots then fork using an explicit exact host binary.
    if hasattr(mariamem.Snapshot, "_created"):
        saved = measure("import", lambda: mariamem.Snapshot.open(args.artifact, host_binary=args.host))
    else:
        saved = measure("import", lambda: mariamem.Snapshot.open(args.artifact))
    file_entries = [v for v in saved.manifest["entries"].values() if v["kind"] == "file"]
    result = dict(label=args.label, prepared_files=len(file_entries),
                  prepared_bytes=sum(v["bytes"] for v in file_entries),
                  owned_fds=len(getattr(saved, "_files", ())), operations=operations, resources=resources)
    probe("imported", os.getpid())
    for index in range(args.forks):
        child = measure(f"fork_ready_{index:02}", lambda: saved.fork(host_binary=args.host))
        if index == 0:
            probe("first_ready", os.getpid(), child.diagnostics["host_pid"])
        def use():
            with pymysql.connect(**child.connection_info(), autocommit=True) as connection:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT payload FROM characterization WHERE id=0")
                    assert len(cursor.fetchone()[0]) == 1024
                    cursor.execute("SELECT COUNT(*) FROM characterization")
                    assert cursor.fetchone()[0] > 0
            child.wait_disconnected()
        measure(f"point_and_count_{index:02}", use)
        # Reaped child CPU enters RUSAGE_CHILDREN here. Sum suite CPU, rather
        # than interpreting close CPU as time actually spent in shutdown.
        measure(f"child_close_{index:02}", child.close)
    measure("snapshot_close", saved.close)
    probe("after", os.getpid())
    result["suite_operation_seconds"] = sum(v["seconds"] for v in operations)
    result["suite_cpu_seconds"] = sum(v["cpu_seconds"] for v in operations)
    Path(args.out).write_text(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
