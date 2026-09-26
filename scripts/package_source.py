#!/usr/bin/env python3
"""Collect a source candidate without silently declaring legal completeness."""
import argparse
import gzip
import io
import json
import tarfile
from pathlib import Path
from common import ROOT, LOCK, digest, fetch
from check_public import check, public_files
from ci_guest_source import verify_ci_guest_source
from runtime_sources import verify_runtime_sources
from verify_guest_provenance import verify_evidence
from release_version import SOURCE_ROOT, SOURCE_CANDIDATE

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--ci-evidence-dir", type=Path,
                    help="canonical Linux guest WASM and macOS AOT build outputs")
args = parser.parse_args()
check()
out = ROOT / "build/release"
out.mkdir(parents=True, exist_ok=True)
archive = out / SOURCE_CANDIDATE
inputs = [entry for entry in LOCK["inputs"] if entry.get("kind") != "runtime-binary"]
for entry in inputs:
    fetch(entry["name"])
runtime_sources = verify_runtime_sources(ROOT, LOCK)
manifest = {"version": 1, "inputs_lock_sha256": digest(ROOT / "release/inputs.lock.json"),
            "files": {p.relative_to(ROOT).as_posix(): digest(p) for p in public_files()},
            "source_inputs": inputs, "runtime_sources": runtime_sources,
            "wasix_sysroot_variant": LOCK["toolchain"]["wasix_sysroot_variant"]}
if args.ci_evidence_dir:
    stage = args.ci_evidence_dir.resolve()
    manifest["build_records"] = {
        name: json.loads(path.read_text()) for name, path in {
            "prepared-source.json": stage / "guest-wasm/prepared-source.json",
            "toolchain.json": stage / "guest-wasm/toolchain.json",
            "guest-wasm-provenance.json": stage / "guest-wasm/provenance.json",
            "guest-aot-provenance.json": stage / "guest-aot/provenance.json",
        }.items()
    }
    manifest["guest_source_provenance"] = verify_ci_guest_source(
        ROOT, LOCK, stage, manifest["build_records"])
    manifest["source_complete"] = True
    manifest["build_path"] = "linux-x86_64-wasm/" + ("ubuntu24.04-x86_64-aot" if manifest["build_records"]["guest-aot-provenance.json"].get("aot_platform") == "ubuntu24.04-x86_64" else "macos-arm64-aot")
    # Approval and clean-platform acceptance can only happen after immutable
    # binary construction. Neither is an input to this archive.
else:
    review = json.loads((ROOT / "release/review.json").read_text())
    provenance = [ROOT / "build" / name for name in
                  ("prepared-source.json", "preparation-inputs.lock.json", "guest-build.json")]
    manifest["source_complete"] = bool(review["checks"]["guest_source"].get("passed"))
    manifest["review"] = review
    manifest["build_records"] = {p.name: json.loads(p.read_text()) for p in provenance if p.exists()}
    manifest["guest_source_provenance"] = verify_evidence(ROOT, LOCK, manifest["build_records"])
with archive.open("wb") as raw, gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as gz:
    with tarfile.open(fileobj=gz, mode="w") as tar:
        def add(path, name):
            info = tar.gettarinfo(str(path), arcname=SOURCE_ROOT + "/" + name)
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            info.mtime = 0
            with path.open("rb") as stream:
                tar.addfile(info, stream)
        for path in public_files():
            add(path, path.relative_to(ROOT).as_posix())
        for entry in inputs:
            add(ROOT / "build/downloads" / entry["file"], "build/downloads/" + entry["file"])
        content = (json.dumps(manifest, indent=2) + "\n").encode()
        info = tarfile.TarInfo(SOURCE_ROOT + "/build/source-manifest.json")
        info.size = len(content)
        tar.addfile(info, io.BytesIO(content))
record = {"file": archive.name, "sha256": digest(archive), "bytes": archive.stat().st_size,
          "manifest": manifest}
(out / "source-manifest.json").write_text(json.dumps(record, indent=2) + "\n")
print(f"Collected source candidate ({archive.stat().st_size} bytes); review remains required")
