#!/usr/bin/env python3
"""Build the pinned guest with Docker, then compile its macOS arm64 AOT artifact."""
import argparse
import json
import os
import platform
import shutil
import subprocess
from common import ROOT, digest, fetch, extract

parser = argparse.ArgumentParser()
parser.add_argument("--image", default="mariamem-wasix-build:0.4.7")
parser.add_argument("--jobs", type=int, default=4)
args = parser.parse_args()
if platform.system() != "Darwin" or platform.machine() != "arm64":
    raise SystemExit("The first AOT target is macOS arm64")
if not (ROOT / "build/prepared-source.json").exists():
    raise SystemExit("Run python3 scripts/prepare_guest.py first")
runtime = ROOT / "build/tools/wasmer"
if not runtime.exists():
    extract(fetch("wasmer"), runtime)
log = ROOT / "build/guest-build.log"
print("Building MariaDB; output is in build/guest-build.log", flush=True)
with log.open("w") as stream:
    subprocess.run(["docker", "run", "--rm", "--platform", "linux/arm64",
                    "-v", f"{ROOT / 'build/source'}:/work", "-e", f"JOBS={args.jobs}",
                    args.image, "bash", "wasm/build-wasix.sh"], check=True,
                   stdout=stream, stderr=subprocess.STDOUT)
out = ROOT / "build/guest"
out.mkdir(parents=True, exist_ok=True)
wasm, aot = out / "mariamem.wasm", out / "mariamem.wasmu"
shutil.copy2(ROOT / "build/source/wasm/dist/lite4mariadb.wasix.wasm", wasm)
env = dict(os.environ, WASMER_DIR=str(ROOT / "build/wasmer-home"))
subprocess.run([str(runtime / "bin/wasmer"), "validate", str(wasm)], check=True, env=env)
subprocess.run([str(runtime / "bin/wasmer"), "compile", str(wasm), "-o", str(aot)], check=True, env=env)
metadata = {"wasm_sha256": digest(wasm), "module_sha256": digest(aot), "snapshot_version": 1}
aot.with_suffix(aot.suffix + ".json").write_text(json.dumps(metadata, indent=2) + "\n")
record = {**metadata, "prepared_source_sha256": digest(ROOT / "build/prepared-source.json"),
          "image_id": subprocess.check_output(["docker", "image", "inspect", args.image,
                                                "--format", "{{.Id}}"], text=True).strip()}
(ROOT / "build/guest-build.json").write_text(json.dumps(record, indent=2) + "\n")
print(json.dumps(record, indent=2))
