#!/usr/bin/env python3
"""Bounded v0.5.0 startup-tail capture using the unchanged OwnedPrepared binary."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

root = Path(__file__).resolve().parent
binary = root / "ownedprepared"
cases = {
    "serial-light": (0, 1, 1),
    "serial-10mib": (10, 8, 1),
    "parallel-10mib": (10, 8, 4),
}


def run(case, index, traced):
    payload, tables, workers = cases[case]
    name = f"{case}-{index:03d}-{'trace' if traced else 'plain'}"
    output = root / f"{name}.json"
    command = [str(root / "ownedprepared-spike" if traced else binary), "-payload-mib", str(payload), "-tables", str(tables),
               "-workers", str(workers), "-forks", "4", "-workload", "app-connections",
               "-lifecycle", "fresh", "-label", "v0.5.0", "-out", str(output)]
    env = os.environ.copy()
    env.pop("MARIAMEM_TIMING_DIR", None)
    trace_dir = root / f"campaign-trace-{name}"
    if traced:
        trace_dir.mkdir()
        env["MARIAMEM_TIMING_DIR"] = str(trace_dir)
    began = time.monotonic()
    completed = subprocess.run(command, env=env, capture_output=True, text=True, timeout=90)
    if completed.returncode:
        raise RuntimeError(f"{name} exit={completed.returncode}: {completed.stderr[-2000:]}")
    result = json.loads(output.read_text())
    operations = {v["name"]: v["seconds"] for v in result["operations"]}
    ready = [v for k, v in operations.items() if k.startswith("fresh_ready_")]
    if len(ready) != 4:
        raise RuntimeError(f"{name} missing ready operations")
    traces = []
    if traced:
        for file in sorted(trace_dir.glob("*-startup-*.json")):
            trace = json.loads(file.read_text())
            traces.append({"events": trace["events"], "guest": trace.get("guest")})
        if len(traces) != 4 or any(not t["guest"] for t in traces):
            raise RuntimeError(f"{name} incomplete traces: {len(traces)}")
    record = {"name": name, "case": case, "index": index, "traced": traced,
              "wall_seconds": result["suite_product_seconds"],
              "loop_seconds": result["instance_suite_wall_seconds"],
              "process_seconds": time.monotonic() - began,
              "ready_seconds": ready, "operations": operations, "traces": traces}
    output.unlink()
    if traced:
        for file in trace_dir.iterdir():
            file.unlink()
        trace_dir.rmdir()
    return record


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--plain", type=int, default=100)
    parser.add_argument("--traced", type=int, default=30)
    parser.add_argument("--case", choices=tuple(cases), action="append")
    parser.add_argument("--campaign", default="main")
    args = parser.parse_args()
    selected = args.case or tuple(cases)
    evidence = root.parent / "evidence" / ("samples.jsonl" if args.campaign == "main" else f"samples-{args.campaign}.jsonl")
    metadata = {"binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
                "spike_binary_sha256": hashlib.sha256((root / "ownedprepared-spike").read_bytes()).hexdigest(),
                "source_commit": "44100ec676c8c9064f32f3a01bd9a990d487bb61",
                "tag_object_sha": "bfd854da1cecbe71ad761d1578b3f2c710a1c07f",
                "plain_per_case": args.plain, "traced_per_case": args.traced,
                "thresholds_seconds": [0.5, 0.9]}
    input_name = f"inputs-{args.campaign}{'-traced' if args.plain == 0 else ''}.json"
    (root.parent / "evidence" / input_name).write_text(json.dumps(metadata, indent=2) + "\n")
    with evidence.open("a" if args.plain == 0 else "w") as out:
        for traced, count in ((False, args.plain), (True, args.traced)):
            for index in range(count):
                order = selected if index % 2 == 0 else tuple(reversed(selected))
                for case in order:
                    record = run(case, index, traced)
                    out.write(json.dumps(record, separators=(",", ":")) + "\n")
                    out.flush()
                    print(record["name"], round(record["wall_seconds"], 3),
                          round(max(record["ready_seconds"]), 3), flush=True)


if __name__ == "__main__":
    main()
