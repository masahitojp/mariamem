#!/usr/bin/env python3
"""Run the pinned GORM consumer outside the checkout, writing ignored evidence."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-dir", type=Path, help="Development-only local module replacement")
    parser.add_argument("--zero-options", action="store_true", help="Use Options{} with the supported environment override for this untagged build")
    args = parser.parse_args()
    native, output = args.native_dir.resolve(), args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(("MARIAMEM_", "MYSQLMEM_", "DOGFOOD_"))}
    env["GOTOOLCHAIN"] = "go1.26.8"
    env["GOWORK"] = "off"
    runs = []
    with tempfile.TemporaryDirectory(prefix="mariamem-gorm-") as temporary:
        project = Path(temporary)
        for source in Path(__file__).with_name("gorm").iterdir():
            shutil.copyfile(source, project / source.name)
        if args.source_dir:
            subprocess.run(["go", "mod", "edit", "-replace",
                            f"github.com/masahitojp/mariamem={args.source_dir.resolve()}"],
                           cwd=project, env=env, check=True)
        if args.zero_options:
            env["MARIAMEM_NATIVE_DIR"] = str(native)
            env["DOGFOOD_ZERO_OPTIONS"] = "1"
        for index, mode in enumerate(("start", "fork", "fork", "start"), 1):
            name = f"{index}-{mode}"
            begin = time.monotonic()
            result = subprocess.run(
                ["go", "test", "-mod=readonly", "-v", "-count=1", "-timeout=3m", "."],
                cwd=project, env={**env, "DOGFOOD_MODE": mode,
                                  "DOGFOOD_NATIVE_DIR": str(native),
                                  "DOGFOOD_EVIDENCE": str(output / f"{name}.json")},
                capture_output=True, text=True, timeout=240)
            (output / f"{name}.txt").write_text(result.stdout + result.stderr)
            runs.append({"name": name, "exit_code": result.returncode,
                         "runner_seconds": time.monotonic() - begin})
            print(json.dumps(runs[-1]), flush=True)
    (output / "summary.json").write_text(json.dumps(runs, indent=2) + "\n")
    return int(any(run["exit_code"] for run in runs))


if __name__ == "__main__":
    raise SystemExit(main())
