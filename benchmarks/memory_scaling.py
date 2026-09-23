#!/usr/bin/env python3
"""Sample startup/steady memory of independent seeded DBs; metrics differ by backend."""
import os
import platform
import subprocess
import threading
import time
import uuid
from _common import backends, options, record, run, template
from parallel_databases import batch


class Sampler:
    def __init__(self, backend, interval):
        self.backend, self.interval = backend, interval
        self.label = uuid.uuid4().hex
        self.samples, self.errors = [], []
        self.done = threading.Event()
        self.thread = None
        self.client = None
        if backend == "testcontainers":
            from testcontainers.core.docker_client import DockerClient
            self.client = DockerClient().client
        elif platform.system() != "Darwin":
            raise RuntimeError("This RSS benchmark currently targets macOS only")

    def read(self):
        if self.backend == "testcontainers":
            containers = self.client.containers.list(filters={"label": "mariamem.benchmark=" + self.label})
            # Raw Docker API/cgroup usage; do not subtract cache or call this host RSS.
            values = {c.id: c.stats(stream=False)["memory_stats"]["usage"] for c in containers}
        else:
            proc = subprocess.Popen(["ps", "-axo", "pid=,ppid=,rss="], stdout=subprocess.PIPE,
                                    stderr=subprocess.PIPE, text=True)
            try:
                stdout, stderr = proc.communicate(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.communicate()
                raise
            if proc.returncode:
                raise RuntimeError(stderr)
            entries = [tuple(map(int, line.split())) for line in stdout.splitlines() if line.strip()]
            descendants = {os.getpid()}
            while True:
                children = {pid for pid, parent, _ in entries if parent in descendants and pid != proc.pid}
                if children <= descendants:
                    break
                descendants.update(children)
            values = {str(pid): rss * 1024 for pid, _, rss in entries
                      if pid in descendants and pid != os.getpid()}
        return {"bytes": sum(values.values()), "members": values}

    def start(self, started):
        def sample():
            while not self.done.is_set():
                begin = time.perf_counter()
                try:
                    value = self.read()
                    value.update(at_seconds=time.perf_counter() - started,
                                 collection_seconds=time.perf_counter() - begin)
                    self.samples.append(value)
                except Exception as exc:
                    self.errors.append(str(exc))
                    break
                self.done.wait(self.interval)
        self.thread = threading.Thread(target=sample, daemon=True)
        self.thread.start()

    def stop(self):
        if self.done.is_set():
            return
        self.done.set()
        if self.thread:
            self.thread.join()
        if self.client:
            self.client.close()

    def result(self, ready_seconds):
        if self.errors or not self.samples:
            raise RuntimeError(f"memory sampling failed: {self.errors}")
        peak = max(self.samples, key=lambda s: s["bytes"])
        ready = min(self.samples, key=lambda s: abs(s["at_seconds"] - ready_seconds))
        return {"mechanism": "macOS descendant-process RSS sum" if self.backend == "mariamem"
                else "Docker API memory_stats.usage sum (Linux cgroup, includes cache)",
                "unit": "bytes", "requested_interval_seconds": self.interval,
                "sampled_peak_bytes": peak["bytes"], "sampled_peak_at_seconds": peak["at_seconds"],
                "nearest_ready_sample": ready, "last_sample": self.samples[-1], "samples": self.samples}


def benchmark(args, report):
    for backend in backends(args):
        for phase, count in (("warmup", args.warmup), ("measurement", args.runs)):
            if not count:
                continue
            with template(backend, args, report, phase) as saved:
                for workers in args.workers:
                    for index in range(count):
                        monitor = Sampler(backend, args.interval) if phase == "measurement" else None
                        result = batch(backend, args, saved, workers,
                                       hold=args.hold if monitor else 0, monitor=monitor)
                        record(report, backend, phase, index, result, workers)
                        if monitor:
                            memory = result["memory"]
                            print(f"  sampled peak={memory['sampled_peak_bytes']/2**20:.1f} MiB; "
                                  f"last={memory['last_sample']['bytes']/2**20:.1f} MiB; "
                                  f"{memory['mechanism']}")


if __name__ == "__main__":
    run(options(__doc__, seeded=True, parallel=True, memory=True), benchmark, "memory_scaling")
