#!/usr/bin/env python3
"""Reduce bounded suite/start observations without treating Starts as independent."""
import collections
import json
import math
from pathlib import Path
import statistics

here = Path(__file__).resolve().parent
evidence = here if (here / "paired-10mib.jsonl").exists() else here.parent / "evidence"
rows = [json.loads(line) for line in (evidence / "paired-10mib.jsonl").read_text().splitlines()]
if len(rows) != 180:
    raise SystemExit(f"incomplete paired cohort: {len(rows)}/180")
arms = {("serial-10mib", False): "serial_plain",
        ("parallel-10mib", False): "parallel_plain",
        ("parallel-10mib", True): "parallel_trace"}
blocks = collections.defaultdict(dict)
for row in rows:
    arm = arms[(row["case"], row["traced"])]
    if arm in blocks[row["block"]]:
        raise SystemExit(f"duplicate block/arm: {row['block']} {arm}")
    blocks[row["block"]][arm] = row
if len(blocks) != 60 or any(set(group) != set(arms.values()) for group in blocks.values()):
    raise SystemExit("missing block or arm")


def wilson(success, total):
    z = 1.959963984540054
    p = success / total
    d = 1 + z*z/total
    c = (p + z*z/(2*total)) / d
    h = z*math.sqrt(p*(1-p)/total + z*z/(4*total*total)) / d
    return [c-h, c+h]


def quantiles(values):
    values = sorted(values)
    return {"min": values[0], "median": statistics.median(values),
            "p90_nearest_rank": values[math.ceil(.9*len(values))-1], "max": values[-1]}


def guest_init_seconds(trace):
    events = {event["name"]: event["offset_ns"] for event in trace["guest"]["events"]}
    return (events["server_init_complete"] - events["server_init_begin"]) / 1e9


summary = {"source": "paired-10mib.jsonl", "blocks": 60,
           "thresholds_seconds": [.5, .9], "arms": {}}
for key in arms.values():
    group = [blocks[index][key] for index in range(60)]
    payload = {"suites": len(group), "starts": 4*len(group),
               "suite_wall_seconds": quantiles([row["wall_seconds"] for row in group]),
               "max_ready_seconds": quantiles([max(row["ready_seconds"]) for row in group])}
    for threshold in (.5, .9):
        tail = [row for row in group if max(row["ready_seconds"]) >= threshold]
        fast = [row for row in group if max(row["ready_seconds"]) < threshold]
        label = f"ready_ge_{int(threshold*1000)}ms"
        payload[label] = {"suites": len(tail), "suite_rate": len(tail)/len(group),
                          "suite_rate_wilson95": wilson(len(tail), len(group)),
                          "starts": sum(sum(value >= threshold for value in row["ready_seconds"]) for row in group),
                          "slow_suite_wall_median": statistics.median(row["wall_seconds"] for row in tail) if tail else None,
                          "fast_suite_wall_median": statistics.median(row["wall_seconds"] for row in fast) if fast else None,
                          "tail_starts_per_suite_histogram": dict(collections.Counter(
                              sum(value >= threshold for value in row["ready_seconds"]) for row in group))}
    if key == "parallel_trace":
        intervals = []
        host_intervals = []
        mismatches = 0
        trace_mismatches = 0
        for row in group:
            if len(row["traces"]) != 4 or any("guest" not in trace for trace in row["traces"]):
                raise SystemExit(f"missing guest trace: {row['name']}")
            current = [guest_init_seconds(trace) for trace in row["traces"]]
            host = []
            for trace in row["traces"]:
                events = {event["name"]: event["offset_ns"] for event in trace["events"]}
                host.append((events["ready_header_received"] - events["linked_execution_begin"]) / 1e9)
            intervals.extend(current)
            host_intervals.extend(host)
            mismatches += sum(value >= .9 for value in current) != sum(value >= .9 for value in row["ready_seconds"])
            trace_mismatches += sum((guest >= .9) != (seen >= .9) for guest, seen in zip(current, host))
        slow = [(seen, guest) for seen, guest in zip(host_intervals, intervals) if guest >= .9]
        fast = [(seen, guest) for seen, guest in zip(host_intervals, intervals) if guest < .9]
        payload["guest_server_init"] = {"seconds": quantiles(intervals),
                                       "starts_ge_900ms": sum(value >= .9 for value in intervals),
                                       "suite_tail_count_mismatches": mismatches,
                                       "per_trace_host_guest_tail_mismatches": trace_mismatches,
                                       "slow_host_median_seconds": statistics.median(seen for seen, _ in slow),
                                       "slow_guest_median_seconds": statistics.median(guest for _, guest in slow),
                                       "slow_host_minus_guest_median_seconds": statistics.median(seen-guest for seen, guest in slow),
                                       "fast_host_median_seconds": statistics.median(seen for seen, _ in fast),
                                       "fast_guest_median_seconds": statistics.median(guest for _, guest in fast)}
    summary["arms"][key] = payload

pair = []
for index in range(60):
    plain = blocks[index]["parallel_plain"]
    traced = blocks[index]["parallel_trace"]
    plain_before = plain["started_utc"] < traced["started_utc"]
    pair.append({"block": index, "plain_before_trace": plain_before,
                 "plain_tail": max(plain["ready_seconds"]) >= .9,
                 "trace_tail": max(traced["ready_seconds"]) >= .9,
                 "plain_wall": plain["wall_seconds"], "trace_wall": traced["wall_seconds"]})
summary["paired_parallel"] = {
    "plain_before_trace_blocks": sum(row["plain_before_trace"] for row in pair),
    "trace_before_plain_blocks": sum(not row["plain_before_trace"] for row in pair),
    "plain_tail_when_plain_first": sum(row["plain_tail"] and row["plain_before_trace"] for row in pair),
    "plain_tail_when_trace_first": sum(row["plain_tail"] and not row["plain_before_trace"] for row in pair),
    "trace_tail_when_plain_first": sum(row["trace_tail"] and row["plain_before_trace"] for row in pair),
    "trace_tail_when_trace_first": sum(row["trace_tail"] and not row["plain_before_trace"] for row in pair),
    "both_fast_blocks": sum(not row["plain_tail"] and not row["trace_tail"] for row in pair),
    "trace_minus_plain_wall_median_both_fast": statistics.median(
        row["trace_wall"]-row["plain_wall"] for row in pair
        if not row["plain_tail"] and not row["trace_tail"]),
}
(evidence / "paired-summary.json").write_text(json.dumps(summary, indent=2) + "\n")
print(json.dumps(summary, indent=2))
