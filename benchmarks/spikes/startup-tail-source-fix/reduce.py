#!/usr/bin/env python3
"""Reduce balanced Fresh records without discarding any completed suite."""

import json
from pathlib import Path
import statistics

ROOT = Path(__file__).resolve().parents[4]
EVIDENCE = ROOT / "evidence"


def reduce(language):
    rows = [json.loads(line) for line in (EVIDENCE / f"source-fix-{language}.jsonl").read_text().splitlines()]
    assert len(rows) == 60
    arms = {arm: {row["block"]: row for row in rows if row["arm"] == arm}
            for arm in ("baseline", "candidate")}
    assert set(arms["baseline"]) == set(arms["candidate"]) == set(range(30))
    result = {}
    for arm, blocks in arms.items():
        values = list(blocks.values())
        result[arm] = {
            "suites": len(values),
            "tail_suites": sum(row["tail_starts"] > 0 for row in values),
            "tail_starts": sum(row["tail_starts"] for row in values),
            "starts": sum(len(row["ready_seconds"]) for row in values),
            "wall_median_seconds": statistics.median(row["wall_seconds"] for row in values),
        }
    result["paired_candidate_minus_baseline_wall_median_seconds"] = statistics.median(
        arms["candidate"][i]["wall_seconds"] - arms["baseline"][i]["wall_seconds"]
        for i in range(30))
    return result


if __name__ == "__main__":
    print(json.dumps({language: reduce(language) for language in ("go", "python")}, indent=2))
