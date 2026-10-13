#!/usr/bin/env python3
"""Balanced v0.5.0 versus source-rebuilt guest Fresh comparison."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

WORK = Path(__file__).resolve().parents[4]
TEMP = WORK / "temp"
EVIDENCE = WORK / "evidence"
BASELINE = Path("/private/tmp/mariamem-v050-release-clone")
CANDIDATE = TEMP / "dev-native-rebound" / "product"
HOSTS = {
    "baseline": TEMP / "mariamem-host-baseline",
    "candidate": TEMP / "dev-native-rebound" / "mariamem-dev-host",
}
GO = {arm: TEMP / f"ownedprepared-{arm}" for arm in HOSTS}
PRODUCT = {"baseline": BASELINE, "candidate": CANDIDATE}
IMAGE = "mariadb@sha256:805c8e104bd563d5bfa24fadd3f31cd419ea859cb5277f32b5db714f9ed1"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("language", choices=("go", "python"))
    parser.add_argument("--blocks", type=int, default=30)
    args = parser.parse_args()
    if not 1 <= args.blocks <= 30:
        parser.error("blocks must be 1..30")
    if subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=BASELINE, text=True).strip() != "44100ec676c8c9064f32f3a01bd9a990d487bb61":
        parser.error("release baseline source changed")
    guest = json.loads((TEMP / "dev-native-rebound" / "development.json").read_text())
    if guest["source_identity"]["commit"] != "ad83e0039415a9277363d4cbdb32f21107cfbf13":
        parser.error("candidate source changed")
    if guest["guest_sha256"] != "7d1330e67b06eb810d0fafd649df0944dbca1b20cd7e49f8e5ecdde7f5ac8c09":
        parser.error("candidate guest changed")

    destination = EVIDENCE / f"source-fix-{args.language}.jsonl"
    if destination.exists():
        parser.error(f"refusing to overwrite {destination}")
    identities = {f"{arm}_{kind}": sha(path) for arm in HOSTS for kind, path in (("go", GO[arm]), ("host", HOSTS[arm]))}
    (EVIDENCE / f"source-fix-{args.language}-inputs.json").write_text(json.dumps({
        "blocks": args.blocks, "language": args.language, "binaries": identities,
        "baseline_source_commit": "44100ec676c8c9064f32f3a01bd9a990d487bb61",
        "candidate_source_commit": "ad83e0039415a9277363d4cbdb32f21107cfbf13",
        "candidate_guest_sha256": guest["guest_sha256"], "python": sys.version,
        "payload_mib": 10, "tables": 8, "workers": 4, "fresh_databases": 4,
    }, indent=2) + "\n")

    with destination.open("w") as out:
        for block in range(args.blocks):
            order = ("baseline", "candidate") if block % 2 == 0 else ("candidate", "baseline")
            for arm in order:
                result = TEMP / f"source-fix-{args.language}-{block:02d}-{arm}.json"
                env = os.environ.copy()
                env["PYTHONPATH"] = str(PRODUCT[arm] / "python")
                env.pop("MARIAMEM_TIMING_DIR", None)
                env.pop("MARIAMEM_SPIKE_TRACE", None)
                if args.language == "go":
                    command = [str(GO[arm]), "-payload-mib", "10", "-tables", "8", "-workers", "4", "-forks", "4",
                               "-workload", "app-connections", "-lifecycle", "fresh", "-label", arm, "-out", str(result)]
                else:
                    command = [sys.executable, str(BASELINE / "benchmarks/python_product_suites.py"),
                               "--mode", "fresh", "--host", str(HOSTS[arm]), "--image", IMAGE,
                               "--count", "4", "--workers", "4", "--payload-mib", "10", "--tables", "8", "--out", str(result)]
                started = datetime.now(timezone.utc).isoformat()
                run = subprocess.run(command, cwd=PRODUCT[arm], env=env, capture_output=True, text=True, timeout=120)
                if run.returncode:
                    (EVIDENCE / f"source-fix-{args.language}-failure-{block:02d}-{arm}.txt").write_text(run.stdout + "\n" + run.stderr)
                    raise RuntimeError(f"{args.language} block {block} {arm} exit {run.returncode}")
                report = json.loads(result.read_text())
                if args.language == "go":
                    ready = [item["seconds"] for item in report["operations"] if item["name"].startswith("fresh_ready_")]
                    wall = report["suite_product_seconds"]
                else:
                    if report.get("completed") is not True or len(report.get("samples", [])) != 4:
                        raise RuntimeError(f"incomplete Python oracle: {block} {arm}")
                    if any(not item["server_version"].startswith("12.3.3") for item in report["samples"]):
                        raise RuntimeError(f"unexpected Python guest version: {block} {arm}")
                    ready = [item["ready_seconds"] for item in report["samples"]]
                    wall = report["suite_wall_seconds"]
                if len(ready) != 4:
                    raise RuntimeError(f"missing ready sample: {block} {arm}")
                out.write(json.dumps({"block": block, "arm": arm, "started_utc": started,
                                      "ready_seconds": ready, "wall_seconds": wall,
                                      "tail_starts": sum(value >= .9 for value in ready)}, separators=(",", ":")) + "\n")
                out.flush()
                result.unlink()
                print(args.language, block, arm, round(wall, 3), round(max(ready), 3), flush=True)


if __name__ == "__main__":
    main()
