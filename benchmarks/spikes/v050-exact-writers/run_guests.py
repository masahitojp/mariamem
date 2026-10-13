"""Bounded SQL comparison of unmodified and isolated candidate host binaries."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[3]
p = argparse.ArgumentParser()
p.add_argument("--task", type=Path, required=True)
a = p.parse_args()
task = a.task.resolve()
python = task / "temp/venv/bin/python"
driver = ROOT / "benchmarks/spikes/v050-shared-impact/scenarios.py"
results = {}
for ahi in (False, True):
    for role in ("control", "candidate"):
        name = "guest-" + role + ("-ahi" if ahi else "-default") + "-final"
        host = task / ("temp/" + role + "-host")
        output = task / "temp" / name
        command = [str(python), str(driver), str(host), str(output), *(["--enable-ahi"] if ahi else [])]
        run = subprocess.run(command, cwd=ROOT, env={**os.environ, "PYTHONPATH": str(ROOT / "python")},
                             capture_output=True, text=True, timeout=180)
        log = run.stdout + run.stderr
        (task / "evidence" / (name + ".txt")).write_text(log)
        if run.returncode:raise RuntimeError(name + "\n" + log)
        r = json.loads((output / "results.json").read_text())
        r.pop("host")
        r["binary_sha256"] = hashlib.sha256(host.read_bytes()).hexdigest()
        results[name] = r
        print(name, r["result"], flush=True)
    names = ["guest-" + role + ("-ahi" if ahi else "-default") + "-final" for role in ("control", "candidate")]
    observations = [[(c["name"], c["value"]) for c in results[n]["cases"]] for n in names]
    assert observations[0] == observations[1], "functional result differs"
(task / "evidence/guest-comparison.json").write_text(json.dumps({
    "driver_sha256": hashlib.sha256(driver.read_bytes()).hexdigest(),
    "runs": results,
    "interpretation": "Same scenario outputs; cold and observer timing variation is not a performance comparison.",
}, indent=2) + "\n")
