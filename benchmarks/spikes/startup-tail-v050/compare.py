#!/usr/bin/env python3
"""Balanced four-Fresh baseline/candidate comparison; product oracles unchanged."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


root = Path(__file__).resolve().parents[3]
workspace = root.parent
temp = workspace / "temp"
evidence = workspace / "evidence"
release = Path("/private/tmp/mariamem-v050-release-clone")
expected = {
    "ownedprepared-baseline": "528e8aa0e28b563d960e3a472d6e117617972ea58178dcee1411e28ba6aca244",
    "ownedprepared-candidate": "c81ac4da0fb6d83800741f62b4d13885332fb6feb65f4fa97518939e039229e5",
    "mariamem-host-baseline": "b2b8a9e88e238ede252d8290897b269ce7c09823e6fd9622fdb9a0dcde48dc66",
    "mariamem-host-candidate": "8e7038567300ed936b9240215a8631a38009081b35731a078e39595782751fea",
}
for filename, wanted in expected.items():
    actual = hashlib.sha256((temp / filename).read_bytes()).hexdigest()
    if actual != wanted:
        raise SystemExit(f"binary mismatch {filename}: {actual}")
if subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=release, text=True).strip() != "44100ec676c8c9064f32f3a01bd9a990d487bb61":
    raise SystemExit("v0.5.0 source identity changed")

parser = argparse.ArgumentParser()
parser.add_argument("language", choices=("go", "python"))
parser.add_argument("--blocks", type=int, default=30)
args = parser.parse_args()
if not 1 <= args.blocks <= 30:
    raise SystemExit("bounded comparison requires 1..30 blocks")
destination = evidence / f"comparison-{args.language}.jsonl"
if destination.exists():
    raise SystemExit(f"refusing to overwrite {destination}")

inputs = {"language": args.language, "blocks": args.blocks, "source_commit": "44100ec676c8c9064f32f3a01bd9a990d487bb61",
          "binaries": expected, "go_version": "go1.26.8", "python": sys.version,
          "payload_mib": 10, "tables": 8, "fresh_dbs": 4, "workers": 4,
          "candidate_boundary": "disposable generated-code hypothesis; canonical guest not rebuilt"}
(evidence / f"comparison-{args.language}-inputs.json").write_text(json.dumps(inputs, indent=2) + "\n")

image = "mariadb@sha256:805c8e104bd563d5bfa24fadd3f31cd419ea859cb5277f32b5db714f9ed1"
python_observer = release / "benchmarks/python_product_suites.py"
env = os.environ.copy()
env["PYTHONPATH"] = str(release / "python")
env.pop("MARIAMEM_TIMING_DIR", None)
env.pop("MARIAMEM_SPIKE_TRACE", None)

with destination.open("w") as out:
    for block in range(args.blocks):
        order = ("baseline", "candidate") if block % 2 == 0 else ("candidate", "baseline")
        for arm in order:
            output = temp / f"compare-{args.language}-{block:02d}-{arm}.json"
            if args.language == "go":
                command = [str(temp / f"ownedprepared-{arm}"), "-payload-mib", "10", "-tables", "8",
                           "-workers", "4", "-forks", "4", "-workload", "app-connections",
                           "-lifecycle", "fresh", "-label", f"v0.5.0-{arm}", "-out", str(output)]
                cwd = release
            else:
                command = [sys.executable, str(python_observer), "--mode", "fresh",
                           "--host", str(temp / f"mariamem-host-{arm}"), "--image", image,
                           "--count", "4", "--workers", "4", "--payload-mib", "10", "--tables", "8",
                           "--out", str(output)]
                cwd = release
            started = datetime.now(timezone.utc).isoformat()
            proc = subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True, timeout=90)
            if proc.returncode:
                (evidence / f"comparison-{args.language}-failure-{block:02d}-{arm}.txt").write_text(proc.stderr)
                raise RuntimeError(f"{args.language} block {block} {arm} failed: {proc.returncode}")
            report = json.loads(output.read_text())
            if args.language == "go":
                ready = [op["seconds"] for op in report["operations"] if op["name"].startswith("fresh_ready_")]
                wall = report["suite_product_seconds"]
            else:
                if report.get("completed") is not True or len(report.get("samples", [])) != 4:
                    raise RuntimeError(f"incomplete Python oracle: block {block} {arm}")
                if any(not row["server_version"].startswith("12.3.3") for row in report["samples"]):
                    raise RuntimeError(f"unexpected Python guest version: block {block} {arm}")
                ready = [row["ready_seconds"] for row in report["samples"]]
                wall = report["suite_wall_seconds"]
            if len(ready) != 4:
                raise RuntimeError(f"missing ready sample: block {block} {arm}")
            record = {"block": block, "arm": arm, "started_utc": started,
                      "wall_seconds": wall, "ready_seconds": ready,
                      "tail_starts": sum(value >= .9 for value in ready)}
            out.write(json.dumps(record, separators=(",", ":")) + "\n")
            out.flush()
            output.unlink()
            print(args.language, block, arm, round(wall, 3), round(max(ready), 3), flush=True)
