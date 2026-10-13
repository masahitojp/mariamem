#!/usr/bin/env python3
"""Capture one slow v0.5.0 diagnostic stack; never use this for frequency."""
import gzip
import json
import os
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parent
evidence = root.parent / "evidence"
binary = root / "ownedprepared-stack"
for index in range(12):
    trace = root / f"stack-probe-{index:02d}"
    trace.mkdir()
    output = root / f"stack-probe-{index:02d}.json"
    env = os.environ.copy()
    env["MARIAMEM_TIMING_DIR"] = str(trace)
    cmd = [str(binary), "-payload-mib", "10", "-tables", "8", "-workers", "4",
           "-forks", "4", "-workload", "app-connections", "-lifecycle", "fresh",
           "-label", "v0.5.0-stack-spike", "-out", str(output)]
    proc = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=90)
    if proc.returncode:
        raise SystemExit(f"trial {index} exited {proc.returncode}: {proc.stderr[-2000:]}")
    result = json.loads(output.read_text())
    ready = [row["seconds"] for row in result["operations"] if row["name"].startswith("fresh_ready_")]
    if len(ready) != 4:
        raise SystemExit(f"trial {index}: missing Starts")
    stacks = sorted(trace.glob("startup-stack-*.txt"))
    print(index, "max_ready", max(ready), "stacks", len(stacks), flush=True)
    if max(ready) >= .9:
        if not stacks:
            raise SystemExit(f"trial {index}: slow Start but no stack")
        metadata = {"trial": index, "ready_seconds": ready,
                    "suite_product_seconds": result["suite_product_seconds"],
                    "stack_files": [p.name for p in stacks],
                    "trace_files": [p.name for p in sorted(trace.glob("*-startup-*.json"))]}
        (evidence / "stack-probe.json").write_text(json.dumps(metadata, indent=2) + "\n")
        for number, path in enumerate(stacks):
            with gzip.open(evidence / f"stack-probe-{number}.txt.gz", "wb") as out:
                out.write(path.read_bytes())
        for number, path in enumerate(sorted(trace.glob("*-startup-*.json"))):
            (evidence / f"stack-probe-trace-{number}.json").write_bytes(path.read_bytes())
        break
else:
    raise SystemExit("no slow Start in 12 diagnostic trials; no path conclusion")
