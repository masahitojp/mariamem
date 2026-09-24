#!/usr/bin/env python3
"""Validate recorded guest source evidence; optionally repeat sysroot comparison."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess
import tarfile

from common import ROOT, LOCK, digest
from runtime_sources import verify_runtime_sources

EVIDENCE = "release/guest-source-provenance.json"
MAJOR = ("libc.a", "libc++.a", "libc++abi.a", "libunwind.a",
         "libclang_rt.builtins-wasm32.a", "crt1.o", "libwasi-emulated-mman.a",
         "libwasi-emulated-process-clocks.a")


def inventory_digest(inventory):
    return hashlib.sha256(json.dumps(inventory, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def read_inventory(archive, prefix):
    inventory = {}
    with tarfile.open(archive, "r:gz") as tar:
        for member in tar:
            if not member.name.startswith(prefix):
                continue
            name = member.name[len(prefix):]
            if not name or member.isdir():
                continue
            path = PurePosixPath(name)
            if path.is_absolute() or ".." in path.parts or name in inventory:
                raise ValueError("unsafe or duplicate sysroot entry")
            if member.isfile():
                inventory[name] = ["file", hashlib.sha256(tar.extractfile(member).read()).hexdigest()]
            elif member.issym():
                inventory[name] = ["symlink", member.linkname]
            else:
                raise ValueError("unsupported sysroot member")
    return inventory


def verify_inventory(inventory, evidence):
    sysroot = evidence["sysroot"]
    if len(inventory) != sysroot["comparison"]["entries"]:
        raise ValueError("sysroot entry count mismatch")
    if inventory_digest(inventory) != sysroot["comparison"]["inventory_sha256"]:
        raise ValueError("sysroot inventory mismatch")
    for name, expected in sysroot["major_library_sha256"].items():
        if inventory.get("lib/wasm32-wasi/" + name) != ["file", expected]:
            raise ValueError(f"sysroot library mismatch: {name}")


def verify_evidence(root, lock, build_records):
    path = root / EVIDENCE
    evidence = json.loads(path.read_text())
    review = json.loads((root / "release/review.json").read_text())["checks"]["guest_source"]
    if review.get("passed") and review.get("evidence") != EVIDENCE:
        raise ValueError("guest source review does not reference provenance evidence")
    if evidence["version"] != 1 or evidence["binary_release_ready"] is not False:
        raise ValueError("invalid provenance scope")
    sysroot = evidence["sysroot"]
    if (sysroot["tag"] != lock["toolchain"]["wasix_sysroot"]
            or sysroot["variant"] != lock["toolchain"]["wasix_sysroot_variant"]):
        raise ValueError("sysroot tag/variant mismatch")
    expected_url = ("https://github.com/wasix-org/wasix-libc/releases/download/"
                    + sysroot["tag"] + "/" + sysroot["variant"] + ".tar.gz")
    if sysroot["url"] != expected_url or set(sysroot["major_library_sha256"]) != set(MAJOR):
        raise ValueError("invalid sysroot asset/libraries")
    comparison = sysroot["comparison"]
    if comparison["entries"] <= 0 or any(comparison[k] != 0 for k in ("missing", "extra", "changed")):
        raise ValueError("sysroot comparison did not pass")
    if build_records.get("guest-build.json") != evidence["guest_build"]:
        raise ValueError("guest build differs from reviewed artifact")
    prepared = build_records.get("prepared-source.json", {})
    if prepared.get("modified_files") != evidence["modified_guest_files"]:
        raise ValueError("guest source inputs differ from reviewed build")
    entries = {e["name"]: e for e in lock["inputs"] if e["name"] != "wasmer-source" and e.get("kind") != "runtime-binary"}
    if set(entries) != set(evidence["source_archives"]):
        raise ValueError("guest source inventory mismatch")
    pins = {p["source_input"]: p["commit"] for p in lock["runtime_source_submodules_to_collect"]}
    for name, recorded in evidence["source_archives"].items():
        entry = entries[name]
        archive = root / "build/downloads" / entry["file"]
        if recorded["sha256"] != entry["sha256"] or digest(archive) != recorded["sha256"]:
            raise ValueError(f"guest source archive mismatch: {name}")
        if entry.get("revision") and recorded.get("revision") != entry["revision"]:
            raise ValueError(f"source revision mismatch: {name}")
        if name == "wasix-libc" or name in pins:
            with tarfile.open(archive) as tar:
                if tar.pax_headers.get("comment") != recorded["revision"]:
                    raise ValueError(f"source PAX commit mismatch: {name}")
            if name in pins and recorded["revision"] != pins[name]:
                raise ValueError(f"source submodule pin mismatch: {name}")
    if evidence["upstream_build"]["commit"] != evidence["source_archives"]["wasix-libc"]["revision"]:
        raise ValueError("upstream build/source commit mismatch")
    return {"evidence": EVIDENCE, "sha256": digest(path),
            "wasm_sha256": evidence["guest_build"]["wasm_sha256"],
            "module_sha256": evidence["guest_build"]["module_sha256"],
            "sysroot_asset_sha256": sysroot["sha256"],
            "recorded_sysroot_entries": comparison["entries"]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sysroot-archive", type=Path)
    parser.add_argument("--compare-build-image", action="store_true",
                        help="read the recorded Docker image without writes/network")
    args = parser.parse_args()
    if args.compare_build_image and not args.sysroot_archive:
        parser.error("--compare-build-image requires --sysroot-archive")
    records = {name: json.loads((ROOT / "build" / name).read_text())
               for name in ("guest-build.json", "prepared-source.json")}
    result = verify_evidence(ROOT, LOCK, records)
    verify_runtime_sources(ROOT, LOCK)
    evidence = json.loads((ROOT / EVIDENCE).read_text())
    if digest(ROOT / "build/prepared-source.json") != evidence["guest_build"]["prepared_source_sha256"]:
        raise ValueError("prepared source record hash mismatch")
    for filename, key in (("mariamem.wasm", "wasm_sha256"), ("mariamem.wasmu", "module_sha256")):
        if digest(ROOT / "build/guest" / filename) != evidence["guest_build"][key]:
            raise ValueError("guest artifact hash mismatch")
    result["source_and_local_guest_verified"] = True
    result["sysroot_asset_rechecked"] = False
    result["build_image_rechecked"] = False
    if args.sysroot_archive:
        if digest(args.sysroot_archive) != evidence["sysroot"]["sha256"]:
            raise ValueError("sysroot asset hash mismatch")
        inventory = read_inventory(args.sysroot_archive, evidence["sysroot"]["archive_prefix"])
        verify_inventory(inventory, evidence)
        result["sysroot_asset_rechecked"] = True
        if args.compare_build_image:
            code = '''import pathlib,hashlib,json,os
root=pathlib.Path("/root/.wasixcc/sysroot/sysroot-exnref-eh")
result={}
for p in root.rglob("*"):
    if p.is_symlink(): result[str(p.relative_to(root))]=["symlink",os.readlink(p)]
    elif p.is_file(): result[str(p.relative_to(root))]=["file",hashlib.sha256(p.read_bytes()).hexdigest()]
print(json.dumps(result))
'''
            actual = json.loads(subprocess.check_output([
                "docker", "run", "--rm", "--read-only", "--network", "none",
                evidence["guest_build"]["image_id"], "python3", "-c", code]))
            if actual != inventory:
                raise ValueError("build image sysroot differs from release payload")
            result["build_image_rechecked"] = True
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
