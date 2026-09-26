#!/usr/bin/env python3
"""Verify an exact guest WASM handoff and compile it on a supported native target."""
import argparse
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess

from common import ROOT, LOCK, digest, extract, fetch
from release_version import PYTHON_VERSION
from native_target import current_target, platform_fields, elf_dependencies


def verify_handoff(directory):
    wasm = directory / "mariamem.wasm"
    provenance_path = directory / "provenance.json"
    provenance = json.loads(provenance_path.read_text())
    if (provenance.get("version") != 1 or provenance.get("linux_architecture") != "x86_64"
            or provenance.get("target") != "wasm32/WASIX"
            or provenance.get("wasm_file") != wasm.name):
        raise ValueError("invalid Linux guest WASM handoff")
    if provenance.get("inputs_lock_sha256") != digest(ROOT / "release/inputs.lock.json"):
        raise ValueError("guest WASM was built with a different input lock")
    prepared_path = directory / "prepared-source.json"
    if (digest(prepared_path) != provenance["prepared_source_sha256"]
            or json.loads(prepared_path.read_text()) != provenance["prepared_source"]):
        raise ValueError("guest prepared source record hash mismatch")
    toolchain_path = directory / "toolchain.json"
    if (digest(toolchain_path) != provenance["toolchain_provenance_sha256"]
            or json.loads(toolchain_path.read_text()) != provenance["toolchain"]):
        raise ValueError("guest toolchain record hash mismatch")
    current_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    if provenance.get("source_commit") != current_commit:
        raise ValueError("guest WASM source commit differs from checkout")
    expected = provenance["wasm_sha256"]
    if digest(wasm) != expected or wasm.stat().st_size != provenance["wasm_bytes"]:
        raise ValueError("transferred guest WASM SHA256/size mismatch")
    if (directory / "SHA256SUMS").read_text() != f"{expected}  {wasm.name}\n":
        raise ValueError("transferred guest WASM checksum record mismatch")
    with wasm.open("rb") as stream:
        header = stream.read(8)
    if header != b"\0asm\1\0\0\0":
        raise ValueError("transferred guest is not a WebAssembly module")
    return wasm, provenance_path, provenance


def compile_command(wasmer, wasm, output, target):
    command = [str(wasmer), "compile", str(wasm), "-o", str(output)]
    if target["goos"] == "linux":
        # An explicit triple and SSSE3 avoid Wasmer's unsupported SIMD libcall
        # fallback, without detecting optional features from the build runner.
        # Use a fixed baseline instead of
        # detecting optional features (such as AVX-512) from the build runner.
        command += ["--target", "x86_64-unknown-linux-gnu", "-m", "ssse3"]
    return command


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wasm-dir", type=Path, default=ROOT / "build/guest-wasm")
    args = parser.parse_args()
    target = current_target(ROOT)
    wasm, provenance_path, provenance = verify_handoff(args.wasm_dir)
    runtime = ROOT / "build/tools/wasmer-guest-aot"
    extract(fetch(target["runtime_input"]), runtime)
    wasmer = runtime / "bin/wasmer"
    wasmer_home = ROOT / "build/wasmer-home"
    wasmer_home.mkdir(exist_ok=True)
    env = dict(os.environ, WASMER_DIR=str(wasmer_home))
    version = subprocess.check_output([str(wasmer), "--version"], text=True, env=env).strip()
    if LOCK["toolchain"]["wasmer"] not in version:
        raise ValueError(f"unexpected Wasmer version: {version}")
    output = ROOT / "build/guest-aot"
    if output.exists():
        raise SystemExit(f"guest AOT output already exists: {output}")
    output.mkdir(parents=True)
    subprocess.run([str(wasmer), "validate", str(wasm)], check=True, env=env)
    aot = output / "mariamem.wasmu"
    subprocess.run(compile_command(wasmer, wasm, aot, target), check=True, env=env)
    headless = output / "wasmer-headless"
    shutil.copy2(runtime / "bin/wasmer-headless", headless)
    headless.chmod(headless.stat().st_mode | 0o111)
    sidecar = {"wasm_sha256": provenance["wasm_sha256"], "module_sha256": digest(aot),
               "snapshot_version": 1}
    (output / "mariamem.wasmu.json").write_text(json.dumps(sidecar, indent=2, sort_keys=True) + "\n")
    manifest = {"version": 1, **platform_fields(target),
                "package_version": PYTHON_VERSION,
                "sha256": {name: digest(output / name) for name in
                           ("wasmer-headless", "mariamem.wasmu", "mariamem.wasmu.json")}}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    record = {
        "version": 1, "source_commit": provenance["source_commit"],
        "wasm_handoff_provenance_sha256": digest(provenance_path),
        "wasm_sha256_verified": provenance["wasm_sha256"],
        "wasixcc_archive_sha256": provenance["toolchain"]["wasixcc_archive_sha256"],
        "aot_platform": target["platform"], "aot_architecture": target["architecture"],
        **({"macos_version": platform.mac_ver()[0], "macos_architecture": "arm64"}
           if target["goos"] == "darwin" else {"linux_os_release": platform.freedesktop_os_release(),
                                                "runtime_dependencies": elf_dependencies(headless),
                                                "aot_target_triple": "x86_64-unknown-linux-gnu",
                                                "aot_cpu_features": ["sse2", "ssse3"]}),
        "wasmer_version": version, "wasmer_archive_sha256": digest(fetch(target["runtime_input"])),
        "wasmer_executable_sha256": digest(wasmer),
        "headless_executable_sha256": digest(headless),
        "aot_sha256": digest(aot), "aot_bytes": aot.stat().st_size,
        "native_manifest_sha256": digest(output / "manifest.json"),
    }
    (output / "provenance.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n")
    print(json.dumps(record, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
