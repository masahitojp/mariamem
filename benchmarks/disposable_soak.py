#!/usr/bin/env python3
"""Serialized-by-caller public-API lifecycle diagnostic; no production tuning."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work", type=Path, required=True)
    parser.add_argument("--generations", type=int, default=50)
    parser.add_argument("--databases", type=int, default=16)
    parser.add_argument("--timeout", type=int, default=900)
    args = parser.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)
    work = args.work.resolve()
    env = dict(os.environ, GOTOOLCHAIN="go1.26.8")
    # Do not allow ambient compatibility overrides to change the measured path.
    for key in ("MARIAMEM_RUNTIME", "MARIAMEM_NATIVE_DIR", "MARIAMEM_GENERATED_HOST",
                "MARIAMEM_GENERATED_GUEST", "MARIAMEM_TIMING", "MARIAMEM_DIAGNOSTICS"):
        env.pop(key, None)
    helper = work / "process-cost"
    binary = work / "disposable-soak"
    subprocess.run(["cc", "-O2", str(ROOT / "benchmarks/tools/process_cost.c"), "-o", str(helper)],
                   check=True, cwd=ROOT, env=env)
    subprocess.run(["go", "build", "-o", str(binary), "./benchmarks/disposable_soak"],
                   check=True, cwd=ROOT, env=env)
    metadata = {
        "schema": "v041-disposable-soak-v1",
        "source_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "source_diff": subprocess.check_output(["git", "diff", "--stat"], cwd=ROOT, text=True),
        "go": subprocess.check_output(["go", "version"], cwd=ROOT, env=env, text=True).strip(),
        "platform": platform.platform(), "machine": platform.machine(),
        "databases": args.databases, "generations": args.generations,
        "timeout_seconds": args.timeout,
        "gc_policy": "normal Go policy; no runtime.GC or FreeOSMemory",
        "cpu_boundary": "self process CPU before generation through after Close counter; observer parent overhead included",
        "ready_boundary": "concurrent public Options{} Start through first SELECT 1 for every DB",
        "memory_boundary": "same long-lived self process, no child DB processes; macOS phys_footprint / RSS",
        "binary_sha256": hashlib.sha256(binary.read_bytes()).hexdigest(),
        "helper_sha256": hashlib.sha256(helper.read_bytes()).hexdigest(),
        "harness_sha256": hashlib.sha256((ROOT / "benchmarks/disposable_soak/main.go").read_bytes()).hexdigest(),
    }
    (work / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    command = [str(binary), "-databases", str(args.databases), "-generations", str(args.generations),
               "-cost-helper", str(helper), "-jsonl", str(work / "checkpoints.jsonl")]
    begin = time.monotonic()
    try:
        result = subprocess.run(command, cwd=ROOT, env=env, timeout=args.timeout)
        metadata["exit_code"] = result.returncode
    except subprocess.TimeoutExpired:
        # Timeout supervises this diagnostic process only; it is not an in-process reclamation claim.
        metadata["timeout"] = True
        metadata["exit_code"] = 124
    metadata["elapsed_seconds"] = time.monotonic() - begin
    (work / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n")
    raise SystemExit(metadata["exit_code"])


if __name__ == "__main__":
    main()
