#!/usr/bin/env python3
"""v0.5.0 Python Fresh serial/four-parallel control, same 10 MiB workload."""
import hashlib
import itertools
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

temp = Path(__file__).resolve().parent
evidence = temp.parent / "evidence"
source = Path(__file__).resolve().parents[4]
host = temp / "mariamem-host"
expected = "b2b8a9e88e238ede252d8290897b269ce7c09823e6fd9622fdb9a0dcde48dc66"
if hashlib.sha256(host.read_bytes()).hexdigest() != expected:
    raise SystemExit("published v0.5.0 host binary identity mismatch")
if subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=source, text=True).strip() != "44100ec676c8c9064f32f3a01bd9a990d487bb61":
    raise SystemExit("source commit mismatch")
observer = source / "benchmarks/python_product_suites.py"
image = "mariadb@sha256:805c8e104bd563d5bfa24fadd3f31cd419ea859cb5277f32b5dbf2db714f9ed1"
inputs = {"source_commit": "44100ec676c8c9064f32f3a01bd9a990d487bb61",
          "host_sha256": expected, "observer_sha256": hashlib.sha256(observer.read_bytes()).hexdigest(),
          "python": sys.version, "image_pin_validation_only": image,
          "blocks": 60, "suite_count": 4, "payload_mib": 10, "tables": 8,
          "ready_boundary": "mariamem.start + SELECT 1, VERSION()"}
(evidence / "python-inputs.json").write_text(json.dumps(inputs, indent=2) + "\n")
destination = evidence / "python-paired-10mib.jsonl"
if destination.exists():
    raise SystemExit("refusing to overwrite Python evidence")
env = os.environ.copy()
env["PYTHONPATH"] = str(source / "python")
env.pop("MARIAMEM_TIMING_DIR", None)

with destination.open("w") as out:
    for block in range(60):
        for workers in ((1, 4) if block % 2 == 0 else (4, 1)):
            name = f"python-{block:02d}-{workers}worker"
            output = temp / f"{name}.json"
            command = [sys.executable, str(observer), "--mode", "fresh", "--host", str(host),
                       "--image", image, "--count", "4", "--workers", str(workers),
                       "--payload-mib", "10", "--tables", "8", "--out", str(output)]
            started = datetime.now(timezone.utc).isoformat()
            proc = subprocess.run(command, cwd=source, env=env, capture_output=True, text=True, timeout=90)
            if proc.returncode:
                raise SystemExit(f"{name} exit={proc.returncode}: {proc.stderr[-2000:]}")
            report = json.loads(output.read_text())
            if report.get("completed") is not True or len(report.get("samples", [])) != 4:
                raise SystemExit(f"{name} incomplete oracles")
            versions = [row["server_version"] for row in report["samples"]]
            if any(not version.startswith("12.3.3") for version in versions):
                raise SystemExit(f"{name} guest version changed: {versions}")
            ready = [row["ready_seconds"] for row in report["samples"]]
            record = {"block": block, "workers": workers, "started_utc": started,
                      "suite_wall_seconds": report["suite_wall_seconds"],
                      "ready_seconds": ready,
                      "prepare_seconds": [row["prepare_seconds"] for row in report["samples"]],
                      "sql_seconds": [row["sql_seconds"] for row in report["samples"]],
                      "cleanup_seconds": [row["cleanup_seconds"] for row in report["samples"]]}
            out.write(json.dumps(record, separators=(",", ":")) + "\n")
            out.flush()
            print(name, round(record["suite_wall_seconds"], 3), round(max(ready), 3), flush=True)
            output.unlink()
