#!/usr/bin/env python3
"""Summarize checkpoints without deleting slow or failed generations."""
import argparse
import hashlib
import json
from pathlib import Path
import statistics


def percentile(values, fraction):
    values = sorted(values)
    position = (len(values) - 1) * fraction
    lo = int(position)
    hi = min(lo + 1, len(values) - 1)
    return values[lo] + (values[hi] - values[lo]) * (position - lo)


def window(rows):
    result = {"generations": [rows[0]["generation"], rows[-1]["generation"]]}
    for key in ("ready_seconds", "use_seconds", "close_seconds", "cpu_seconds"):
        values = [row[key] for row in rows]
        result[key] = {"min": min(values), "p50": statistics.median(values),
                       "p95": percentile(values, 0.95), "max": max(values)}
    for phase in ("ready", "after_close"):
        result[phase] = {}
        for key in ("heap_alloc_bytes", "heap_inuse_bytes", "heap_idle_bytes",
                    "heap_released_bytes", "sys_bytes", "fds", "goroutines"):
            values = [row[phase][key] for row in rows]
            result[phase][key] = {"min": min(values), "p50": statistics.median(values), "max": max(values)}
        for key in ("rss_bytes", "primary_bytes"):
            values = [row[phase]["os"][key] for row in rows]
            result[phase][key] = {"min": min(values), "p50": statistics.median(values), "max": max(values)}
    result["failures"] = [dict(generation=row["generation"], errors=row["errors"])
                          for row in rows if row["errors"]]
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    raw = (args.work / "checkpoints.jsonl").read_bytes()
    checkpoints = [json.loads(line) for line in raw.splitlines()]
    rows = [row for row in checkpoints if "generation" in row and "before" in row]
    if not rows:
        raise SystemExit("No generation checkpoints")
    evidence = {"metadata": json.loads((args.work / "metadata.json").read_text()),
                "raw_sha256": hashlib.sha256(raw).hexdigest(),
                "baseline": checkpoints[0], "raw_generations": rows,
                "terminal_records": [row for row in checkpoints if row.get("type") in ("completed", "stop")],
                "all": window(rows), "windows": [window(rows[i:i+10]) for i in range(0, len(rows), 10)],
                "allocation_bytes": rows[-1]["after_close"]["total_alloc_bytes"] - rows[0]["before"]["total_alloc_bytes"],
                "automatic_gc_cycles": rows[-1]["after_close"]["num_gc"] - rows[0]["before"]["num_gc"]}
    args.output.write_text(json.dumps(evidence, indent=2) + "\n")


if __name__ == "__main__":
    main()
