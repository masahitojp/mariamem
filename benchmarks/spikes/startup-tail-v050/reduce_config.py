#!/usr/bin/env python3
"""Reduce complete balanced InnoDB setting blocks; incomplete input fails."""
from __future__ import annotations

import json
from pathlib import Path
from statistics import median


ROOT = Path(__file__).resolve().parents[3]
WORK = ROOT.parent
EVIDENCE = WORK / "evidence"
INPUT = EVIDENCE / "config-comparison-unrestricted.jsonl"
OUTPUT = EVIDENCE / "config-summary.json"


def main() -> None:
    records = [json.loads(line) for line in INPUT.read_text().splitlines()]
    if len(records) != 60:
        raise SystemExit(f"expected 60 records for 30 complete blocks, got {len(records)}")
    blocks = {}
    for record in records:
        block = record["block"]
        arm = record["arm"]
        if block not in range(30) or arm not in ("flush-sync-0", "flush-sync-1"):
            raise SystemExit("unexpected block or arm")
        if arm in blocks.setdefault(block, {}):
            raise SystemExit("duplicate block arm")
        if len(record["ready_seconds"]) != 4:
            raise SystemExit("incomplete suite")
        blocks[block][arm] = record
    if any(set(block) != {"flush-sync-0", "flush-sync-1"} for block in blocks.values()):
        raise SystemExit("incomplete pair")
    summary = {"blocks": 30, "tail_threshold_seconds": .9, "arms": {}}
    for value in (1, 0):
        arm = f"flush-sync-{value}"
        rows = [blocks[i][arm] for i in range(30)]
        fast = [r for r in rows if not r["tail_starts"]]
        slow = [r for r in rows if r["tail_starts"]]
        summary["arms"][arm] = {
            "tail_suites": len(slow), "tail_starts": sum(r["tail_starts"] for r in rows),
            "suite_wall_median_seconds": median(r["suite_wall_seconds"] for r in rows),
            "fast_suite_wall_median_seconds": median(r["suite_wall_seconds"] for r in fast) if fast else None,
            "tail_suite_wall_median_seconds": median(r["suite_wall_seconds"] for r in slow) if slow else None,
            "ready_median_seconds": median(x for r in rows for x in r["ready_seconds"]),
        }
    on_only = off_only = both = neither = 0
    paired_wall = []
    for block in range(30):
        on = blocks[block]["flush-sync-1"]
        off = blocks[block]["flush-sync-0"]
        on_tail, off_tail = bool(on["tail_starts"]), bool(off["tail_starts"])
        if on_tail and off_tail:
            both += 1
        elif on_tail:
            on_only += 1
        elif off_tail:
            off_only += 1
        else:
            neither += 1
        paired_wall.append(off["suite_wall_seconds"] - on["suite_wall_seconds"])
    summary["paired"] = {"both_tail": both, "on_only_tail": on_only,
                         "off_only_tail": off_only, "neither_tail": neither,
                         "off_minus_on_wall_median_seconds": median(paired_wall)}
    OUTPUT.write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
