#!/usr/bin/env python3
"""Reduce paired product-suite records without pseudo-independent Starts."""
import json
import math
from pathlib import Path
import statistics

root = Path(__file__).resolve().parents[3]
evidence = root / "benchmarks/v050-startup-tail-wakeup-evidence"


def wilson(k, n):
    z = 1.959963984540054
    p = k / n
    d = 1 + z*z/n
    center = (p + z*z/(2*n))/d
    radius = z*math.sqrt(p*(1-p)/n + z*z/(4*n*n))/d
    return [center-radius, center+radius]


output = {"threshold_seconds": .9, "languages": {}}
for language in ("go", "python"):
    rows = [json.loads(line) for line in (evidence / f"comparison-{language}.jsonl").read_text().splitlines()]
    if len(rows) != 60:
        raise SystemExit(f"incomplete {language} comparison: {len(rows)}/60")
    blocks = {}
    for row in rows:
        group = blocks.setdefault(row["block"], {})
        if row["arm"] in group:
            raise SystemExit(f"duplicate {language} block {row['block']}")
        group[row["arm"]] = row
        if row["tail_starts"] != sum(value >= .9 for value in row["ready_seconds"]):
            raise SystemExit("tail count mismatch")
    if set(blocks) != set(range(30)) or any(set(pair) != {"baseline", "candidate"} for pair in blocks.values()):
        raise SystemExit(f"missing {language} block/arm")
    payload = {"blocks": 30, "arms": {}}
    for arm in ("baseline", "candidate"):
        group = [blocks[index][arm] for index in range(30)]
        suites = sum(row["tail_starts"] > 0 for row in group)
        payload["arms"][arm] = {
            "suites": 30, "starts": 120, "tail_suites": suites,
            "tail_starts": sum(row["tail_starts"] for row in group),
            "tail_suite_rate_wilson95": wilson(suites, 30),
            "suite_wall_median_seconds": statistics.median(row["wall_seconds"] for row in group),
            "suite_wall_min_seconds": min(row["wall_seconds"] for row in group),
            "suite_wall_max_seconds": max(row["wall_seconds"] for row in group),
            "max_ready_median_seconds": statistics.median(max(row["ready_seconds"]) for row in group),
        }
    differences = {kind: [] for kind in ("all", "baseline_fast", "baseline_tail")}
    pairs = {kind: 0 for kind in ("baseline_only_tail", "candidate_only_tail", "both_tail", "neither_tail")}
    for block in blocks.values():
        baseline, candidate = block["baseline"], block["candidate"]
        base_tail = baseline["tail_starts"] > 0
        cand_tail = candidate["tail_starts"] > 0
        pairs["both_tail" if base_tail and cand_tail else
              "baseline_only_tail" if base_tail else
              "candidate_only_tail" if cand_tail else "neither_tail"] += 1
        difference = candidate["wall_seconds"] - baseline["wall_seconds"]
        differences["all"].append(difference)
        differences["baseline_tail" if base_tail else "baseline_fast"].append(difference)
    payload["paired_tail_suites"] = pairs
    payload["candidate_minus_baseline_wall_median_seconds"] = {
        kind: statistics.median(values) if values else None for kind, values in differences.items()}
    output["languages"][language] = payload

(evidence / "comparison-summary.json").write_text(json.dumps(output, indent=2) + "\n")
print(json.dumps(output, indent=2))
