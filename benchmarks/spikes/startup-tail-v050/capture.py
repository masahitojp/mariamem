#!/usr/bin/env python3
"""Bounded v0.5.0 condition-order diagnostic: three slow Starts or 60 suites."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess


root = Path(__file__).resolve().parents[3]
workspace = root.parent
binary = workspace / "temp" / "ownedprepared-order"
evidence = workspace / "evidence"
expected_binary = "c021e8336a50cd90004b6d7d37c3ce703f68b8d6bbd67644a8ec4c9b337fd656"
actual_binary = hashlib.sha256(binary.read_bytes()).hexdigest()
if actual_binary != expected_binary:
    raise SystemExit(f"diagnostic binary identity differs: {actual_binary}")
observations = evidence / "observations.jsonl"
if observations.exists():
    raise SystemExit(f"refusing to overwrite {observations}")

inputs = {
    "release_source_commit": "44100ec676c8c9064f32f3a01bd9a990d487bb61",
    "release_tag_object_sha": "bfd854da1cecbe71ad761d1578b3f2c710a1c07f",
    "parent_experiment_commit": "40c8e773592ebe914c466a7dce8fe3e57dbeb0e5",
    "guest_sha256": "7c7b6ce5168a1a0d98019751b4c36c25f2e9948dbae0124ec3f434efb0b8642c",
    "diagnostic_binary_sha256": actual_binary,
    "stop": "3 ready >=900 ms, or 60 four-parallel suites including focused pilot",
    "command": ["-payload-mib", "10", "-tables", "8", "-workers", "4", "-forks", "4",
                "-workload", "app-connections", "-lifecycle", "fresh", "-label", "v0.5.0"],
}
(evidence / "inputs.json").write_text(json.dumps(inputs, indent=2) + "\n")


def collect(index: int, result_path: Path, trace_path: Path, out):
    result = json.loads(result_path.read_text())
    trace = json.loads(trace_path.read_text())
    ready = [op["seconds"] for op in result["operations"] if op["name"].startswith("fresh_ready_")]
    if len(ready) != 4 or trace["dropped"]:
        raise RuntimeError(f"invalid trial {index}: ready={len(ready)}, dropped={trace['dropped']}")
    if len({ev["instance"] for ev in trace["events"] if ev["kind"] == "main-target-set"}) != 4:
        raise RuntimeError(f"missing startup events in trial {index}")
    record = {"trial": index, "ready_seconds": ready,
              "suite_product_seconds": result["suite_product_seconds"],
              "slow_starts": sum(value >= .9 for value in ready),
              "events": len(trace["events"]), "dropped": trace["dropped"],
              "trace": trace_path.name}
    out.write(json.dumps(record, separators=(",", ":")) + "\n")
    out.flush()
    print(index, "ready", [round(value, 3) for value in ready],
          "slow", record["slow_starts"], "events", record["events"], flush=True)
    return record["slow_starts"]


slow = 0
with observations.open("w") as out:
    # The narrowed-instrumentation pilot is valid and counts as suite zero.
    pilot_result = workspace / "temp" / "result-pilot2.json"
    pilot_trace = workspace / "temp" / "trace-pilot2.json"
    first_trace = evidence / "trace-000.json"
    shutil.copyfile(pilot_trace, first_trace)
    slow += collect(0, pilot_result, first_trace, out)
    for index in range(1, 60):
        if slow >= 3:
            break
        trace_path = evidence / f"trace-{index:03d}.json"
        result_path = workspace / "temp" / f"result-{index:03d}.json"
        command = [str(binary), *inputs["command"], "-out", str(result_path)]
        env = os.environ.copy()
        env["MARIAMEM_SPIKE_TRACE"] = str(trace_path)
        completed = subprocess.run(command, env=env, capture_output=True, text=True, timeout=90)
        if completed.returncode:
            (evidence / f"failure-{index:03d}.txt").write_text(completed.stderr)
            raise RuntimeError(f"trial {index} failed: {completed.returncode}")
        slow += collect(index, result_path, trace_path, out)
        result_path.unlink()
print(f"captured {slow} slow Starts in {sum(1 for _ in observations.open())} suites")
