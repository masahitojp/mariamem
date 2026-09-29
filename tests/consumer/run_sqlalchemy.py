#!/usr/bin/env python3
"""Run the installed-wheel SQLAlchemy application outside the checkout."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--without-found-rows", action="store_true", help="Exploratory compatibility workaround; changes matched-rowcount semantics")
    args = parser.parse_args()
    source = Path(__file__).with_name("test_sqlalchemy_dogfood.py")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    env = {key: value for key, value in os.environ.items()
           if not key.startswith(("MARIAMEM_", "MYSQLMEM_", "PYTHON", "PYTEST", "DOGFOOD_"))}
    runs = []
    # Two order-balanced observations, not a performance benchmark.
    with tempfile.TemporaryDirectory(prefix="mariamem-sqlalchemy-") as temporary:
        project = Path(temporary)
        shutil.copy(source, project / source.name)
        for index, mode in enumerate(("start", "fork", "fork", "start")):
            name = f"{index + 1}-{mode}"
            evidence = output / f"{name}.json"
            junit = output / f"{name}.xml"
            started = time.monotonic()
            result = subprocess.run(
                [sys.executable, "-m", "pytest", "-q", source.name, "--junitxml", str(junit)],
                cwd=project, env={**env, "DOGFOOD_MODE": mode, "DOGFOOD_WITHOUT_FOUND_ROWS": "1" if args.without_found_rows else "0", "DOGFOOD_EVIDENCE": str(evidence)},
                capture_output=True, text=True, timeout=180)
            (output / f"{name}.log").write_text(result.stdout + result.stderr)
            counts = [dict(suite.attrib) for suite in ET.parse(junit).getroot().iter("testsuite")] if junit.exists() else []
            runs.append({"name": name, "mode": mode, "returncode": result.returncode,
                         "suite_seconds": time.monotonic() - started, "junit": counts})
            print(f"{name}: exit={result.returncode}; {counts}; log={output / f'{name}.log'}", flush=True)
    report = {"source_commit": subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=source.parents[2], text=True).strip(),
        "runs": runs, "passed": all(run["returncode"] == 0 for run in runs)}
    (output / "summary.json").write_text(json.dumps(report, indent=2) + "\n")
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
