#!/usr/bin/env python3
"""Classify only the first startup flush request of each traced instance."""
from __future__ import annotations

from collections import defaultdict
import hashlib
import json
from pathlib import Path


root = Path(__file__).resolve().parents[3]
evidence = root / "benchmarks/v050-startup-tail-wakeup-evidence"
observations = [json.loads(line) for line in (evidence / "observations.jsonl").read_text().splitlines()]
if not observations or len(observations) > 60:
    raise SystemExit("invalid bounded cohort")


def first_after(events, kind, seq):
    return next((event for event in events if event["kind"] == kind and event["seq"] > seq), None)


def first_before(events, kind, seq):
    return next((event for event in reversed(events) if event["kind"] == kind and event["seq"] < seq), None)


records = []
for observed in observations:
    path = evidence / observed["trace"]
    data = json.loads(path.read_text())
    if data["dropped"] or len(data["events"]) != observed["events"]:
        raise SystemExit(f"incomplete trace: {path}")
    groups = defaultdict(list)
    for event in data["events"]:
        groups[event["instance"]].append(event)
    startup = [events for events in groups.values() if any(e["kind"] == "main-target-set" for e in events)]
    if len(startup) != 4:
        raise SystemExit(f"missing startup instances: {path}")
    for events in startup:
        target = next(e for e in events if e["kind"] == "main-target-set")
        signal = first_after(events, "cond-signal-head", target["seq"])
        before = first_before(events, "cleaner-target-before-lock", target["seq"])
        after = first_after(events, "cleaner-after-lock", target["seq"])
        register = first_after(events, "cond-register", target["seq"])
        wait = first_after(events, "cond-wait-enter", target["seq"])
        returned = first_after(events, "cond-wait-return", wait["seq"]) if wait else None
        if not all((before, signal, after, register, wait, returned)):
            raise SystemExit(f"incomplete first flush events: {path} {target['instance']}")
        order = [before["seq"], target["seq"], signal["seq"], after["seq"], register["seq"], wait["seq"], returned["seq"]]
        slow_order = (order == sorted(order) and before.get("a", 0) == 0
                      and target.get("a", 0) > 0 and signal.get("a", 0) == 0
                      and after.get("b", 0) > 0 and wait.get("c", 0) >= 900_000_000
                      and returned.get("b", 0) == -73
                      and returned["ns"] - wait["ns"] >= 900_000_000)
        records.append({
            "trial": observed["trial"], "instance": target["instance"],
            "trace": path.name, "trace_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "first_flush_order": {e["kind"]: {"seq": e["seq"], "ns": e["ns"],
                                              "a": e.get("a", 0), "b": e.get("b", 0), "c": e.get("c", 0)}
                                  for e in (before, target, signal, after, register, wait, returned)},
            "wait_elapsed_ms": (returned["ns"] - wait["ns"]) / 1e6,
            "observed_early_empty_signal_timeout": slow_order,
        })

if len(records) != len(observations) * 4:
    raise SystemExit("instance count mismatch")
ready_slow = sum(row["slow_starts"] for row in observations)
classified = sum(row["observed_early_empty_signal_timeout"] for row in records)
if ready_slow != classified:
    raise SystemExit(f"ready/ordering mismatch: {ready_slow} vs {classified}")
summary = {"suites": len(observations), "starts": len(records), "ready_slow_starts": ready_slow,
           "early_empty_signal_timeout_starts": classified,
           "all_traces_complete": True, "instances": records}
(evidence / "ordering-summary.json").write_text(json.dumps(summary, indent=2) + "\n")
print(json.dumps({key: value for key, value in summary.items() if key != "instances"}, indent=2))
