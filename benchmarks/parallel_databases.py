#!/usr/bin/env python3
"""Wall time until all independently seeded databases are queryable."""
from concurrent.futures import ThreadPoolExecutor
import queue
import threading
import time
from _common import backends, instance, options, probe, record, run, template


def batch(backend, args, saved, workers, *, hold=0, monitor=None):
    ready_queue = queue.Queue()
    release = threading.Event()
    started = time.perf_counter()

    def worker():
        local_start = time.perf_counter()
        try:
            with instance(backend, args, saved, label=monitor.label if monitor else None) as db:
                ready, version = probe(db, rows=args.rows, seed=backend == "testcontainers")
                ready_queue.put({"ready_at_seconds": ready - started,
                                 "latency_seconds": ready - local_start, "server_version": version})
                release.wait()
        except BaseException as exc:
            ready_queue.put(exc)
            raise

    if monitor:
        monitor.start(started)
    try:
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = []
            try:
                for _ in range(workers):
                    futures.append(pool.submit(worker))
                timings = []
                for _ in futures:
                    item = ready_queue.get(timeout=180)
                    if isinstance(item, BaseException):
                        raise item
                    timings.append(item)
                wall = max(item["ready_at_seconds"] for item in timings)
                time.sleep(hold)
            finally:
                if monitor:
                    monitor.stop()
                cleanup = time.perf_counter()
                release.set()
            for future in futures:
                future.result()
        result = {"ready_seconds": wall, "per_db": timings, "hold_seconds": hold,
                  "cleanup_seconds": time.perf_counter() - cleanup}
        if monitor:
            result["memory"] = monitor.result(wall)
        return result
    finally:
        release.set()
        if monitor:
            monitor.stop()


def benchmark(args, report):
    for backend in backends(args):
        for phase, count in (("warmup", args.warmup), ("measurement", args.runs)):
            if not count:
                continue
            with template(backend, args, report, phase) as saved:
                for workers in args.workers:
                    for index in range(count):
                        record(report, backend, phase, index, batch(backend, args, saved, workers), workers)


if __name__ == "__main__":
    run(options(__doc__, seeded=True, parallel=True), benchmark, "parallel_databases")
