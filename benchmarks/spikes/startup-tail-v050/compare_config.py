#!/usr/bin/env python3
"""Balanced v0.5.0 four-Fresh comparison for InnoDB flush-sync ON/OFF."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[3]
WORK = ROOT.parent
TEMP = WORK / "temp"
EVIDENCE = WORK / "evidence"
RELEASE = Path("/private/tmp/mariamem-v050-release-clone")
SOURCE_COMMIT = "44100ec676c8c9064f32f3a01bd9a990d487bb61"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--blocks", type=int, default=30)
    parser.add_argument("--name", choices=("config-comparison", "config-comparison-unrestricted"),
                        default="config-comparison")
    args = parser.parse_args()
    if not 1 <= args.blocks <= 30:
        raise SystemExit("bounded comparison requires 1..30 blocks")
    if subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=RELEASE, text=True).strip() != SOURCE_COMMIT:
        raise SystemExit("release source identity changed")
    build = json.loads((EVIDENCE / "config-build.json").read_text())
    for value in (1, 0):
        arm = f"flush-sync-{value}"
        if sha(TEMP / f"ownedprepared-{arm}") != build[arm]["binary_sha256"]:
            raise SystemExit(f"binary identity differs: {arm}")
        if build[arm]["sql_setting"] != str(value):
            raise SystemExit(f"SQL setting not verified: {arm}")
    destination = EVIDENCE / f"{args.name}.jsonl"
    if destination.exists():
        raise SystemExit("refusing existing comparison output")
    inputs = {"source_commit": SOURCE_COMMIT, "guest_sha256":
              "7c7b6ce5168a1a0d98019751b4c36c25f2e9948dbae0124ec3f434efb0b8642c",
              "blocks": args.blocks, "binaries": {str(v): build[f"flush-sync-{v}"]["binary_sha256"] for v in (1, 0)},
              "config_sql_probe": {str(v): build[f"flush-sync-{v}"]["sql_setting"] for v in (1, 0)},
              "fixture": "10 MiB, 8 InnoDB tables, 4 independent Fresh DBs, 4 workers, app-connections",
              "tail_threshold_seconds": .9}
    (EVIDENCE / f"{args.name}-inputs.json").write_text(json.dumps(inputs, indent=2) + "\n")
    env = os.environ.copy()
    env.pop("MARIAMEM_TIMING_DIR", None)
    env.pop("MARIAMEM_SPIKE_TRACE", None)
    with destination.open("w") as out:
        for block in range(args.blocks):
            order = (1, 0) if block % 2 == 0 else (0, 1)
            for value in order:
                arm = f"flush-sync-{value}"
                output = TEMP / f"config-{block:02d}-{arm}.json"
                command = [str(TEMP / f"ownedprepared-{arm}"), "-payload-mib", "10", "-tables", "8",
                           "-workers", "4", "-forks", "4", "-workload", "app-connections",
                           "-lifecycle", "fresh", "-label", f"v0.5.0-{arm}", "-out", str(output)]
                started = datetime.now(timezone.utc).isoformat()
                completed = subprocess.run(command, cwd=RELEASE, env=env,
                                           capture_output=True, text=True, timeout=90)
                if completed.returncode:
                    (EVIDENCE / f"{args.name}-failure-{block:02d}-{arm}.txt").write_text(completed.stderr)
                    raise RuntimeError(f"block {block} {arm} failed: {completed.returncode}")
                report = json.loads(output.read_text())
                ready = [op["seconds"] for op in report["operations"] if op["name"].startswith("fresh_ready_")]
                if len(ready) != 4:
                    raise RuntimeError(f"block {block} {arm} missing ready samples")
                record = {"block": block, "arm": arm, "started_utc": started,
                          "suite_wall_seconds": report["suite_product_seconds"],
                          "ready_seconds": ready, "tail_starts": sum(x >= .9 for x in ready)}
                out.write(json.dumps(record, separators=(",", ":")) + "\n")
                out.flush()
                output.unlink()
                print(block, arm, "wall", round(record["suite_wall_seconds"], 3),
                      "max ready", round(max(ready), 3), flush=True)


if __name__ == "__main__":
    main()
