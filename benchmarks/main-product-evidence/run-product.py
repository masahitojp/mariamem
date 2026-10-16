"""Replay the approved v047/v050 Go/Python Fresh/Fork product matrix."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

p = argparse.ArgumentParser(description=__doc__)
p.add_argument("--workspace", type=Path, required=True)
p.add_argument("--output", type=Path, required=True)
a = p.parse_args()
root = Path(__file__).resolve().parents[2]
work = a.workspace.resolve()
out = a.output.resolve()
out.mkdir(parents=True, exist_ok=False)
sys.path.insert(0, str(root / "scripts"))
from experiment_disk import DiskGuard, run_guarded

roots = {"baseline": work / "temp/baseline", "candidate": work / "temp/candidate"}
bins = work / "temp/binaries"
helper = bins / "process-cost"
env = dict(os.environ, GOTOOLCHAIN="local")
env.pop("GOMAXPROCS", None)
image = "mariadb@sha256:805c8e104bd563d5bfa24fadd3f31cd419ea859cb5277f32b5dbf2db714f9ed1"
identity = {
    "source_commits": {state: subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=path, text=True).strip()
                       for state, path in roots.items()},
    "harness_source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(),
    "harness_sha256": {name: hashlib.sha256((root / name).read_bytes()).hexdigest()
                       for name in ("benchmarks/main-product-evidence/run-product.py",
                                    "benchmarks/python_product_suites.py",
                                    "benchmarks/ownedprepared/main.go", "benchmarks/ownedprepared/resources.go")},
    "go": subprocess.check_output(["go", "version"], text=True).strip(),
    "python": sys.version, "trials": 3, "large_trials": 1, "suite_count": 4,
    "normal_cells": 80, "pilots": 8, "cell_timeout_seconds": 900,
    "disk_budget_gib": 12, "minimum_free_gib": 20,
    "scope": "Approved paired Go/Python Fresh/Fork comparison; native container anchors are not included.",
    "host": {"uname": subprocess.check_output(["uname", "-a"], text=True).strip(),
             "ram_bytes": int(subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True)),
             "macos": subprocess.check_output(["sw_vers", "-productVersion"], text=True).strip()},
    "cells": [],
}
assert identity["go"] == "go version go1.26.8 darwin/arm64"
def save():
    (out / "inputs.json").write_text(json.dumps(identity, indent=2) + "\n")
save()

def run(state, language, case, trial, mode, size, tables, workers, count=4, pilot=False):
    name = f"{state}-{language}-{case}-{trial}-{mode}"
    if pilot:
        name = "pilot-" + name
    dest = out / (name + ".json")
    if language == "go":
        command = [str(bins / state / "ownedprepared"), "-payload-mib", str(size), "-tables", str(tables),
                   "-workers", str(workers), "-forks", str(count), "-workload", "app-connections",
                   "-lifecycle", mode, "-go-resources", "-helper", str(helper),
                   "-label", identity["source_commits"][state], "-out", str(dest)]
    else:
        command = [sys.executable, str(root / "benchmarks/python_product_suites.py"),
                   "--payload-mib", str(size), "--tables", str(tables), "--workers", str(workers),
                   "--count", str(count), "--mode", mode, "--host", str(bins / state / "mariamem-host"),
                   "--image", image, "--helper", str(helper), "--out", str(dest)]
    cellenv = dict(env, PYTHONPATH=str(roots[state] / "python"))
    guard = DiskGuard(work, 20, 12)
    started = time.monotonic()
    print("RUN", name, flush=True)
    with (out / (name + ".txt")).open("w") as log:
        code = run_guarded(command, guard, cwd=roots[state], env=cellenv, output=log, timeout=900, interval=5)
    identity["cells"].append({"name": name, "returncode": code,
                              "elapsed_seconds": time.monotonic() - started, "disk": guard.check()})
    save()
    if code:
        raise SystemExit(f"{name} failed: {code}; keep the original oracle")
    data = json.loads(dest.read_text())
    if data.get("completed") is False:
        raise SystemExit(f"{name} incomplete")
    if data.get("go_resource_observation", {}).get("process_peak_rss_bytes", 0) > 8 * 1024**3:
        raise SystemExit("Stop: completed cell exceeded 8 GiB process RSS budget")
    print("PASS", name, flush=True)

for state in roots:
    for language in ("go", "python"):
        for mode in ("fresh", "fork"):
            run(state, language, "light", 0, mode, 0, 1, 1, count=1, pilot=True)
for trial in range(3):
    cases = [("light", 0, 1, 1), ("fixture", 10, 8, 1), ("parallel", 10, 8, 4)]
    if trial == 0:
        cases.append(("large", 100, 8, 1))
    for case, size, tables, workers in cases:
        for language in ("go", "python"):
            for mode in ("fresh", "fork"):
                order = ("baseline", "candidate") if (trial + (mode == "fork")) % 2 == 0 else ("candidate", "baseline")
                for state in order:
                    run(state, language, case, trial, mode, size, tables, workers)
assert len(identity["cells"]) == 88
print("PASS: approved 80 cells and 8 pilots completed", flush=True)
