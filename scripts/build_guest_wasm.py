#!/usr/bin/env python3
"""Build the pinned WASIX guest on Linux x86_64 into an immutable handoff."""
import argparse
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess

from common import ROOT, LOCK, digest
from install_guest_toolchain import inventory


def verify_prepared():
    path = ROOT / "build/prepared-source.json"
    prepared = json.loads(path.read_text())
    if prepared["inputs_lock_sha256"] != digest(ROOT / "release/inputs.lock.json"):
        raise ValueError("prepared source input lock differs")
    overlays = {p.name: digest(p) for p in sorted((ROOT / "guest").iterdir()) if p.is_file()}
    if prepared["overlays"] != overlays:
        raise ValueError("guest overlays differ from prepared source")
    for name, expected in prepared["modified_files"].items():
        if digest(ROOT / "build/source" / name) != expected:
            raise ValueError(f"prepared guest source changed: {name}")
    return path, prepared


def verify_toolchain():
    path = ROOT / "build/tools/wasixcc-linux-x86_64.json"
    record = json.loads(path.read_text())
    pin = LOCK["toolchain"]["wasixcc_linux_x86_64"]
    expected = {"version": 1, "host": "linux-x86_64", "target": "wasm32/WASIX",
                "inputs_lock_sha256": digest(ROOT / "release/inputs.lock.json"),
                "wasixcc_version": LOCK["toolchain"]["wasixcc"],
                "wasixcc_archive_url": pin["url"],
                "wasixcc_archive_sha256": pin["sha256"],
                "llvm_tag": LOCK["toolchain"]["llvm"],
                "binaryen_tag": LOCK["toolchain"]["binaryen"],
                "sysroot_tag": LOCK["toolchain"]["wasix_sysroot"],
                "sysroot_variant": LOCK["toolchain"]["wasix_sysroot_variant"]}
    for key, value in expected.items():
        if record.get(key) != value:
            raise ValueError(f"WASIXCC toolchain record mismatch: {key}")
    home = Path.home() / ".wasixcc"
    for name, expected_hash in record["selected_executables_sha256"].items():
        if digest(home / name) != expected_hash:
            raise ValueError(f"WASIXCC executable changed: {name}")
    sysroot = home / "sysroot" / record["sysroot_variant"]
    if inventory(sysroot) != record["sysroot"]:
        raise ValueError("WASIXCC sysroot changed")
    for name, expected_hash in record["sysroot_major_libraries_sha256"].items():
        if digest(sysroot / "lib/wasm32-wasi" / name) != expected_hash:
            raise ValueError(f"WASIXCC sysroot library changed: {name}")
    return path, record, home


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jobs", type=int, default=3)
    args = parser.parse_args()
    if args.jobs < 1:
        parser.error("--jobs must be positive")
    if platform.system() != "Linux" or platform.machine() != "x86_64":
        raise SystemExit("WASIX guest build requires Linux x86_64")
    prepared_path, prepared = verify_prepared()
    toolchain_path, toolchain, home = verify_toolchain()
    output = ROOT / "build/guest-wasm"
    if output.exists():
        raise SystemExit(f"guest WASM handoff already exists: {output}")
    script = ROOT / "build/source/wasm/build-wasix.sh"
    if not script.is_file():
        raise ValueError("prepared guest build script is missing")
    env = dict(os.environ, JOBS=str(args.jobs), PATH=f"{home / 'bin'}{os.pathsep}{os.environ.get('PATH', '')}")
    log = ROOT / "build/guest-wasm-build.log"
    print(f"Building WASIX guest; output is in {log}", flush=True)
    with log.open("w") as stream:
        subprocess.run(["bash", str(script)], cwd=ROOT / "build/source", env=env,
                       stdout=stream, stderr=subprocess.STDOUT, check=True)
    built = ROOT / "build/source/wasm/dist/lite4mariadb.wasix.wasm"
    with built.open("rb") as stream:
        header = stream.read(8)
    if header != b"\0asm\1\0\0\0":
        raise ValueError("guest output is not a WebAssembly module")
    output.mkdir(parents=True)
    wasm = output / "mariamem.wasm"
    shutil.copyfile(built, wasm)
    shutil.copyfile(prepared_path, output / "prepared-source.json")
    shutil.copyfile(toolchain_path, output / "toolchain.json")
    source_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    record = {
        "version": 1, "source_commit": source_commit, "linux_architecture": "x86_64",
        "target": "wasm32/WASIX", "inputs_lock_sha256": prepared["inputs_lock_sha256"],
        "prepared_source_sha256": digest(prepared_path),
        "prepared_source": prepared,
        "toolchain_provenance_sha256": digest(toolchain_path),
        "toolchain": toolchain,
        "wasm_file": wasm.name, "wasm_sha256": digest(wasm), "wasm_bytes": wasm.stat().st_size,
    }
    (output / "provenance.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    (output / "SHA256SUMS").write_text(f"{record['wasm_sha256']}  {wasm.name}\n")
    print(json.dumps(record, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
