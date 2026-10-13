#!/usr/bin/env python3
"""Bounded, balanced Ubuntu Fresh tail comparison for the v0.5.0 source fix."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import statistics
import subprocess


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def percentile(values, percent):
    ordered = sorted(values)
    return ordered[(len(ordered) * percent + 99) // 100 - 1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--blocks", type=int, default=30)
    args = parser.parse_args()
    if not 1 <= args.blocks <= 60:
        parser.error("blocks must be 1..60")
    args.evidence.mkdir(parents=True, exist_ok=True)
    binaries = {"baseline": args.baseline, "candidate": args.candidate}
    inputs = {
        "utc": datetime.now(timezone.utc).isoformat(),
        "baseline_source_commit": "44100ec676c8c9064f32f3a01bd9a990d487bb61",
        "candidate_review_commit": "8d1628f533b573de3124660613b69703040043d9",
        "binaries_sha256": {arm: sha256(path) for arm, path in binaries.items()},
        "fixture": {"payload_mib": 10, "tables": 8, "workers": 4,
                    "fresh_databases": 4, "workload": "app-connections"},
        "tail_threshold_seconds": 0.9,
        "blocks": args.blocks,
    }
    (args.evidence / "inputs.json").write_text(json.dumps(inputs, indent=2) + "\n")
    records = []
    with (args.evidence / "fresh.jsonl").open("x") as output:
        for block in range(args.blocks):
            order = ("baseline", "candidate") if block % 2 == 0 else ("candidate", "baseline")
            for arm in order:
                report_path = args.evidence / f"trial-{block:02d}-{arm}.json"
                command = [str(binaries[arm]), "-payload-mib", "10", "-tables", "8",
                           "-workers", "4", "-forks", "4", "-workload", "app-connections",
                           "-lifecycle", "fresh", "-label", arm, "-out", str(report_path)]
                run = subprocess.run(command, capture_output=True, text=True, timeout=120)
                if run.returncode:
                    (args.evidence / f"failure-{block:02d}-{arm}.txt").write_text(
                        f"command: {command}\nstdout:\n{run.stdout}\nstderr:\n{run.stderr}\n"
                    )
                    raise RuntimeError(f"{arm} block {block} exited {run.returncode}")
                report = json.loads(report_path.read_text())
                ready = [item["seconds"] for item in report["operations"]
                         if item["name"].startswith("fresh_ready_")]
                if (len(ready) != 4 or report["lifecycle"] != "fresh"
                        or report["workers"] != 4 or report["forks"] != 4):
                    raise RuntimeError(f"incomplete trial {block} {arm}")
                record = {"block": block, "arm": arm, "ready_seconds": ready,
                          "suite_product_seconds": report["suite_product_seconds"],
                          "tail_starts": sum(value >= 0.9 for value in ready)}
                records.append(record)
                output.write(json.dumps(record, separators=(",", ":")) + "\n")
                output.flush()
                report_path.unlink()
                print(block, arm, "max_ready", round(max(ready), 3),
                      "wall", round(record["suite_product_seconds"], 3), flush=True)
    summary = {}
    for arm in binaries:
        subset = [record for record in records if record["arm"] == arm]
        ready = [value for record in subset for value in record["ready_seconds"]]
        summary[arm] = {
            "suites": len(subset), "tail_suites": sum(record["tail_starts"] > 0 for record in subset),
            "starts": len(ready), "tail_starts": sum(value >= 0.9 for value in ready),
            "ready_p50_seconds": statistics.median(ready),
            "ready_p95_nearest_rank_seconds": percentile(ready, 95),
            "ready_max_seconds": max(ready),
            "suite_product_median_seconds": statistics.median(
                record["suite_product_seconds"] for record in subset),
        }
    (args.evidence / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
