"""Run the same Go test binary against the four Sakila deployment modes."""
import argparse
from collections import defaultdict
import json
import os
from pathlib import Path
import re
import statistics
import subprocess
import sys
import tempfile
import time


MODES = ("mariamem", "testcontainers", "mysql", "docker")


def capture(args, backend, path, expected_cases):
    path.unlink(missing_ok=True)
    start = time.monotonic_ns()
    process = subprocess.run(
        [str(args.binary.resolve()), "-test.run=^TestSakila$", "-test.parallel=8",
         "-test.timeout=4m", f"-sakila.backend={backend}", f"-sakila.image={args.image}",
         f"-sakila.metrics={path}"],
        text=True, capture_output=True, timeout=270,
    )
    if process.returncode:
        raise RuntimeError(f"{backend} failed\n{process.stdout}\n{process.stderr}")
    wall_ms = (time.monotonic_ns() - start) / 1_000_000
    report = json.loads(path.read_text())
    assert (report["backend"], report["parallel"], report["reads"], report["writes"]) == (backend, 8, 50, 50)
    assert len(report["source_commit"]) == 40
    phases = report["phases"]
    cases = {(item["name"], item["case"]) for item in phases if item["name"] in ("read", "write")}
    assert len(cases) == 100
    assert sum(item["name"] in ("read", "write") for item in phases) == 100
    variants = defaultdict(set)
    for stage, case in cases:
        scenario, variant = case.split("/")
        variants[stage, scenario].add(int(variant))
    for stage in ("read", "write"):
        groups = [ids for (group, _), ids in variants.items() if group == stage]
        assert len(groups) == 5
        assert all(ids == set(range(1, 11)) for ids in groups)
    if expected_cases is not None:
        assert cases == expected_cases
    assert sum(item["name"] == "fork" for item in phases) == (51 if backend == "mariamem" else 0)
    assert sum(item["name"] == "reset" for item in phases) == (0 if backend == "mariamem" else 50)
    report["process_wall_ms"] = wall_ms
    return report, cases


def run(args):
    if not os.environ.get("SAKILA_MYSQL_DSN"):
        raise ValueError("SAKILA_MYSQL_DSN must point to the already running MySQL server")
    if not re.search(r"@sha256:[0-9a-f]{64}$", args.image):
        raise ValueError("provide the managed MySQL image by immutable digest")
    expected_cases = None
    with tempfile.TemporaryDirectory(prefix="sakila-modelcase-") as temporary:
        path = Path(temporary) / "report.json"
        for sample in range(args.runs + 1):
            offset = sample % len(MODES)
            for backend in MODES[offset:] + MODES[:offset]:
                report, expected_cases = capture(args, backend, path, expected_cases)
                report["sample"] = sample
                print(json.dumps(report, separators=(",", ":")), flush=True)
                print(f"{backend} sample {sample}: 100 cases", file=sys.stderr, flush=True)


def compact(source, destination):
    rows = [json.loads(line) for line in source.read_text().splitlines()]
    medians = set()
    for backend in MODES:
        measured = [r for r in rows if r["backend"] == backend and r["sample"]]
        middle = statistics.median(r["process_wall_ms"] for r in measured)
        representative = min(measured, key=lambda r: (abs(r["process_wall_ms"] - middle), r["sample"]))
        medians.add((backend, representative["sample"]))

    destination.mkdir(parents=True, exist_ok=True)
    median_traces = []
    with (destination / "samples.jsonl").open("w") as output:
        for row in rows:
            phases = row["phases"]
            if (row["backend"], row["sample"]) in medians:
                median_traces.append({"backend": row["backend"], "sample": row["sample"], "phases": phases})
            groups = defaultdict(list)
            for phase in phases:
                groups[phase["name"]].append(phase)
            row["stage_totals"] = {
                name: {"count": len(items), "sum_ms": sum(p["to_ms"] - p["from_ms"] for p in items)}
                for name, items in groups.items()
            }
            row["phases"] = groups["ready"]
            print(json.dumps(row, separators=(",", ":")), file=output)
    with (destination / "median-phases.jsonl").open("w") as output:
        for row in median_traces:
            print(json.dumps(row, separators=(",", ":")), file=output)


def summarize(path):
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    groups = {mode: sorted((r for r in rows if r["backend"] == mode), key=lambda r: r["sample"]) for mode in MODES}
    samples = [r["sample"] for r in groups["mariamem"]]
    if samples != list(range(len(samples))) or len(samples) < 2 or any(
        [r["sample"] for r in group] != samples for group in groups.values()
    ):
        raise ValueError("the input does not contain complete matched samples")
    if len({r["source_commit"] for r in rows}) != 1:
        raise ValueError("mixed source commits")
    if len({r["version"] for r in rows if r["backend"] != "mariamem"}) != 1:
        raise ValueError("shared server versions differ")
    print("backend,version,ready_median_ms,suite_median_ms,wall_median_ms,wall_min_ms,wall_max_ms")
    for backend, group in groups.items():
        measured = group[1:]
        ready = [next(p["to_ms"] - p["from_ms"] for p in r["phases"] if p["name"] == "ready") for r in measured]
        suite = [r["total_ms"] for r in measured]
        wall = [r["process_wall_ms"] for r in measured]
        values = (statistics.median(ready), statistics.median(suite), statistics.median(wall), min(wall), max(wall))
        print(",".join((backend, measured[0]["version"], *(f"{value:.2f}" for value in values))))


def main():
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    execute = commands.add_parser("run")
    execute.add_argument("binary", type=Path)
    execute.add_argument("image")
    execute.add_argument("--runs", type=int, default=5)
    summary = commands.add_parser("summarize")
    summary.add_argument("samples", type=Path)
    reduce_evidence = commands.add_parser("compact")
    reduce_evidence.add_argument("samples", type=Path)
    reduce_evidence.add_argument("destination", type=Path)
    args = parser.parse_args()
    if args.command == "run":
        if args.runs < 1:
            parser.error("--runs must be positive")
        run(args)
    elif args.command == "summarize":
        summarize(args.samples)
    else:
        compact(args.samples, args.destination)


if __name__ == "__main__":
    main()
