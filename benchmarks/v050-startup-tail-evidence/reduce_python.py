#!/usr/bin/env python3
"""Group-level reduction of Python Fresh controls."""
import collections
import json
import math
from pathlib import Path
import statistics

here = Path(__file__).resolve().parent
evidence = here if (here / "python-paired-10mib.jsonl").exists() else here.parent / "evidence"
rows = [json.loads(line) for line in (evidence / "python-paired-10mib.jsonl").read_text().splitlines()]
if len(rows) != 120:
    raise SystemExit(f"incomplete Python cohort: {len(rows)}/120")
groups = collections.defaultdict(dict)
for row in rows:
    if row["workers"] in groups[row["block"]]:
        raise SystemExit("duplicate Python block/arm")
    groups[row["block"]][row["workers"]] = row
if len(groups) != 60 or any(set(group) != {1, 4} for group in groups.values()):
    raise SystemExit("missing Python block/arm")


def wilson(success, total):
    z = 1.959963984540054
    p = success/total
    d = 1+z*z/total
    c = (p+z*z/(2*total))/d
    h = z*math.sqrt(p*(1-p)/total+z*z/(4*total*total))/d
    return [c-h, c+h]


summary = {"source": "python-paired-10mib.jsonl", "blocks": 60, "arms": {}}
for workers in (1, 4):
    arm = [groups[block][workers] for block in range(60)]
    result = {"suites": 60, "starts": 240,
              "suite_wall_median_seconds": statistics.median(row["suite_wall_seconds"] for row in arm)}
    for threshold in (.5, .9):
        tail = [row for row in arm if max(row["ready_seconds"]) >= threshold]
        fast = [row for row in arm if max(row["ready_seconds"]) < threshold]
        result[f"ready_ge_{int(threshold*1000)}ms"] = {
            "suites": len(tail), "suite_rate_wilson95": wilson(len(tail), 60),
            "starts": sum(sum(value >= threshold for value in row["ready_seconds"]) for row in arm),
            "slow_suite_wall_median": statistics.median(row["suite_wall_seconds"] for row in tail) if tail else None,
            "fast_suite_wall_median": statistics.median(row["suite_wall_seconds"] for row in fast) if fast else None,
            "tail_starts_per_suite_histogram": dict(collections.Counter(
                sum(value >= threshold for value in row["ready_seconds"]) for row in arm))}
    summary["arms"][str(workers)] = result
summary["order"] = {
    "serial_first": sum(groups[block][1]["started_utc"] < groups[block][4]["started_utc"] for block in range(60)),
    "parallel_first": sum(groups[block][4]["started_utc"] < groups[block][1]["started_utc"] for block in range(60)),
}
(evidence / "python-summary.json").write_text(json.dumps(summary, indent=2) + "\n")
print(json.dumps(summary, indent=2))
